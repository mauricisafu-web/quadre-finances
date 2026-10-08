"""Models de la fitxa `torre-finances/expedient@1`.

Aquests models són la FONT ÚNICA de l'esquema: el JSON Schema que llegeix Claude
(skill i eina MCP) es genera d'aquí amb `python -m quadre esquema`.

Convencions (vegeu docs/ARQUITECTURA.md §1.3):
- Imports en euros amb 2 decimals, sense separador de milers (1496005.42).
- Percentatges en tant per cent (21.2914), fins a 4 decimals.
- Un valor desconegut és `null` + una entrada a `pendents`. Mai un zero inventat.
- Cada bloc admet `font_ref` (d'on surt la xifra) i `calculats` (camps calculats, no llegits).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Eur = Annotated[Decimal, Field(max_digits=15, decimal_places=2, description="Import en euros, 2 decimals")]
Pct = Annotated[Decimal, Field(max_digits=9, decimal_places=4, description="Tant per cent (21.2914 = 21,2914 %)")]
Dies = Annotated[Decimal, Field(max_digits=7, decimal_places=2)]

TIPUS = Literal[
    "liquidacio", "pressupost", "modificacio_credit", "pef", "operacio_credit",
    "tresoreria", "pmp", "control_intern", "compte_general", "tramesa",
]
EstatTramit = Literal[
    "esborrany", "en_tramit", "aprovat_inicial", "aprovat", "publicat", "executat", "arxivat", "anullat",
]
Organ = Literal["alcaldia", "ple", "junta_govern"]
ESTATS_APROVATS = ("aprovat", "publicat", "executat", "arxivat")


class Estricte(BaseModel):
    """Rebutja camps desconeguts: un camp mal escrit per Claude ha de fallar, no perdre's."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Bloc(Estricte):
    font_ref: str | None = Field(None, description="Fitxer + full + cel·la, o document + annex/pàgina")
    calculats: list[str] = Field(default_factory=list, description="Noms dels camps calculats (no llegits d'una font)")


# ───────────────────────────── Sobre comú ─────────────────────────────

class EntitatRef(Estricte):
    nif: Literal["P4315400D"]


class Resolucio(Estricte):
    num: str | None = None
    data: date | None = None
    organ: Organ | None = None


class Fita(Estricte):
    fita: str = Field(description="provisio_inici, informe_intervencio, acord_ple, publicacio_bop, tramesa_ministeri…")
    data: date | None = None
    estat: Literal["pendent", "fet", "no_escau"] = "pendent"
    document: str | None = None


class Expedient(Estricte):
    num: str | None = Field(None, pattern=r"^\d{10}-\d{4}-\d{7}$",
                            description="Número d'expedient del gestor (p. ex. 4315200000-2026-0000642). null si no en té")
    exercici: int = Field(ge=2000, le=2100)
    titol: str = Field(min_length=3)
    estat_tramit: EstatTramit
    organ: Organ | None = None
    resolucio: Resolucio = Field(default_factory=Resolucio)
    fites: list[Fita] = Field(default_factory=list)


class FitxerFont(Estricte):
    ruta: str
    sha256: str | None = None
    full: str | None = None


class Font(Estricte):
    origen: Literal["claude_code", "cowork", "claude_desktop", "claude_ai", "mcp", "extractor", "manual"]
    sessio: str | None = None
    generat_el: datetime | None = None
    fitxers: list[FitxerFont] = Field(default_factory=list)


class Pendent(Estricte):
    camp: str
    motiu: str


class Incoherencia(Estricte):
    descripcio: str
    camp: str | None = Field(None, description="Camp afectat, p. ex. romanent_tresoreria.saldo_418")
    valors: dict[str, Decimal | str | None] = Field(default_factory=dict)


