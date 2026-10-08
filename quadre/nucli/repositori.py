"""Accés a SQLite: importació transaccional, versions, precedència de fonts i discrepàncies."""
from __future__ import annotations

import getpass
import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from quadre.config import Config, carrega
from quadre.nucli.cataleg import magnituds, ruta
from quadre.nucli.magnituds import fets_de_fitxa
from quadre.nucli.models import ESTATS_APROVATS
from quadre.nucli.numeros import TOLERANCIA, a_cent, canonic, de_cent, json_canonic, json_per_fitxa
from quadre.nucli.validacio import Informe, valida

RANG_EXTRACTOR, RANG_APROVAT, RANG_XAT, RANG_MANUAL = 1, 2, 3, 4


def ara() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def hash_fitxa(fitxa: dict) -> str:
    copia = json.loads(json_per_fitxa(fitxa), parse_float=Decimal)
    copia.get("font", {}).pop("generat_el", None)
    copia.get("font", {}).pop("sessio", None)
    return hashlib.sha256(json_canonic(copia).encode("utf-8")).hexdigest()


def _aplana(d, prefix="") -> dict:
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_aplana(v, f"{prefix}{k}."))
    elif isinstance(d, list):
        out[prefix[:-1]] = json.dumps(json.loads(json_per_fitxa(d)), ensure_ascii=False, sort_keys=True)
    else:
        out[prefix[:-1]] = d
    return out


def diff(abans: dict, despres: dict) -> list[str]:
    a, b = _aplana(abans), _aplana(despres)
    canvis = []
    for k in sorted(set(a) | set(b)):
        if k.startswith("font.") or k in ("font",):
            continue
        va, vb = a.get(k), b.get(k)
        if isinstance(va, Decimal) and isinstance(vb, Decimal) and va == vb:
            continue
        if va != vb:
            canvis.append(f"{k}: {va if va is not None else 'null'} → {vb if vb is not None else 'null'}")
    return canvis


@dataclass
class ResultatImportacio:
    estat: str  # 'importada' | 'duplicada' | 'rebutjada'
    informe: Informe
    clau_expedient: str | None = None
    versio: int | None = None
    fitxa_id: int | None = None
    canvis: list[str] | None = None
    ruta_registre: Path | None = None


