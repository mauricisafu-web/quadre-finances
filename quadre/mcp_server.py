"""Servidor MCP local `finances-torre` (transport stdio).

Permet que Claude (Desktop, Cowork o Claude Code) desi fitxes a la safata d'entrada i consulti
les xifres i el calendari de remissió. NO importa res a la BD: la importació la decideix l'usuari
(`python -m quadre importa`).

Registre a Claude Code (àmbit d'usuari):
    claude mcp add --scope user finances-torre -- C:\\Users\\secretari\\quadre-finances\\.venv\\Scripts\\python.exe C:\\Users\\secretari\\quadre-finances\\quadre\\mcp_server.py
Registre a Claude Desktop: vegeu docs/PROJECTE_CLAUDE.md.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(Path(__file__).resolve().parent.parent)

from mcp.server.mcpserver import MCPServer  # noqa: E402

from quadre.nucli.models import esquema_json  # noqa: E402
from quadre.nucli.numeros import json_per_fitxa, llegeix_json  # noqa: E402
from quadre.nucli.validacio import valida  # noqa: E402

mcp = MCPServer(
    "finances-torre",
    instructions=(
        "Quadre de comandament financer de l'Ajuntament de la Torre de l'Espanyol. "
        "En acabar o actualitzar un expedient econòmic (liquidació, pressupost, modificació de crèdit, PEF, "
        "operació de crèdit, tresoreria, PMP, control intern, compte general) o una tramesa d'informació, "
        "crida `esquema_fitxa`, construeix la fitxa amb xifres llegides de fonts (mai inventades; els desconeguts "
        "com a null + pendents) i crida `registrar_fitxa`. Si retorna errors, corregeix i torna-hi."
    ),
)


def _repo():
    from quadre.nucli.repositori import Repositori
    return Repositori()


def _normalitza(fitxa: dict | str) -> dict:
    """Reparseja amb Decimal perquè cap import passi per float."""
    text = fitxa if isinstance(fitxa, str) else json.dumps(fitxa, ensure_ascii=False)
    return llegeix_json(text)


@mcp.tool()
def esquema_fitxa() -> str:
    """Retorna el JSON Schema de la fitxa `torre-finances/expedient@1` i les convencions obligatòries."""
    conv = (
        "CONVENCIONS: imports amb punt decimal i 2 decimals, sense milers (1496005.42); percentatges en tant per cent "
        "(21.2914); dates ISO (2026-09-24); desconegut = null + entrada a `pendents`; calculat = nom del camp a "
        "`calculats` del bloc; `font_ref` amb fitxer/full/cel·la o document; `aprovat` només amb resolucio.num i data; "
        "entitat.nif = P4315400D; `dades` segueix `dades_per_tipus[tipus]`; no hi posis noms de persones físiques.\n\n"
    )
    return conv + json.dumps(esquema_json(), ensure_ascii=False)


@mcp.tool()
def validar_fitxa(fitxa: dict) -> dict:
    """Valida una fitxa (5 nivells) sense desar-la. Retorna errors, avisos i informació."""
    return valida(_normalitza(fitxa), repo=_repo()).com_dict()


@mcp.tool()
def registrar_fitxa(fitxa: dict) -> dict:
    """Valida la fitxa i, si és vàlida, la desa a la safata d'entrada del quadre (no l'importa a la BD).

    Retorna {valida, errors, avisos, fitxer}. Si `valida` és false, corregeix els errors i torna-la a enviar.
    """
    f = _normalitza(fitxa)
    repo = _repo()
    inf = valida(f, repo=repo)
    res = inf.com_dict()
    if not inf.es_valida:
        return res
    exp = f["expedient"]
    clau = (exp.get("num") or f"{f['tipus']}-{exp['exercici']}").replace("/", "-")
    nom = f"{exp['exercici']}_{f['tipus']}_{clau}_{datetime.now():%Y%m%d-%H%M%S}.json"
    desti = repo.cfg.safata_entrada / nom
    desti.parent.mkdir(parents=True, exist_ok=True)
    f.setdefault("font", {}).setdefault("origen", "mcp")
    desti.write_text(json_per_fitxa(f), encoding="utf-8")
    res["fitxer"] = str(desti)
    res["seguent_pas"] = "L'usuari l'ha d'importar: python -m quadre importa"
    return res


@mcp.tool()
def consultar_magnitud(codi: str, exercici: int) -> dict:
    """Valor vigent d'una magnitud (p. ex. 'RT.RTDG_AJ', 2025) amb qualitat (definitiu/provisional) i expedient d'origen.

    Codis: vegeu cataleg/magnituds.yaml (LIQ.*, RT.*, RD.*, EN.*, DEU.*, EST.CF, TES.PMP…).
    """
    f = _repo().fet_vigent(codi, exercici)
    if not f:
        return {"codi": codi, "exercici": exercici, "valor": None, "nota": "Sense dada registrada"}
    return {"codi": codi, "exercici": exercici, "valor": str(f["valor"]), "qualitat": f["qualitat"],
            "expedient": f["clau_expedient"], "font_ref": f["font_ref"], "calculat": bool(f["calculat"])}


@mcp.tool()
def estat_financer() -> dict:
    """Regles fiscals del darrer exercici liquidat, alertes i discrepàncies obertes."""
    from quadre.nucli import regles
    from quadre.remissio import calendari
    repo = _repo()
    exs = repo.exercicis()
    ex = max(exs) if exs else None
    return {
        "exercici": ex,
        "regles": [{"regla": r.nom, "valor": r.text_valor, "estat": r.estat, "resum": r.frase,
                    "provisional": r.provisional} for r in (regles.regles_fiscals(repo, ex) if ex else [])],
        "alertes": [{"severitat": a.severitat, "titol": a.titol, "detall": a.detall}
                    for a in regles.alertes(repo, calendari.genera(repo)) if a.severitat != "info"],
    }


@mcp.tool()
def obligacions_remissio(nomes_pendents: bool = True) -> list[dict]:
    """Calendari d'obligacions de remissió (Ministeri, Generalitat, Sindicatura, IGAE) amb estat i venciment."""
    from quadre.remissio import calendari
    out = []
    for v in calendari.genera(_repo()):
        if nomes_pendents and v.estat in ("complerta", "complerta_fora_termini", "no_escau", "futura"):
            continue
        out.append({"codi": v.codi, "obligacio": v.nom, "periode": v.periode, "titol": v.titol,
                    "venciment": v.venciment.isoformat() if v.venciment else None, "estat": v.etiqueta,
                    "organisme": v.organisme, "canal": v.canal, "fonament": v.fonament})
    return out


if __name__ == "__main__":
    mcp.run()