class Fitxa(Estricte):
    fitxa: Literal["torre-finances/expedient@1"] = Field(alias="$fitxa")
    entitat: EntitatRef
    tipus: TIPUS
    expedient: Expedient
    font: Font
    dades: dict
    pendents: list[Pendent] = Field(default_factory=list)
    incoherencies: list[Incoherencia] = Field(default_factory=list)

    @model_validator(mode="after")
    def _aprovat_exigeix_resolucio(self):
        e = self.expedient
        if self.tipus != "tramesa" and e.estat_tramit in ESTATS_APROVATS and not (e.resolucio.num and e.resolucio.data):
            raise ValueError(
                f"estat_tramit='{e.estat_tramit}' exigeix resolucio.num i resolucio.data; "
                "si encara no en tens, fes servir 'en_tramit' i afegeix-ho a pendents"
            )
        return self

    def clau_expedient(self) -> str:
        if self.tipus == "tramesa":
            return f"tramesa-{self.dades.get('obligacio')}-{self.dades.get('periode')}"
        return self.expedient.num or f"{self.tipus}-{self.expedient.exercici}"


# ───────────────────────────── Liquidació ─────────────────────────────

class CapitolIngressos(Estricte):
    capitol: int = Field(ge=1, le=9)
    previsions_definitives: Eur | None = None
    drn: Eur | None = None
    recaptacio: Eur | None = None


class CapitolDespeses(Estricte):
    capitol: int = Field(ge=1, le=9)
    credits_definitius: Eur | None = None
    orn: Eur | None = None
    pagaments: Eur | None = None


class ExecucioIngressos(Bloc):
    previsions_inicials: Eur | None = None
    modificacions: Eur | None = None
    previsions_definitives: Eur | None = None
    drn: Eur | None = None
    recaptacio_neta: Eur | None = None
    pendent_cobrament: Eur | None = None
    per_capitol: list[CapitolIngressos] = Field(default_factory=list)


class ExecucioDespeses(Bloc):
    credits_inicials: Eur | None = None
    modificacions: Eur | None = None
    credits_definitius: Eur | None = None
    autoritzat: Eur | None = None
    compromes: Eur | None = None
    orn: Eur | None = None
    ordenat: Eur | None = None
    pagaments: Eur | None = None
    pendent_pagament: Eur | None = None
    per_capitol: list[CapitolDespeses] = Field(default_factory=list)


class DrnOrn(Estricte):
    drn: Eur | None = None
    orn: Eur | None = None


class ResultatPressupostari(Bloc):
    operacions_corrents: DrnOrn | None = None
    operacions_capital: DrnOrn | None = None
    actius_financers: DrnOrn | None = None
    passius_financers: DrnOrn | None = None
    rp: Eur | None = None
    ajust_despeses_rtdg: Eur | None = Field(None, description="Obligacions finançades amb RTDG (suma)")
    ajust_desviacions_negatives: Eur | None = Field(None, description="Desviacions de finançament negatives (suma)")
    ajust_desviacions_positives: Eur | None = Field(None, description="Desviacions de finançament positives (resta)")
    rp_ajustat: Eur | None = None


class RomanentTresoreria(Bloc):
    fons_liquids: Eur | None = None
    drets_pendents_total: Eur | None = None
    obligacions_pendents_total: Eur | None = None
    partides_pendents_aplicacio: Eur | None = Field(
        None, description="Component 4 de l'estat del romanent: cobraments pendents d'aplicació (−) i pagaments pendents d'aplicació (+)")
    rt_total: Eur | None = None
    saldos_dubtos_cobrament: Eur | None = None
    exces_financament_afectat: Eur | None = None
    rtdg: Eur | None = None
    saldo_413: Eur | None = None
    saldo_418: Eur | None = None
    rtdg_ajustat: Eur | None = None


class RomanentsCredit(Bloc):
    total: Eur | None = None
    incorporacio_obligatoria: Eur | None = None
    incorporacio_voluntaria: Eur | None = None
    no_incorporables: Eur | None = None


class AjustSec(Estricte):
    concepte: str
    import_: Eur = Field(alias="import")


class Estabilitat(Bloc):
    ingressos_no_financers: Eur | None = None
    despeses_no_financeres: Eur | None = None
    ajustos_sec: list[AjustSec] = Field(default_factory=list)
    capacitat_financament: Eur | None = Field(None, description="Positiu = capacitat; negatiu = necessitat")


