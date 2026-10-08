"""Rutes i paràmetres de l'entitat.

Les rutes es poden sobreescriure amb `config.ini` a l'arrel del projecte
(vegeu `config.ini.example`). Tot el que és normatiu (llindars, taxes) viu a
`cataleg/parametres.yaml`, no aquí.
"""
from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path

ARREL = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Entitat:
    nif: str = "P4315400D"
    nom: str = "Ajuntament de la Torre de l'Espanyol"
    poblacio: int = 641
    # Model de cessió (arts. 111 i 135 TRLRHL): NO. Condiciona la periodicitat de moltes trameses.
    model_cessio: bool = False
    # Tutela financera: Generalitat de Catalunya (art. 218.5 EAC).
    tutela: str = "generalitat"


@dataclass(frozen=True)
class Config:
    entitat: Entitat = field(default_factory=Entitat)
    bd: Path = ARREL / "dades" / "finances.db"
    safata_entrada: Path = ARREL / "safata" / "entrada"
    safata_rebutjades: Path = ARREL / "safata" / "rebutjades"
    registre: Path = ARREL / "registre"
    sortida: Path = ARREL / "sortida"
    cataleg: Path = ARREL / "cataleg"
    migracions: Path = ARREL / "migracions"
    copies: tuple[Path, ...] = ()
    # Primer dia a partir del qual el calendari de remissió mostra venciments.
    remissio_des_de: str = "2026-01-01"


def carrega() -> Config:
    ini = ARREL / "config.ini"
    if not ini.exists():
        return Config()
    cp = configparser.ConfigParser()
    cp.read(ini, encoding="utf-8")
    kw: dict = {}
    if cp.has_option("rutes", "bd"):
        kw["bd"] = Path(cp.get("rutes", "bd"))
    if cp.has_option("rutes", "copies"):
        kw["copies"] = tuple(Path(p.strip()) for p in cp.get("rutes", "copies").split(";") if p.strip())
    if cp.has_option("remissio", "des_de"):
        kw["remissio_des_de"] = cp.get("remissio", "des_de")
    return Config(**kw)
