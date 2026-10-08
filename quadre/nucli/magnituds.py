"""Converteix una fitxa validada en fets (magnitud, exercici, data de referència, valor)."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from quadre.nucli.cataleg import magnituds, ruta


@dataclass(frozen=True)
class Fet:
    codi: str
    exercici: int
    data_referencia: str
    valor: Decimal
    calculat: bool
    font_ref: str | None


def _fi_periode(periode: str) -> tuple[int, str]:
    any_, _, p = periode.partition("-")
    a = int(any_)
    if p.startswith("T"):
        mes = int(p[1]) * 3
    else:
        mes = int(p)
    return a, date(a, mes, calendar.monthrange(a, mes)[1]).isoformat()


def fets_de_fitxa(tipus: str, exercici: int, dades: dict) -> list[Fet]:
    fets: list[Fet] = []
    if tipus == "liquidacio":
        data_ref = f"{exercici}-12-31"
        for codi, m in magnituds().items():
            cami = m.get("cami")
            if not cami:
                continue
            valor = ruta(dades, cami)
            if valor is None:
                continue
            bloc, _, camp = cami.rpartition(".")
            bloc_dict = ruta(dades, bloc.split(".")[0]) or {}
            calculats = bloc_dict.get("calculats") or []
            fets.append(Fet(codi, exercici, data_ref, Decimal(valor), camp in calculats, bloc_dict.get("font_ref")))
    elif tipus == "pmp" and dades.get("pmp_dies") is not None:
        a, fi = _fi_periode(dades["periode"])
        fets.append(Fet("TES.PMP", a, fi, Decimal(dades["pmp_dies"]), False, dades.get("font_ref")))
    elif tipus == "tresoreria" and dades.get("fons_liquids") is not None:
        d = dades["data_tall"]
        d = d if isinstance(d, date) else date.fromisoformat(str(d))
        fets.append(Fet("TES.FONS_LIQUIDS", d.year, d.isoformat(), Decimal(dades["fons_liquids"]), False,
                        dades.get("font_ref")))
    return fets
