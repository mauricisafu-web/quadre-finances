"""Lectura dels catàlegs YAML (magnituds, paràmetres normatius, obligacions de remissió)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

from quadre.config import ARREL

DIR = ARREL / "cataleg"


def _llegeix(nom: str) -> dict:
    return yaml.safe_load((DIR / nom).read_text(encoding="utf-8")) or {}


@lru_cache
def magnituds() -> dict[str, dict]:
    return _llegeix("magnituds.yaml")


@lru_cache
def _parametres() -> dict[str, list[dict]]:
    return _llegeix("parametres.yaml")


def parametre(codi: str, a_data: date | None = None) -> Decimal | None:
    """Valor vigent d'un paràmetre normatiu a una data (per defecte, avui)."""
    a_data = a_data or date.today()
    vigents = [
        f for f in _parametres().get(codi, [])
        if f["des_de"] <= a_data and (f.get("fins") is None or a_data <= f["fins"])
    ]
    if not vigents:
        return None
    return Decimal(str(max(vigents, key=lambda f: f["des_de"])["valor"]))


def font_parametre(codi: str) -> str:
    files = _parametres().get(codi, [])
    return files[-1]["font"] if files else ""


@lru_cache
def obligacions() -> dict[str, dict]:
    return _llegeix("obligacions.yaml")


def ruta(obj, cami: str):
    """Segueix una ruta amb punts dins d'un dict (None si falta algun tram)."""
    for part in cami.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
    return obj


def arrel() -> Path:
    return ARREL