class Repositori:
    def __init__(self, cfg: Config | None = None, bd: Path | None = None):
        self.cfg = cfg or carrega()
        self.ruta_bd = bd or self.cfg.bd
        self.ruta_bd.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.ruta_bd)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.execute("PRAGMA journal_mode = WAL")
        self._migra()
        self._entitat_id = self._assegura_entitat()
        self._sincronitza_cataleg()

    # ── infraestructura
    def _migra(self):
        versio = self.con.execute("PRAGMA user_version").fetchone()[0]
        for f in sorted(self.cfg.migracions.glob("*.sql")):
            n = int(f.name.split("_")[0])
            if n > versio:
                self.con.executescript(f.read_text(encoding="utf-8"))
                self.con.execute(f"PRAGMA user_version = {n}")
                self.con.commit()

    def _assegura_entitat(self) -> int:
        e = self.cfg.entitat
        self.con.execute("INSERT OR IGNORE INTO entitat (nif, nom, poblacio, tutela) VALUES (?,?,?,?)",
                         (e.nif, e.nom, e.poblacio, e.tutela))
        self.con.commit()
        return self.con.execute("SELECT id FROM entitat WHERE nif=?", (e.nif,)).fetchone()[0]

    def _sincronitza_cataleg(self):
        with self.con:
            for codi, m in magnituds().items():
                self.con.execute(
                    "INSERT INTO cat_magnitud (codi, nom, unitat, grup, fonament) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(codi) DO UPDATE SET nom=excluded.nom, unitat=excluded.unitat, "
                    "grup=excluded.grup, fonament=excluded.fonament",
                    (codi, m["nom"], m["unitat"], m["grup"], m.get("fonament")))

    def tanca(self):
        self.con.close()

    def audita(self, accio: str, objecte: str, detall: str = ""):
        try:
            usuari = getpass.getuser()
        except Exception:  # pragma: no cover
            usuari = "desconegut"
        self.con.execute("INSERT INTO registre_auditoria (moment, usuari, accio, objecte, detall) VALUES (?,?,?,?,?)",
                         (ara(), usuari, accio, objecte, detall))

    # ── consultes
    @staticmethod
    def _valor(fila) -> Decimal:
        return de_cent(fila["valor_cent"]) if fila["valor_cent"] is not None else Decimal(fila["valor_dec"])

    def fet_vigent(self, codi: str, exercici: int, data_referencia: str | None = None) -> dict | None:
        sql = ("SELECT f.*, e.clau AS clau_expedient FROM fet f LEFT JOIN expedient e ON e.id = f.expedient_id "
               "WHERE f.codi=? AND f.exercici=? AND f.substituit_el IS NULL "
               "AND f.qualitat IN ('definitiu','provisional')")
        args: list = [codi, exercici]
        if data_referencia:
            sql += " AND f.data_referencia=?"
            args.append(data_referencia)
        sql += " ORDER BY f.data_referencia DESC LIMIT 1"
        fila = self.con.execute(sql, args).fetchone()
        if not fila:
            return None
        d = dict(fila)
        d["valor"] = self._valor(fila)
        return d

    def valor(self, codi: str, exercici: int) -> Decimal | None:
        f = self.fet_vigent(codi, exercici)
        return f["valor"] if f else None

    def serie(self, codi: str) -> list[dict]:
        files = self.con.execute(
            "SELECT * FROM fet WHERE codi=? AND substituit_el IS NULL AND qualitat IN ('definitiu','provisional') "
            "ORDER BY data_referencia", (codi,)).fetchall()
        return [{**dict(f), "valor": self._valor(f)} for f in files]

    def exercicis(self) -> list[int]:
        return [r[0] for r in self.con.execute(
            "SELECT DISTINCT exercici FROM fet WHERE substituit_el IS NULL AND codi LIKE 'LIQ.%' ORDER BY exercici")]

    def expedients(self) -> list[dict]:
        return [dict(r) for r in self.con.execute("SELECT * FROM expedient ORDER BY exercici DESC, tipus, clau")]

    def fitxa_vigent(self, clau: str) -> dict | None:
        fila = self.con.execute(
            "SELECT fx.cos_json FROM expedient e JOIN expedient_versio v ON v.expedient_id=e.id "
            "AND v.versio=e.versio_vigent JOIN fitxa fx ON fx.id=v.fitxa_id WHERE e.clau=?", (clau,)).fetchone()
        return json.loads(fila[0], parse_float=Decimal) if fila else None

    def fitxes_vigents(self, tipus: str) -> list[dict]:
        files = self.con.execute(
            "SELECT fx.cos_json FROM expedient e JOIN expedient_versio v ON v.expedient_id=e.id "
            "AND v.versio=e.versio_vigent JOIN fitxa fx ON fx.id=v.fitxa_id WHERE e.tipus=? "
            "ORDER BY e.exercici", (tipus,)).fetchall()
        return [json.loads(f[0], parse_float=Decimal) for f in files]

    def versions(self, clau: str) -> list[dict]:
        return [dict(r) for r in self.con.execute(
            "SELECT v.* FROM expedient_versio v JOIN expedient e ON e.id=v.expedient_id WHERE e.clau=? "
            "ORDER BY v.versio", (clau,))]

    def discrepancies(self, nomes_obertes: bool = True) -> list[dict]:
        sql = ("SELECT d.*, e.clau AS clau_expedient FROM discrepancia d "
               "LEFT JOIN expedient e ON e.id=d.expedient_id")
        if nomes_obertes:
            sql += " WHERE d.estat='oberta'"
        return [{**dict(r), "valors": json.loads(r["valors_json"])} for r in self.con.execute(sql + " ORDER BY d.id")]

    def resol_discrepancia(self, ident: int, estat: str, resolucio: str):
        with self.con:
            self.con.execute("UPDATE discrepancia SET estat=?, resolucio=?, tancada_el=? WHERE id=?",
                             (estat, resolucio, ara(), ident))
            self.audita("resol_discrepancia", str(ident), f"{estat}: {resolucio}")

    def compliments(self) -> dict[tuple[str, str], dict]:
        return {(r["obligacio"], r["periode"]): dict(r) for r in self.con.execute("SELECT * FROM compliment")}

    def operacions(self) -> list[dict]:
        return [{**dict(r), "import": de_cent(r["import_cent"])} for r in self.con.execute(
            "SELECT o.*, e.clau, e.estat_tramit, e.titol FROM operacio_credit o JOIN expedient e ON e.id=o.expedient_id")]

    # ── importació
    def importa(self, fitxa_dict: dict, fitxer_origen: str | None = None) -> ResultatImportacio:
        informe = valida(fitxa_dict, repo=self)
        if not informe.es_valida:
            return ResultatImportacio("rebutjada", informe)
        fitxa, dades = informe.fitxa, informe.dades
        sha = hash_fitxa(fitxa_dict)
        if self.con.execute("SELECT 1 FROM fitxa WHERE sha256=?", (sha,)).fetchone():
            return ResultatImportacio("duplicada", informe, fitxa.clau_expedient())

        exp = fitxa.expedient
        aprovat = exp.estat_tramit in ESTATS_APROVATS
        origen = fitxa.font.origen
        rang = RANG_EXTRACTOR if origen == "extractor" else RANG_APROVAT if aprovat else \
            RANG_MANUAL if origen == "manual" else RANG_XAT
        qualitat = "definitiu" if aprovat else "provisional"
        clau = fitxa.clau_expedient()
        moment = ara()
        cos = json_per_fitxa(fitxa_dict)

        with self.con:
            cur = self.con.execute(
                "INSERT INTO fitxa (sha256, esquema, tipus, clau_expedient, exercici, origen, rang_font, fitxer_origen,"
                " cos_json, informe_validacio, rebuda_el) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (sha, "torre-finances/expedient@1", fitxa.tipus, clau, exp.exercici, origen, rang, fitxer_origen,
                 cos, json.dumps(informe.com_dict(), ensure_ascii=False), moment))
            fitxa_id = cur.lastrowid

            anterior = self.con.execute("SELECT * FROM expedient WHERE clau=?", (clau,)).fetchone()
            canvis: list[str] = []
            if anterior:
                versio = anterior["versio_vigent"] + 1
                exp_id = anterior["id"]
                previ = self.fitxa_vigent(clau)
                canvis = diff(previ, json.loads(cos, parse_float=Decimal)) if previ else []
                self.con.execute(
                    "UPDATE expedient SET titol=?, estat_tramit=?, organ=?, resolucio_num=?, resolucio_data=?, "
                    "versio_vigent=?, actualitzat_el=?, num_expedient=? WHERE id=?",
                    (exp.titol, exp.estat_tramit, exp.organ, exp.resolucio.num,
                     exp.resolucio.data.isoformat() if exp.resolucio.data else None, versio, moment, exp.num, exp_id))
            else:
                versio = 1
                exp_id = self.con.execute(
                    "INSERT INTO expedient (entitat_id, clau, num_expedient, tipus, exercici, titol, estat_tramit, organ,"
                    " resolucio_num, resolucio_data, versio_vigent, actualitzat_el) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (self._entitat_id, clau, exp.num, fitxa.tipus, exp.exercici, exp.titol, exp.estat_tramit, exp.organ,
                     exp.resolucio.num, exp.resolucio.data.isoformat() if exp.resolucio.data else None, 1, moment)
                ).lastrowid
            self.con.execute("INSERT INTO expedient_versio VALUES (?,?,?,?,?)",
                             (exp_id, versio, fitxa_id, moment, "\n".join(canvis) or None))

            self._desa_fets(fitxa, dades, fitxa_id, exp_id, rang, qualitat, moment)
            self._desa_incoherencies(fitxa, exp_id, fitxa_id, moment)
            self._desa_detall(fitxa, dades, exp_id, fitxa_id, moment)
            self.audita("importa", clau, f"v{versio} · {sha[:12]} · {fitxer_origen or ''}")

        ruta_reg = self._arxiva(fitxa, cos, clau, versio, sha, informe, canvis)
        return ResultatImportacio("importada", informe, clau, versio, fitxa_id, canvis, ruta_reg)

    def _desa_fets(self, fitxa, dades, fitxa_id, exp_id, rang, qualitat, moment):
        cat = magnituds()
        for f in fets_de_fitxa(fitxa.tipus, fitxa.expedient.exercici, dades):
            eur_ = cat[f.codi]["unitat"] == "eur"
            vcent, vdec = (a_cent(f.valor), None) if eur_ else (None, canonic(f.valor))
            vig = self.con.execute(
                "SELECT * FROM fet WHERE entitat_id=? AND exercici=? AND codi=? AND data_referencia=? "
                "AND substituit_el IS NULL AND qualitat IN ('definitiu','provisional')",
                (self._entitat_id, f.exercici, f.codi, f.data_referencia)).fetchone()
            if vig:
                igual = abs(self._valor(vig) - f.valor) <= (TOLERANCIA if eur_ else Decimal(0))
                mateix_exp = vig["expedient_id"] == exp_id
                if not mateix_exp and igual:
                    continue  # mateixa xifra confirmada per una altra font: no cal un fet nou
                if not mateix_exp and rang > vig["rang_font"]:
                    self._discrepancia_creuada(f, vig, exp_id, fitxa_id, moment, "oberta")
                    continue
                if not mateix_exp:
                    self._discrepancia_creuada(f, vig, exp_id, fitxa_id, moment, "resolta_per_precedencia")
                if mateix_exp and igual and vig["qualitat"] == qualitat and vig["rang_font"] == rang:
                    continue
            if vig:
                self.con.execute("UPDATE fet SET substituit_el=? WHERE id=?", (moment, vig["id"]))
            nou_id = self.con.execute(
                "INSERT INTO fet (entitat_id, exercici, codi, data_referencia, valor_cent, valor_dec, qualitat, calculat,"
                " rang_font, fitxa_id, expedient_id, font_ref, registrat_el) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (self._entitat_id, f.exercici, f.codi, f.data_referencia, vcent, vdec, qualitat, int(f.calculat), rang,
                 fitxa_id, exp_id, f.font_ref, moment)).lastrowid
            if vig:
                self.con.execute("UPDATE fet SET substituit_per=? WHERE id=?", (nou_id, vig["id"]))

    def _discrepancia_creuada(self, f, vig, exp_id, fitxa_id, moment, estat):
        valors = {"vigent": canonic(self._valor(vig)), "nou": canonic(f.valor)}
        nom = magnituds()[f.codi]["nom"]
        self.con.execute(
            "INSERT INTO discrepancia (codi, exercici, descripcio, valors_json, origen, expedient_id, fitxa_id, estat,"
            " resolucio, oberta_el, tancada_el) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (f.codi, f.exercici, f"{nom}: valors diferents entre expedients", json.dumps(valors),
             "creuada" if estat == "oberta" else "precedencia", exp_id, fitxa_id, estat,
             None if estat == "oberta" else "Preval la font de rang superior", moment,
             None if estat == "oberta" else moment))

    def _desa_incoherencies(self, fitxa, exp_id, fitxa_id, moment):
        # Les incoherències declarades en versions anteriors i no repetides es consideren resoltes.
        declarades = {i.descripcio for i in fitxa.incoherencies}
        for d in self.con.execute("SELECT id, descripcio FROM discrepancia WHERE expedient_id=? AND origen='declarada' "
                                  "AND estat='oberta'", (exp_id,)).fetchall():
            if d["descripcio"] not in declarades:
                self.con.execute("UPDATE discrepancia SET estat='resolta_nova_versio', tancada_el=?, "
                                 "resolucio='No es repeteix a la versió nova de la fitxa' WHERE id=?", (moment, d["id"]))
        cami_a_codi = {m.get("cami"): c for c, m in magnituds().items() if m.get("cami")}
        for inc in fitxa.incoherencies:
            ja = self.con.execute("SELECT 1 FROM discrepancia WHERE expedient_id=? AND origen='declarada' AND estat='oberta'"
                                  " AND descripcio=?", (exp_id, inc.descripcio)).fetchone()
            if ja:
                continue
            valors = {k: (canonic(v) if isinstance(v, Decimal) else v) for k, v in inc.valors.items()}
            self.con.execute(
                "INSERT INTO discrepancia (codi, camp, exercici, descripcio, valors_json, origen, expedient_id, fitxa_id,"
                " estat, oberta_el) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (cami_a_codi.get(inc.camp), inc.camp, fitxa.expedient.exercici, inc.descripcio,
                 json.dumps(valors, ensure_ascii=False), "declarada", exp_id, fitxa_id, "oberta", moment))

    def _desa_detall(self, fitxa, dades, exp_id, fitxa_id, moment):
        if fitxa.tipus == "operacio_credit":
            fz = dades.get("formalitzacio") or {}
            estat = "formalitzada" if fz.get("data") else "cancel·lada" if fitxa.expedient.estat_tramit == "anullat" \
                else "projectada"
            ctm = ruta(dades, "prudencia.cost_total_maxim.total_pct")
            self.con.execute(
                "INSERT INTO operacio_credit (expedient_id, classe, import_cent, termini_mesos, ratio_pct,"
                " cost_total_maxim_pct, entitat_financera, data_formalitzacio, data_venciment, tae_pct, estat)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(expedient_id) DO UPDATE SET classe=excluded.classe,"
                " import_cent=excluded.import_cent, termini_mesos=excluded.termini_mesos, ratio_pct=excluded.ratio_pct,"
                " cost_total_maxim_pct=excluded.cost_total_maxim_pct, entitat_financera=excluded.entitat_financera,"
                " data_formalitzacio=excluded.data_formalitzacio, data_venciment=excluded.data_venciment,"
                " tae_pct=excluded.tae_pct, estat=excluded.estat",
                (exp_id, dades["classe"], a_cent(dades["import"]), dades["termini_mesos"],
                 canonic(dades["ratio_pct"]) if dades.get("ratio_pct") is not None else None,
                 canonic(ctm) if ctm is not None else None, fz.get("entitat"),
                 fz["data"].isoformat() if fz.get("data") else None,
                 fz["venciment"].isoformat() if fz.get("venciment") else None,
                 canonic(fz["tae_pct"]) if fz.get("tae_pct") is not None else None, estat))
        elif fitxa.tipus == "tramesa":
            self.con.execute(
                "INSERT INTO compliment (obligacio, periode, estat, data_tramesa, justificant, observacions, fitxa_id,"
                " registrat_el) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(obligacio, periode) DO UPDATE SET"
                " estat=excluded.estat, data_tramesa=excluded.data_tramesa, justificant=excluded.justificant,"
                " observacions=excluded.observacions, fitxa_id=excluded.fitxa_id, registrat_el=excluded.registrat_el",
                (dades["obligacio"], dades["periode"], dades["estat"],
                 dades["data_tramesa"].isoformat() if dades.get("data_tramesa") else None,
                 dades.get("justificant"), dades.get("observacions"), fitxa_id, moment))

    def _arxiva(self, fitxa, cos, clau, versio, sha, informe, canvis) -> Path:
        """Deixa constància a disc: registre/<exercici>/<tipus>/<clau>/vN_<hash>.json + FITXA.md."""
        carpeta = self.cfg.registre / str(fitxa.expedient.exercici) / fitxa.tipus / clau
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta_json = carpeta / f"v{versio:02d}_{sha[:10]}.json"
        ruta_json.write_text(cos, encoding="utf-8")
        from quadre.sortida.fitxa_md import resum_markdown
        (carpeta / "FITXA.md").write_text(
            resum_markdown(self, clau, informe, canvis), encoding="utf-8")
        return ruta_json

    # ── còpia de seguretat
    def copia_seguretat(self, desti: Path) -> Path:
        desti.mkdir(parents=True, exist_ok=True)
        fitxer = desti / f"finances_{datetime.now():%Y%m%d_%H%M%S}.db"
        dst = sqlite3.connect(fitxer)
        with dst:
            self.con.backup(dst)
        dst.close()
        return fitxer


def mou_a(fitxer: Path, carpeta: Path) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    desti = carpeta / fitxer.name
    if desti.exists():
        desti = carpeta / f"{fitxer.stem}_{datetime.now():%H%M%S}{fitxer.suffix}"
    shutil.move(str(fitxer), desti)
    return desti