class ReglaDespesa(Bloc):
    despesa_computable_n_1: Eur | None = None
    taxa_referencia: Pct | None = None
    limit_n: Eur | None = None
    augments_permanents: Eur | None = None
    disminucions_permanents: Eur | None = None
    despesa_computable_n: Eur | None = None
    marge: Eur | None = Field(None, description="limit_n − despesa_computable_n (negatiu = incompliment)")
    variacio_interanual_pct: Pct | None = Field(None, description="despesa_computable_n / despesa_computable_n_1 − 1")
    exces_sobre_limit_pct: Pct | None = Field(None, description="despesa_computable_n / limit_n − 1")
    compleix: bool | None = None


class EstalviNet(Bloc):
    ingressos_corrents: Eur | None = None
    ingressos_extraordinaris: Eur | None = None
    ingressos_corrents_ajustats: Eur | None = None
    despeses_corrents_1_2_4: Eur | None = None
    anualitat_teorica: Eur | None = None
    estalvi_net: Eur | None = None
    estalvi_net_ajustat: Eur | None = None


class Endeutament(Bloc):
    deute_viu_llarg: Eur | None = None
    deute_viu_curt: Eur | None = None
    deute_viu_total: Eur | None = None
    ratio_deute_viu_pct: Pct | None = None


class PmpBloc(Bloc):
    pmp_dies: Dies | None = None
    periode_referencia: str | None = None


class Bestreta(Estricte):
    codi: str
    import_: Eur = Field(alias="import")
    estat: str
    antiguitat_anys: int | None = None


class SaldoDepurar(Estricte):
    compte: str
    import_: Eur = Field(alias="import")
    nota: str | None = None


class ControlInternLiq(Bloc):
    objeccions: int | None = None
    omissions_fiscalitzacio: int | None = None
    anomalies_ingressos: int | None = None
    pagaments_justificar_pendents: int | None = None
    bestretes: list[Bestreta] = Field(default_factory=list)
    saldos_a_depurar: list[SaldoDepurar] = Field(default_factory=list)


class DestiSuperavit(Bloc):
    superavit_estabilitat: Eur | None = None
    rtdg_ajustat: Eur | None = None
    import_amortitzacio: Eur | None = None
    import_ifs: Eur | None = None
    import_413: Eur | None = None


class DadesLiquidacio(Estricte):
    execucio_ingressos: ExecucioIngressos | None = None
    execucio_despeses: ExecucioDespeses | None = None
    resultat_pressupostari: ResultatPressupostari | None = None
    romanent_tresoreria: RomanentTresoreria | None = None
    romanents_credit: RomanentsCredit | None = None
    estabilitat: Estabilitat | None = None
    regla_despesa: ReglaDespesa | None = None
    estalvi_net: EstalviNet | None = None
    endeutament: Endeutament | None = None
    pmp: PmpBloc | None = None
    control_intern: ControlInternLiq | None = None
    desti_superavit: DestiSuperavit | None = None


# ───────────────────────────── Operació de crèdit ─────────────────────────────

class TipusInteres(Estricte):
    modalitat: Literal["fix", "variable"]
    index: str | None = Field(None, description="EURIBOR_12M, EURIBOR_6M…")
    diferencial_pct: Pct | None = None
    tipus_fix_pct: Pct | None = None


class BaseRatio(Estricte):
    ingressos_corrents: Eur
    exercici_base: int


class CostTotalMaxim(Estricte):
    index: str | None = None
    diferencial_pct: Pct | None = None
    index_valor_pct: Pct | None = None
    data_index: date | None = None
    total_pct: Pct | None = None


class Prudencia(Estricte):
    resolucio: str | None = None
    elegible_fie: bool | None = None
    cost_total_maxim: CostTotalMaxim | None = None
    cost_total_maxim_si_regularitza: CostTotalMaxim | None = None


class Delegacio(Estricte):
    organ_delegat: Organ
    condicio: str | None = None
    data_acord_ple: date | None = None


class Oferta(Estricte):
    entitat: str
    data: date | None = None
    tipus_interes: TipusInteres | None = None
    tae_pct: Pct | None = None
    comissions: str | None = None


