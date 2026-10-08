"""Proves amb els valors d'or 2024-2025 (docs/ARQUITECTURA.md §0.1). Cap prova toca la BD real."""
from __future__ import annotations

import copy
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from quadre.config import ARREL, Config, Entitat
from quadre.nucli.numeros import eur, llegeix_fitxer
from quadre.nucli.repositori import Repositori, hash_fitxa
from quadre.nucli.validacio import valida
from quadre.remissio import calendari

INICIALS = ARREL / "dades_inicials"


def fitxa(nom: str) -> dict:
    return llegeix_fitxer(INICIALS / nom)


@pytest.fixture
def repo(tmp_path: Path):
    cfg = Config(bd=tmp_path / "t.db", registre=tmp_path / "registre", safata_entrada=tmp_path / "entrada",
                 safata_rebutjades=tmp_path / "rebutjades", sortida=tmp_path / "sortida")
    r = Repositori(cfg)
    yield r
    r.tanca()


@pytest.fixture
def carregat(repo):
    for f in sorted(INICIALS.glob("*.json")):
        assert repo.importa(llegeix_fitxer(f), f.name).estat == "importada"
    return repo


# ── números
def test_format_catala():
    assert eur(Decimal("1496005.42")) == "1.496.005,42 €"
    assert eur(Decimal("-176245.38")) == "−176.245,38 €"


# ── identitats (nivell 2)
def test_liquidacio_2025_quadra():
    inf = valida(fitxa("02_liquidacio_2025.json"))
    assert inf.es_valida, inf.text()
    assert not [t for t in inf.troballes if t.nivell == 2 and t.severitat != "info"]


def test_romanent_2024_detecta_component_4():
    inf = valida(fitxa("01_liquidacio_2024.json"))
    assert inf.es_valida
    avis = [t for t in inf.avisos if t.codi == "RT_PARTIDES"]
    assert avis and "−13.432,78 €" in avis[0].missatge


def test_un_digit_erroni_es_rebutja():
    f = copy.deepcopy(fitxa("02_liquidacio_2025.json"))
    f["dades"]["romanent_tresoreria"]["rt_total"] = Decimal("1496050.42")
    inf = valida(f)
    assert not inf.es_valida
    assert any(t.codi == "RT" and "45,00 €" in t.missatge for t in inf.errors)


def test_camp_desconegut_es_rebutja():
    f = copy.deepcopy(fitxa("02_liquidacio_2025.json"))
    f["dades"]["romanent_tresoreria"]["rtdg_ajustad"] = Decimal("1")
    assert not valida(f).es_valida


def test_aprovat_sense_decret_es_rebutja():
    f = copy.deepcopy(fitxa("02_liquidacio_2025.json"))
    f["expedient"]["estat_tramit"] = "aprovat"
    assert not valida(f).es_valida


def test_polissa_i_pef_quadren():
    assert valida(fitxa("03_polissa_credit_2026.json")).es_valida
    inf = valida(fitxa("04_pef_2026_2027.json"))
    assert inf.es_valida and not [t for t in inf.errors]


def test_polissa_competencia_ple():
    f = copy.deepcopy(fitxa("03_polissa_credit_2026.json"))
    f["dades"]["competencia"] = "alcaldia"
    f["expedient"]["organ"] = "alcaldia"
    inf = valida(f)
    assert any(t.codi == "OC_COMPETENCIA" for t in inf.errors)


def test_tae_superior_al_cost_maxim():
    f = copy.deepcopy(fitxa("03_polissa_credit_2026.json"))
    f["dades"]["formalitzacio"] = {"data": "2026-10-15", "entitat": "CaixaBank", "tae_pct": Decimal("3.700")}
    assert any(t.codi == "OC_TAE" for t in valida(f).errors)


# ── importació, duplicats, versions i discrepàncies
def test_importacio_idempotent(carregat):
    for f in sorted(INICIALS.glob("*.json")):
        assert carregat.importa(llegeix_fitxer(f), f.name).estat == "duplicada"


def test_hash_ignora_data_generacio():
    a = fitxa("02_liquidacio_2025.json")
    b = copy.deepcopy(a)
    b["font"]["generat_el"] = "2030-01-01T00:00:00+01:00"
    assert hash_fitxa(a) == hash_fitxa(b)


def test_valors_vigents(carregat):
    assert carregat.valor("RT.RTDG", 2025) == Decimal("298549.92")
    assert carregat.valor("RD.MARGE", 2025) == Decimal("-176245.38")
    assert carregat.valor("TES.PMP", 2024) == Decimal("8.61")
    assert carregat.fet_vigent("RT.RTDG", 2025)["qualitat"] == "provisional"
    assert carregat.fet_vigent("RT.RTDG", 2024)["qualitat"] == "definitiu"


