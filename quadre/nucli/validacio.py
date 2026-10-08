"""Validació en cinc nivells (docs/ARQUITECTURA.md §2.5).

1. Esquema (Pydantic)            → error
2. Identitats comptables         → error (o avís si falta un component)
3. Coherència creuada amb la BD  → avís (i discrepància en importar)
4. Plausibilitat                 → avís
5. Estat jurídic i normatiu      → error o avís

`valida()` no escriu res: només informa. La BD és opcional (sense BD, nivells 1, 2 i 5).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import ValidationError

from quadre.nucli import identitats
from quadre.nucli.cataleg import magnituds, obligacions
from quadre.nucli.identitats import Troballa
from quadre.nucli.magnituds import fets_de_fitxa
from quadre.nucli.models import MODELS_DADES, Fitxa
from quadre.nucli.numeros import TOLERANCIA, eur

if TYPE_CHECKING:
    from quadre.nucli.repositori import Repositori

# Magnituds que es comparen amb l'exercici anterior (nivell 4) i el llindar de variació.
PLAUSIBILITAT = {"LIQ.DRN": 50, "LIQ.ORN": 50, "EN.ING_CORRENTS": 30, "RT.RTDG": 60, "TES.PMP": 100}


@dataclass
class Informe:
    troballes: list[Troballa] = field(default_factory=list)
    fitxa: Fitxa | None = None
    dades: dict | None = None  # `dades` validades (dict amb Decimal i date)

    @property
    def errors(self) -> list[Troballa]:
        return [t for t in self.troballes if t.severitat == "error"]

    @property
    def avisos(self) -> list[Troballa]:
        return [t for t in self.troballes if t.severitat == "avis"]

    @property
    def es_valida(self) -> bool:
        return not self.errors

    def com_dict(self) -> dict:
        return {
            "valida": self.es_valida,
            "errors": [t.com_dict() for t in self.errors],
            "avisos": [t.com_dict() for t in self.avisos],
            "info": [t.com_dict() for t in self.troballes if t.severitat == "info"],
        }

    def text(self) -> str:
        if not self.troballes:
            return "✔ Fitxa vàlida, sense avisos."
        linies = ["✔ Fitxa vàlida." if self.es_valida else "✘ Fitxa NO vàlida."]
        for t in sorted(self.troballes, key=lambda t: ({"error": 0, "avis": 1, "info": 2}[t.severitat], t.nivell)):
            marca = {"error": "ERROR", "avis": "AVÍS ", "info": "info "}[t.severitat]
            linies.append(f"  [{marca}] nivell {t.nivell} · {t.codi}: {t.missatge}")
        return "\n".join(linies)


def _errors_pydantic(e: ValidationError, prefix: str = "") -> list[Troballa]:
    out = []
    for err in e.errors():
        loc = ".".join(str(x) for x in err["loc"])
        out.append(Troballa(1, "error", "ESQUEMA", f"{prefix}{loc}: {err['msg']}"))
    return out


def valida(fitxa_dict: dict, repo: "Repositori | None" = None) -> Informe:
    inf = Informe()

    # ── Nivell 1: esquema
    try:
        fitxa = Fitxa.model_validate(fitxa_dict)
    except ValidationError as e:
        inf.troballes += _errors_pydantic(e)
        return inf
    model_dades = MODELS_DADES[fitxa.tipus]
    try:
        dades_model = model_dades.model_validate(fitxa.dades)
    except ValidationError as e:
        inf.troballes += _errors_pydantic(e, prefix="dades.")
        return inf
    dades = dades_model.model_dump(by_alias=True, mode="python")
    inf.fitxa, inf.dades = fitxa, dades
    expedient = fitxa.expedient.model_dump(mode="python")

    if fitxa.tipus == "tramesa" and dades["obligacio"] not in obligacions():
        inf.troballes.append(Troballa(1, "error", "OBLIGACIO",
                                      f"L'obligació '{dades['obligacio']}' no existeix a cataleg/obligacions.yaml"))
    for bloc in dades.values():
        if isinstance(bloc, dict):
            for camp in bloc.get("calculats") or []:
                if camp not in bloc:
                    inf.troballes.append(Troballa(1, "error", "CALCULATS", f"`calculats` cita '{camp}', que no és al bloc"))

    # ── Nivells 2 i 5: identitats i estat jurídic
    inf.troballes += identitats.per_tipus(fitxa.tipus, dades, expedient)

    for inc in fitxa.incoherencies:
        valors = ", ".join(f"{k}: {v}" for k, v in inc.valors.items())
        inf.troballes.append(Troballa(3, "avis", "INCOHERENCIA_DECLARADA", f"{inc.descripcio} ({valors})"))
    if fitxa.pendents:
        inf.troballes.append(Troballa(5, "info", "PENDENTS",
                                      f"{len(fitxa.pendents)} camp(s) pendent(s): "
                                      + "; ".join(p.camp for p in fitxa.pendents)))

    # ── Nivells 3 i 4: contra la BD
    if repo is not None:
        clau = fitxa.clau_expedient()
        for f in fets_de_fitxa(fitxa.tipus, fitxa.expedient.exercici, dades):
            vigent = repo.fet_vigent(f.codi, f.exercici, f.data_referencia)
            if vigent and vigent["clau_expedient"] != clau and abs(vigent["valor"] - f.valor) > TOLERANCIA:
                nom = magnituds()[f.codi]["nom"]
                inf.troballes.append(Troballa(
                    3, "avis", "DISCREPANCIA",
                    f"{nom} {f.exercici}: aquesta fitxa diu {_fmt(f.codi, f.valor)}, però l'expedient "
                    f"{vigent['clau_expedient']} diu {_fmt(f.codi, vigent['valor'])}"))
            if f.codi in PLAUSIBILITAT:
                anterior = repo.fet_vigent(f.codi, f.exercici - 1, f"{f.exercici - 1}{f.data_referencia[4:]}")
                if anterior and anterior["valor"]:
                    var = (f.valor / anterior["valor"] - 1) * 100
                    if abs(var) > PLAUSIBILITAT[f.codi]:
                        inf.troballes.append(Troballa(
                            4, "avis", "PLAUSIBILITAT",
                            f"{magnituds()[f.codi]['nom']}: variació interanual {eur(var, simbol=False)} % "
                            f"({_fmt(f.codi, anterior['valor'])} → {_fmt(f.codi, f.valor)}). Justifica-la"))
        if fitxa.tipus == "operacio_credit" and dades.get("base_ratio"):
            b = dades["base_ratio"]
            vig = repo.fet_vigent("EN.ING_CORRENTS", b["exercici_base"], f"{b['exercici_base']}-12-31")
            if vig and abs(vig["valor"] - b["ingressos_corrents"]) > TOLERANCIA:
                inf.troballes.append(Troballa(
                    3, "avis", "DISCREPANCIA",
                    f"Base de la ràtio ({eur(b['ingressos_corrents'])}) ≠ ingressos corrents de la liquidació "
                    f"{b['exercici_base']} ({eur(vig['valor'])})"))
    return inf


def _fmt(codi: str, v: Decimal) -> str:
    unitat = magnituds()[codi]["unitat"]
    if unitat == "eur":
        return eur(v)
    if unitat == "pct":
        return eur(v, simbol=False) + " %"
    return eur(v, simbol=False) + (" dies" if unitat == "dies" else "")
