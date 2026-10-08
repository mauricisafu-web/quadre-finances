"""CLI del quadre de comandament financer.

    python -m quadre init
    python -m quadre valida FITXER...
    python -m quadre importa [FITXER...]          (per defecte, tota la safata d'entrada)
    python -m quadre carrega-inicial
    python -m quadre quadre [--no-obris]
    python -m quadre estat
    python -m quadre remissio [--tots] [--ics]
    python -m quadre remissio marca CODI PERIODE --data AAAA-MM-DD [--justificant TEXT] [--no-escau]
    python -m quadre discrepancies [resol ID --estat resolta|acceptada --text TEXT]
    python -m quadre esquema
    python -m quadre copia
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from quadre.config import ARREL, carrega
from quadre.nucli.numeros import json_per_fitxa, llegeix_fitxer
from quadre.nucli.validacio import valida

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CHROME = [Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
          Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
          Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe"]


def _repo():
    from quadre.nucli.repositori import Repositori
    return Repositori()


def _obre(ruta: Path):
    for c in CHROME:
        if c.exists():
            subprocess.Popen([str(c), ruta.resolve().as_uri()])
            return
    os.startfile(ruta)  # type: ignore[attr-defined]


def cmd_init(a):
    cfg = carrega()
    for d in (cfg.safata_entrada, cfg.safata_rebutjades, cfg.registre, cfg.sortida, cfg.bd.parent):
        d.mkdir(parents=True, exist_ok=True)
    r = _repo()
    print(f"BD: {r.ruta_bd}\nSafata: {cfg.safata_entrada}\nRegistre: {cfg.registre}")


def cmd_valida(a):
    from quadre.nucli.repositori import Repositori
    repo = Repositori() if carrega().bd.exists() else None
    codi = 0
    for f in a.fitxers:
        p = Path(f)
        print(f"== {p.name}")
        try:
            inf = valida(llegeix_fitxer(p), repo=repo)
        except json.JSONDecodeError as e:
            print(f"✘ JSON mal format: {e}")
            codi = 1
            continue
        print(inf.text())
        codi |= 0 if inf.es_valida else 1
    sys.exit(codi)


def _importa_fitxers(repo, fitxers: list[Path], de_safata: bool):
    from quadre.nucli.repositori import mou_a
    cfg = repo.cfg
    resum = {"importada": 0, "duplicada": 0, "rebutjada": 0}
    for p in fitxers:
        try:
            dades = llegeix_fitxer(p)
        except json.JSONDecodeError as e:
            print(f"✘ {p.name}: JSON mal format ({e})")
            resum["rebutjada"] += 1
            if de_safata:
                (cfg.safata_rebutjades / (p.name + ".err.txt")).write_text(f"JSON mal format: {e}\n", encoding="utf-8")
                mou_a(p, cfg.safata_rebutjades)
            continue
        r = repo.importa(dades, fitxer_origen=p.name)
        resum[r.estat] += 1
        if r.estat == "importada":
            print(f"✔ {p.name} → {r.clau_expedient} v{r.versio}  ({r.ruta_registre.relative_to(ARREL)})")
            for t in r.informe.avisos:
                print(f"    avís: {t.missatge}")
            for c in (r.canvis or [])[:15]:
                print(f"    canvi: {c}")
            if de_safata:
                mou_a(p, cfg.safata_entrada.parent / "processades")
        elif r.estat == "duplicada":
            print(f"= {p.name}: ja registrada (mateix contingut)")
            if de_safata:
                mou_a(p, cfg.safata_entrada.parent / "processades")
        else:
            print(f"✘ {p.name}: rebutjada")
            print(r.informe.text())
            if de_safata:
                (cfg.safata_rebutjades / (p.name + ".err.txt")).write_text(r.informe.text() + "\n", encoding="utf-8")
                mou_a(p, cfg.safata_rebutjades)
    print(f"\nResum: {resum['importada']} importades · {resum['duplicada']} duplicades · {resum['rebutjada']} rebutjades")


def cmd_importa(a):
    repo = _repo()
    if a.fitxers:
        _importa_fitxers(repo, [Path(f) for f in a.fitxers], de_safata=False)
    else:
        fitxers = sorted(repo.cfg.safata_entrada.glob("*.json"))
        if not fitxers:
            print(f"La safata d'entrada és buida ({repo.cfg.safata_entrada}).")
            return
        _importa_fitxers(repo, fitxers, de_safata=True)


def cmd_carrega_inicial(a):
    repo = _repo()
    _importa_fitxers(repo, sorted((ARREL / "dades_inicials").glob("*.json")), de_safata=False)


def cmd_quadre(a):
    from quadre.sortida.quadre_html import genera
    repo = _repo()
    desti = genera(repo, repo.cfg.sortida / "quadre.html")
    print(f"Quadre generat: {desti}")
    if not a.no_obris:
        _obre(desti)


def cmd_estat(a):
    from quadre.nucli import regles
    from quadre.remissio import calendari
    repo = _repo()
    exs = repo.exercicis()
    if not exs:
        print("Encara no hi ha cap liquidació importada.")
    else:
        ex = max(exs)
        print(f"Regles fiscals {ex}:")
        for r in regles.regles_fiscals(repo, ex):
            print(f"  [{r.estat:^11}] {r.nom}: {r.text_valor} — {r.frase}{' (provisional)' if r.provisional else ''}")
    print("\nAlertes:")
    for al in regles.alertes(repo, calendari.genera(repo)):
        if al.severitat != "info":
            print(f"  {al.severitat.upper():8} {al.titol}")


def cmd_remissio(a):
    from quadre.remissio import calendari
    repo = _repo()
    if a.accio == "marca":
        if not (a.codi and a.periode):
            sys.exit("Ús: remissio marca CODI PERIODE --data AAAA-MM-DD [--justificant …] [--no-escau]")
        if not a.no_escau and not a.data:
            sys.exit("Cal --data (o --no-escau)")
        from quadre.nucli.cataleg import obligacions
        o = obligacions().get(a.codi)
        if not o:
            sys.exit(f"Obligació desconeguda: {a.codi}. Codis: {', '.join(obligacions())}")
        any_ = int(a.periode[:4]) if a.periode[:4].isdigit() else date.today().year
        fitxa = {
            "$fitxa": "torre-finances/expedient@1", "entitat": {"nif": repo.cfg.entitat.nif}, "tipus": "tramesa",
            "expedient": {"num": None, "exercici": any_, "titol": f"Tramesa {a.codi} {a.periode}: {o['nom']}",
                          "estat_tramit": "executat" if not a.no_escau else "arxivat"},
            "font": {"origen": "manual", "generat_el": datetime.now().astimezone().isoformat()},
            "dades": {"obligacio": a.codi, "periode": a.periode, "estat": "no_escau" if a.no_escau else "tramesa",
                      "data_tramesa": a.data, "justificant": a.justificant, "observacions": a.observacions},
        }
        # Cada tramesa té clau pròpia (obligació + període): vegeu Fitxa.clau_expedient().
        r = repo.importa(json.loads(json_per_fitxa(fitxa)), fitxer_origen="cli:remissio marca")
        if r.estat == "rebutjada":
            print(r.informe.text())
            sys.exit(1)
        print(f"✔ Registrada: {a.codi} · {a.periode} ({r.estat})")
        return

    vs = calendari.genera(repo)
    if a.ics:
        desti = repo.cfg.sortida / "remissio.ics"
        desti.parent.mkdir(parents=True, exist_ok=True)
        desti.write_text(calendari.a_ics(vs), encoding="utf-8")
        print(f"Calendari exportat: {desti} (obre'l amb Outlook per afegir els venciments amb avís 7 dies abans)")
        return
    for v in vs:
        if not a.tots and v.estat in ("futura", "complerta", "no_escau") and (v.dies or 0) > 90:
            continue
        venc = v.venciment.strftime("%d/%m/%Y") if v.venciment else "   —    "
        print(f"{v.etiqueta:28} {venc}  {v.codi:30} {v.titol:28} {v.organisme}")
    print("\n(--tots per veure-ho tot; --ics per exportar a Outlook)")


def cmd_discrepancies(a):
    repo = _repo()
    if a.accio == "resol":
        repo.resol_discrepancia(int(a.id), a.estat, a.text or "")
        print(f"Discrepància {a.id}: {a.estat}")
        return
    ds = repo.discrepancies()
    if not ds:
        print("No hi ha discrepàncies obertes.")
    for d in ds:
        print(f"#{d['id']} [{d['origen']}] {d['descripcio']} · {d['valors']} · {d.get('clau_expedient') or ''}")


def cmd_esquema(a):
    from quadre.nucli.models import esquema_json
    desti = Path(a.sortida) if a.sortida else ARREL / "skill" / "fitxa-financera" / "esquema.json"
    desti.write_text(json.dumps(esquema_json(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Esquema JSON: {desti}")


def cmd_copia(a):
    repo = _repo()
    destins = list(repo.cfg.copies) or [ARREL / "dades" / "copies"]
    for d in destins:
        try:
            f = repo.copia_seguretat(d)
            print(f"✔ Còpia: {f}")
            _rotacio(d)
        except OSError as e:
            print(f"✘ No s'ha pogut copiar a {d}: {e}")


def _rotacio(carpeta: Path, conserva: int = 30):
    copies = sorted(carpeta.glob("finances_*.db"))
    for f in copies[:-conserva]:
        f.unlink()


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m quadre", description="Quadre de comandament financer")
    s = p.add_subparsers(dest="ordre", required=True)
    s.add_parser("init").set_defaults(f=cmd_init)
    x = s.add_parser("valida"); x.add_argument("fitxers", nargs="+"); x.set_defaults(f=cmd_valida)
    x = s.add_parser("importa"); x.add_argument("fitxers", nargs="*"); x.set_defaults(f=cmd_importa)
    s.add_parser("carrega-inicial").set_defaults(f=cmd_carrega_inicial)
    x = s.add_parser("quadre"); x.add_argument("--no-obris", action="store_true"); x.set_defaults(f=cmd_quadre)
    s.add_parser("estat").set_defaults(f=cmd_estat)
    x = s.add_parser("remissio")
    x.add_argument("accio", nargs="?", choices=["marca"])
    x.add_argument("codi", nargs="?"); x.add_argument("periode", nargs="?")
    x.add_argument("--data"); x.add_argument("--justificant"); x.add_argument("--observacions")
    x.add_argument("--no-escau", action="store_true"); x.add_argument("--tots", action="store_true")
    x.add_argument("--ics", action="store_true"); x.set_defaults(f=cmd_remissio)
    x = s.add_parser("discrepancies"); x.add_argument("accio", nargs="?", choices=["resol"]); x.add_argument("id", nargs="?")
    x.add_argument("--estat", default="resolta", choices=["resolta", "acceptada"]); x.add_argument("--text")
    x.set_defaults(f=cmd_discrepancies)
    x = s.add_parser("esquema"); x.add_argument("--sortida"); x.set_defaults(f=cmd_esquema)
    s.add_parser("copia").set_defaults(f=cmd_copia)
    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