class Formalitzacio(Estricte):
    data: date | None = None
    entitat: str | None = None
    tae_pct: Pct | None = None
    venciment: date | None = None


class QuotaAmortitzacio(Estricte):
    data: date
    capital: Eur
    interessos: Eur
    capital_viu: Eur


class Comunicacio(Estricte):
    desti: str = Field(description="ministeri_art17_om, generalitat_ct_art5_ecf138, generalitat_art4_ecf138…")
    data: date | None = None
    justificant: str | None = None


class DadesOperacioCredit(Bloc):
    classe: Literal["tresoreria", "llarg_termini"]
    import_: Eur = Field(alias="import")
    termini_mesos: int = Field(ge=1, le=480)
    tipus_interes: TipusInteres | None = None
    amortitzacio: str | None = None
    liquidacio_interessos: str | None = None
    base_ratio: BaseRatio | None = None
    ratio_pct: Pct | None = None
    llindar_competencia_pct: Pct | None = None
    competencia: Organ | None = None
    fonament_competencia: str | None = None
    limit_art51_pct: Pct | None = None
    prudencia: Prudencia | None = None
    delegacio: Delegacio | None = None
    ofertes: list[Oferta] = Field(default_factory=list)
    formalitzacio: Formalitzacio = Field(default_factory=Formalitzacio)
    quadre_amortitzacio: list[QuotaAmortitzacio] = Field(default_factory=list)
    comunicacions: list[Comunicacio] = Field(default_factory=list)


# ───────────────────────────── PEF ─────────────────────────────

class Constatacio(Estricte):
    exercici_incompliment: int
    regles_incomplertes: list[Literal["estabilitat", "regla_despesa", "deute"]]
    data_constatacio: date | None = Field(None, description="Data d'aprovació de la liquidació que constata l'incompliment")


class Quantificacio(Estricte):
    exces: Eur | None = None
    deduccio_rtdg: Eur | None = None
    deduccio_exces_afectat: Eur | None = None
    import_a_corregir: Eur | None = None
    fonament_deduccio: str | None = None
    criteri_confirmat_tutela: bool | None = None


class AnyTrajectoria(Estricte):
    exercici: int
    capacitat_financament: Eur | None = None
    despesa_computable: Eur | None = None
    limit: Eur | None = None
    marge: Eur | None = None
    deute_viu_pct: Pct | None = None
    es_projeccio: bool = True


class Mesura(Estricte):
    codi: str
    descripcio: str
    tipus: Literal["ingressos", "despeses", "no_quantificada"]
    import_anual: Eur | None = None
    exercici: int | None = None
    indicador_seguiment: str | None = None


class TramitPef(Estricte):
    data_elaboracio: date | None = None
    data_ple: date | None = None
    data_comunicacio_ministeri: date | None = None
    data_comunicacio_generalitat: date | None = None
    data_publicacio: date | None = None


class DadesPef(Bloc):
    exercicis: list[int] = Field(description="Exercicis de vigència: l'any en curs i el següent (art. 21 LOEPSF)")
    causa: str | None = None
    constatacio: Constatacio
    quantificacio: Quantificacio | None = None
    trajectoria: list[AnyTrajectoria] = Field(default_factory=list)
    mesures: list[Mesura] = Field(default_factory=list)
    tramit: TramitPef = Field(default_factory=TramitPef)


# ───────────────────────────── Modificació de crèdit ─────────────────────────────

class LiniaMc(Estricte):
    sentit: Literal["alta", "baixa"]
    organica: str | None = None
    programa: str = Field(pattern=r"^\d{3,5}$")
    economica: str = Field(pattern=r"^\d{3,7}$")
    descripcio: str | None = None
    import_: Eur = Field(alias="import", gt=0)


class RecursMc(Estricte):
    tipus: Literal["rtdg", "rt_afectat", "nous_majors_ingressos", "baixes_anullacio", "operacio_credit",
                   "aportacio_compromis_ferm", "exces_financament_afectat"]
    concepte_ingressos: str | None = None
    import_: Eur = Field(alias="import", gt=0)


