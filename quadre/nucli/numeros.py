"""Imports exactes: Decimal a Python, cèntims a la BD, format català a la sortida."""
from __future__ import annotations

import json
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

CENTIM = Decimal("0.01")
TOLERANCIA = Decimal("0.01")


def llegeix_json(text: str) -> Any:
    """Parseja JSON sense passar mai per float."""
    return json.loads(text, parse_float=Decimal)


def llegeix_fitxer(ruta: Path) -> Any:
    return llegeix_json(ruta.read_text(encoding="utf-8-sig"))


def a_cent(v: Decimal) -> int:
    return int((Decimal(v) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def de_cent(c: int | None) -> Decimal | None:
    return None if c is None else (Decimal(c) / 100).quantize(CENTIM)


def canonic(v: Decimal) -> str:
    """Representació única d'un decimal (1496005.4 i 1496005.40 donen el mateix)."""
    d = Decimal(v).normalize()
    s = format(d, "f")
    return "0" if s in ("-0", "") else s


def _agrupa(enter: str) -> str:
    grups = []
    while len(enter) > 3:
        grups.insert(0, enter[-3:])
        enter = enter[:-3]
    grups.insert(0, enter)
    return ".".join(grups)


def eur(v: Decimal | int | float | None, simbol: bool = True, decimals: int = 2) -> str:
    """1496005.42 -> '1.496.005,42 €'."""
    if v is None:
        return "—"
    d = Decimal(str(v)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    signe = "−" if d < 0 else ""
    enter, _, dec = format(abs(d), "f").partition(".")
    text = signe + _agrupa(enter) + ("," + dec if decimals else "")
    return text + (" €" if simbol else "")


def pct(v: Decimal | float | None, decimals: int = 2) -> str:
    if v is None:
        return "—"
    return eur(v, simbol=False, decimals=decimals) + " %"


_SENTINELLA = "§D§"  # «§D§»: marca temporal, mai no arriba al fitxer
_RE_SENTINELLA = re.compile('"' + _SENTINELLA + r'(-?[0-9.]+)"')


def json_per_fitxa(obj: Any) -> str:
    """Serialitza una fitxa amb els decimals com a números JSON exactes (mai float)."""

    def conv(o):
        if isinstance(o, Decimal):
            return _SENTINELLA + format(o, "f")
        if isinstance(o, dict):
            return {k: conv(v) for k, v in o.items()}
        if isinstance(o, list):
            return [conv(v) for v in o]
        return o

    text = json.dumps(conv(obj), ensure_ascii=False, indent=2)
    return _RE_SENTINELLA.sub(lambda m: m.group(1), text)


def json_canonic(obj: Any) -> str:
    """JSON canònic per al hash: claus ordenades, sense espais, decimals normalitzats."""

    def conv(o):
        if isinstance(o, Decimal):
            return {"$d": canonic(o)}
        if isinstance(o, float):
            return {"$d": canonic(Decimal(str(o)))}
        if isinstance(o, int) and not isinstance(o, bool):
            return {"$d": canonic(Decimal(o))}
        if isinstance(o, dict):
            return {k: conv(v) for k, v in o.items()}
        if isinstance(o, list):
            return [conv(v) for v in o]
        return o

    return json.dumps(conv(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