def test_discrepancia_418_oberta_i_es_tanca_amb_versio_nova(carregat):
    assert any("418" in d["descripcio"] for d in carregat.discrepancies())
    f = copy.deepcopy(fitxa("02_liquidacio_2025.json"))
    rt = f["dades"]["romanent_tresoreria"]
    rt["saldo_418"], rt["rtdg_ajustat"] = Decimal("215.82"), Decimal("293893.52")
    f["incoherencies"] = []
    f["pendents"] = [p for p in f["pendents"] if p["camp"] != "romanent_tresoreria.saldo_418"]
    r = carregat.importa(f, "v2.json")
    assert r.estat == "importada" and r.versio == 2
    assert any("saldo_418" in c for c in r.canvis)
    assert not any("418" in d["descripcio"] for d in carregat.discrepancies())
    assert carregat.valor("RT.RTDG_AJ", 2025) == Decimal("293893.52")
    antic = carregat.con.execute("SELECT COUNT(*) FROM fet WHERE codi='RT.RTDG_AJ' AND substituit_el IS NOT NULL").fetchone()[0]
    assert antic == 1  # el valor anterior es conserva (bitemporal)


def test_registre_immutable(carregat):
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError):
        carregat.con.execute("DELETE FROM fitxa")


def test_arxiu_a_carpetes(carregat):
    carpeta = carregat.cfg.registre / "2025" / "liquidacio" / "4315200000-2026-0000642"
    assert (carpeta / "FITXA.md").exists()
    assert list(carpeta.glob("v01_*.json"))


# ── remissió
def test_calendari_municipi_petit(carregat):
    vs = calendari.genera(carregat, avui=date(2026, 9, 24), des_de=date(2026, 1, 1), fins=date(2027, 2, 28))
    codis = {v.codi for v in vs}
    assert "MIN_TRIMESTRAL_PMP_TRESORERIA" in codis and "MIN_TRIMESTRAL_4T" in codis
    assert "MIN_TRIMESTRAL_COMPLET" not in codis  # art. 16.10 OM: ≤ 5.000 h
    lf = next(v for v in vs if v.codi == "MIN_LINIES_FONAMENTALS" and v.periode == "2027")
    assert lf.venciment == date(2026, 9, 14) and lf.estat == "vencuda"
    liq = next(v for v in vs if v.codi == "MIN_LIQUIDACIO" and v.periode == "2025")
    assert liq.venciment == date(2026, 3, 30)
    t3 = next(v for v in vs if v.codi == "MIN_TRIMESTRAL_PMP_TRESORERIA" and v.periode == "2026-T3")
    assert t3.venciment == date(2026, 10, 30)
    cg = next(v for v in vs if v.codi == "INT_CG_PLE" and v.periode == "2025")
    assert cg.venciment == date(2026, 9, 30) and cg.estat == "propera"


def test_municipi_gran_fa_trimestral_complet():
    vs = calendari.genera(None, entitat=Entitat(poblacio=20000), avui=date(2026, 9, 24),
                          des_de=date(2026, 1, 1), fins=date(2026, 12, 31))
    codis = {v.codi for v in vs}
    assert "MIN_TRIMESTRAL_COMPLET" in codis and "MIN_TRIMESTRAL_PMP_TRESORERIA" not in codis


def test_esdeveniments_polissa(carregat):
    vs = calendari.genera(carregat, avui=date(2026, 9, 24), des_de=date(2026, 1, 1), fins=date(2027, 12, 31))
    pend = [v for v in vs if v.codi == "GEN_OPERACIO_CURT"]
    assert pend and pend[0].estat == "esdeveniment_pendent"
    f = copy.deepcopy(fitxa("03_polissa_credit_2026.json"))
    f["dades"]["formalitzacio"] = {"data": "2026-10-20", "entitat": "CaixaBank", "tae_pct": Decimal("3.500"),
                                   "venciment": "2027-10-20"}
    assert carregat.importa(f).estat == "importada"
    vs = calendari.genera(carregat, avui=date(2026, 9, 24), des_de=date(2026, 1, 1), fins=date(2028, 12, 31))
    gen = next(v for v in vs if v.codi == "GEN_OPERACIO_CURT")
    assert gen.venciment == date(2026, 11, 10)
    cir = next(v for v in vs if v.codi == "MIN_OPERACIO_ENDEUTAMENT" and v.periode.endswith("formalitzacio_operacio"))
    assert cir.venciment == date(2026, 11, 20)


def test_marcar_tramesa(carregat):
    f = {"$fitxa": "torre-finances/expedient@1", "entitat": {"nif": "P4315400D"}, "tipus": "tramesa",
         "expedient": {"exercici": 2027, "titol": "Tramesa de prova", "estat_tramit": "executat"},
         "font": {"origen": "manual"},
         "dades": {"obligacio": "MIN_LINIES_FONAMENTALS", "periode": "2027", "data_tramesa": "2026-09-20"}}
    assert carregat.importa(f).estat == "importada"
    vs = calendari.genera(carregat, avui=date(2026, 9, 24), des_de=date(2026, 1, 1), fins=date(2026, 12, 31))
    lf = next(v for v in vs if v.codi == "MIN_LINIES_FONAMENTALS" and v.periode == "2027")
    assert lf.estat == "complerta_fora_termini"