class ImpacteMc(Estricte):
    afecta_estabilitat: bool | None = None
    afecta_regla_despesa: bool | None = None
    informe_estabilitat: Literal["compleix", "incompliment_previst", "no_escau"] | None = None


class DadesModificacioCredit(Bloc):
    modalitat: Literal["credit_extraordinari", "suplement", "ampliacio", "transferencia", "generacio",
                       "incorporacio", "baixa_anullacio"]
    num_modificacio: str | None = None
    linies: list[LiniaMc]
    recursos: list[RecursMc] = Field(default_factory=list)
    impacte: ImpacteMc | None = None


# ───────────────────────────── Tresoreria, PMP, altres ─────────────────────────────

class SaldoCompte(Estricte):
    compte: str
    entitat_financera: str | None = None
    import_: Eur = Field(alias="import")


class DadesTresoreria(Bloc):
    data_tall: date
    saldos: list[SaldoCompte] = Field(default_factory=list)
    fons_liquids: Eur | None = None


class DadesPmp(Bloc):
    periode: str = Field(pattern=r"^\d{4}-(T[1-4]|\d{2})$", description="2026-T2 (trimestral) o 2026-05 (mensual)")
    ratio_operacions_pagades: Dies | None = None
    import_pagat: Eur | None = None
    ratio_operacions_pendents: Dies | None = None
    import_pendent: Eur | None = None
    pmp_dies: Dies | None = None


class DadesPressupost(Bloc):
    situacio: Literal["aprovat", "prorrogat", "en_elaboracio"]
    total_ingressos: Eur | None = None
    total_despeses: Eur | None = None
    data_aprovacio_inicial: date | None = None
    data_aprovacio_definitiva: date | None = None
    data_publicacio_bop: date | None = None


class InformeControl(Estricte):
    tipus: Literal["fiscalitzacio_previa", "control_financer", "informe_resum", "omissio", "objeccio"]
    num: str | None = None
    data: date | None = None
    resultat: str | None = None
    efecte_suspensiu: bool | None = None
    resolucio_discrepancia: str | None = None


class DadesControlIntern(Bloc):
    informes: list[InformeControl] = Field(default_factory=list)


class DadesCompteGeneral(Bloc):
    data_formacio: date | None = None
    data_comissio_especial: date | None = None
    data_exposicio_publica: date | None = None
    data_ple: date | None = None
    data_rendicio_sindicatura: date | None = None


class DadesTramesa(Estricte):
    obligacio: str = Field(description="Codi del catàleg cataleg/obligacions.yaml (p. ex. MIN_LIQUIDACIO)")
    periode: str = Field(description="Període al qual es refereix: '2025', '2026-T3', o la clau de l'esdeveniment")
    estat: Literal["tramesa", "no_escau"] = "tramesa"
    data_tramesa: date | None = None
    justificant: str | None = None
    observacions: str | None = None

    @model_validator(mode="after")
    def _data_si_tramesa(self):
        if self.estat == "tramesa" and self.data_tramesa is None:
            raise ValueError("Una tramesa feta ha de tenir data_tramesa")
        return self


MODELS_DADES: dict[str, type[BaseModel]] = {
    "liquidacio": DadesLiquidacio,
    "operacio_credit": DadesOperacioCredit,
    "pef": DadesPef,
    "modificacio_credit": DadesModificacioCredit,
    "tresoreria": DadesTresoreria,
    "pmp": DadesPmp,
    "pressupost": DadesPressupost,
    "control_intern": DadesControlIntern,
    "compte_general": DadesCompteGeneral,
    "tramesa": DadesTramesa,
}


def esquema_json() -> dict:
    """JSON Schema complet: sobre + `dades` per tipus (a `$defs.dades_per_tipus`)."""
    base = Fitxa.model_json_schema(by_alias=True)
    base["title"] = "torre-finances/expedient@1"
    base["description"] = (
        "Fitxa estructurada d'un expedient econòmic de l'Ajuntament de la Torre de l'Espanyol. "
        "El camp `dades` segueix l'esquema de `dades_per_tipus[tipus]`."
    )
    base["dades_per_tipus"] = {t: m.model_json_schema(by_alias=True) for t, m in MODELS_DADES.items()}
    return base
