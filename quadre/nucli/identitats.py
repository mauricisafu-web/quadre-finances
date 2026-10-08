"""Identitats comptables i coherència interna de cada tipus de fitxa (nivells 2 i 5).

Totes les comparacions es fan amb Decimal i una tolerància d'1 cèntim.
Quan falta un component, la identitat no es pot verificar: es genera un AVÍS
amb el valor implícit (mai no s'inventa el component).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quadre.nucli.numeros import TOLERANCIA, eur, pct

TOL_PCT = Decimal("0.01")  # 0,01 punts percentuals


@dataclass
class Troballa:
    nivell: int
    severitat: str  # 'error' | 'avis' | 'info'
    codi: str
    missatge: str

    def com_dict(self) -> dict:
        return {"nivell": self.nivell, "severitat": self.severitat, "codi": self.codi, "missatge": self.missatge}


def _g(d: dict | None, *claus):
    for c in claus:
        if not isinstance(d, dict):
            return None
        d = d.get(c)
    return d


def _suma(*v):
    return sum((x for x in v), Decimal(0))


class _Comprovador:
    def __init__(self):
        self.t: list[Troballa] = []

    def igualtat(self, codi: str, descr: str, calculat, declarat, *, tol=TOLERANCIA, unitat="eur", nivell=2):
        if calculat is None or declarat is None:
            return
        dif = Decimal(declarat) - Decimal(calculat)
        if abs(dif) > tol:
            f = eur if unitat == "eur" else pct
            self.t.append(Troballa(nivell, "error", codi,
                                   f"{descr}: calculat {f(calculat)} ≠ declarat {f(declarat)} (diferència {f(dif)})"))

    def avis(self, codi, missatge, nivell=2):
        self.t.append(Troballa(nivell, "avis", codi, missatge))

    def error(self, codi, missatge, nivell=2):
        self.t.append(Troballa(nivell, "error", codi, missatge))

    def info(self, codi, missatge, nivell=2):
        self.t.append(Troballa(nivell, "info", codi, missatge))


# ───────────────────────────── Liquidació ─────────────────────────────

def liquidacio(d: dict) -> list[Troballa]:
    c = _Comprovador()
    ei, ed = d.get("execucio_ingressos") or {}, d.get("execucio_despeses") or {}
    rp, rt = d.get("resultat_pressupostari") or {}, d.get("romanent_tresoreria") or {}

    drn, orn = ei.get("drn"), ed.get("orn")

    # Execució
    if ei.get("recaptacio_neta") is not None and ei.get("pendent_cobrament") is not None and drn is not None:
        c.igualtat("EXEC_ING", "Recaptació + pendent de cobrament = DRN",
                   ei["recaptacio_neta"] + ei["pendent_cobrament"], drn)
    if ed.get("pagaments") is not None and ed.get("pendent_pagament") is not None and orn is not None:
        c.igualtat("EXEC_DESP", "Pagaments + pendent de pagament = ORN", ed["pagaments"] + ed["pendent_pagament"], orn)
    if orn is not None and ed.get("credits_definitius") is not None and orn > ed["credits_definitius"]:
        c.error("ORN_CREDITS", f"ORN ({eur(orn)}) superen els crèdits definitius ({eur(ed['credits_definitius'])})")
    if all(ed.get(k) is not None for k in ("credits_inicials", "modificacions", "credits_definitius")):
        c.igualtat("CRED_DEF", "Crèdits inicials + modificacions = crèdits definitius",
                   ed["credits_inicials"] + ed["modificacions"], ed["credits_definitius"])

    # Resultat pressupostari (arts. 96-97 RD 500/1990)
    if drn is not None and orn is not None:
        c.igualtat("RP", "RP = DRN − ORN", drn - orn, rp.get("rp"))
    parts = [rp.get(k) for k in ("operacions_corrents", "operacions_capital", "actius_financers", "passius_financers")]
    if parts[0] and parts[1]:
        for camp, total in (("drn", drn), ("orn", orn)):
            valors = [p.get(camp) for p in parts if p]
            if total is None or any(v is None for v in valors):
                continue
            suma = _suma(*valors)
            if abs(suma - total) > TOLERANCIA:
                complet = parts[2] is not None and parts[3] is not None
                (c.error if complet else c.avis)(
                    f"RP_PARTS_{camp.upper()}",
                    f"Suma de {camp.upper()} per tipus d'operació ({eur(suma)}) ≠ total ({eur(total)})"
                    + ("" if complet else "; falten els actius/passius financers?"))
    if all(rp.get(k) is not None for k in ("rp", "ajust_despeses_rtdg", "ajust_desviacions_negatives",
                                             "ajust_desviacions_positives")):
        c.igualtat("RPA", "RPA = RP + despeses RTDG + desviacions negatives − desviacions positives",
                   rp["rp"] + rp["ajust_despeses_rtdg"] + rp["ajust_desviacions_negatives"]
                   - rp["ajust_desviacions_positives"], rp.get("rp_ajustat"))

    # Romanent de tresoreria (art. 191.2 TRLRHL; arts. 101-105 RD 500/1990)
    fl, dp, op, pp = (rt.get(k) for k in ("fons_liquids", "drets_pendents_total", "obligacions_pendents_total",
                                          "partides_pendents_aplicacio"))
    total = rt.get("rt_total")
    if None not in (fl, dp, op, total):
        if pp is None:
            implicit = total - (fl + dp - op)
            if abs(implicit) > TOLERANCIA:
                c.avis("RT_PARTIDES",
                       f"RT = fons líquids + drets pendents − obligacions pendents + partides pendents d'aplicació: "
                       f"sense el component 4 no quadra (falten {eur(implicit)}). Informa "
                       f"`partides_pendents_aplicacio` (valor implícit: {eur(implicit)}).")
        else:
            c.igualtat("RT", "RT = fons líquids + drets pendents − obligacions pendents + partides pendents",
                       fl + dp - op + pp, total)
    if None not in (total, rt.get("saldos_dubtos_cobrament"), rt.get("exces_financament_afectat")):
        c.igualtat("RTDG", "RTDG = RT − dubtós cobrament − excés de finançament afectat",
                   total - rt["saldos_dubtos_cobrament"] - rt["exces_financament_afectat"], rt.get("rtdg"))
    if rt.get("rtdg") is not None and rt.get("rtdg_ajustat") is not None:
        s413, s418 = rt.get("saldo_413"), rt.get("saldo_418")
        if s413 is None:
            c.avis("RTDG_AJ", "RTDG ajustat informat sense saldo del compte 413: no es pot verificar")
        else:
            calc = rt["rtdg"] - s413 - (s418 or 0)
            if s418 is None and abs(calc - rt["rtdg_ajustat"]) <= TOLERANCIA:
                c.info("RTDG_AJ", "RTDG ajustat = RTDG − 413 (saldo 418 no informat: s'ha considerat 0)")
            else:
                c.igualtat("RTDG_AJ", "RTDG ajustat = RTDG − saldo 413 − saldo 418", calc, rt["rtdg_ajustat"])

    rc = d.get("romanents_credit") or {}
    if rc.get("total") is not None:
        parcial = _suma(*(rc.get(k) or 0 for k in ("incorporacio_obligatoria", "incorporacio_voluntaria",
                                                   "no_incorporables")))
        if parcial - rc["total"] > TOLERANCIA:
            c.error("ROMANENTS", f"Els components dels romanents ({eur(parcial)}) superen el total ({eur(rc['total'])})")

    # Estabilitat
    es = d.get("estabilitat") or {}
    if es.get("ingressos_no_financers") is not None and es.get("despeses_no_financeres") is not None:
        ajustos = _suma(*(a.get("import") or a.get("import_") or 0 for a in es.get("ajustos_sec") or []))
        c.igualtat("EST_CF", "CF = ingressos no financers − despeses no financeres ± ajustos SEC",
                   es["ingressos_no_financers"] - es["despeses_no_financeres"] + ajustos,
                   es.get("capacitat_financament"))

    # Regla de despesa (art. 12 LOEPSF)
    rd = d.get("regla_despesa") or {}
    lim, comp, base = rd.get("limit_n"), rd.get("despesa_computable_n"), rd.get("despesa_computable_n_1")
    if lim is not None and comp is not None:
        c.igualtat("RD_MARGE", "Marge = límit − despesa computable", lim - comp, rd.get("marge"))
        if rd.get("compleix") is not None and rd["compleix"] != (comp <= lim):
            c.error("RD_COMPLEIX", f"`compleix`={rd['compleix']} és incoherent amb el marge {eur(lim - comp)}")
        if lim:
            c.igualtat("RD_EXCES", "Excés sobre el límit = computable / límit − 1",
                       (comp / lim - 1) * 100, rd.get("exces_sobre_limit_pct"), tol=TOL_PCT, unitat="pct")
    if base and comp is not None:
        c.igualtat("RD_VARIACIO", "Variació interanual = computable n / computable n−1 − 1",
                   (comp / base - 1) * 100, rd.get("variacio_interanual_pct"), tol=TOL_PCT, unitat="pct")
    if base is not None and rd.get("taxa_referencia") is not None and lim is not None:
        teoric = base * (1 + rd["taxa_referencia"] / 100) + (rd.get("augments_permanents") or 0) \
            - (rd.get("disminucions_permanents") or 0)
        if abs(teoric - lim) > TOLERANCIA:
            c.avis("RD_LIMIT", f"Límit declarat {eur(lim)} ≠ base × (1 + taxa) ± canvis normatius = {eur(teoric)}. "
                               "Comprova els augments/disminucions permanents de recaptació")

    # Estalvi net (art. 53.1 TRLRHL)
    en = d.get("estalvi_net") or {}
    if all(en.get(k) is not None for k in ("ingressos_corrents", "despeses_corrents_1_2_4", "anualitat_teorica")):
        c.igualtat("EN", "Estalvi net = ingressos corrents − despeses cap. 1, 2 i 4 − anualitat teòrica",
                   en["ingressos_corrents"] - en["despeses_corrents_1_2_4"] - en["anualitat_teorica"],
                   en.get("estalvi_net"))
    if en.get("ingressos_corrents") is not None and en.get("ingressos_extraordinaris") is not None:
        c.igualtat("EN_ING_AJ", "Ingressos corrents ajustats = ingressos corrents − extraordinaris",
                   en["ingressos_corrents"] - en["ingressos_extraordinaris"], en.get("ingressos_corrents_ajustats"))
    rc_corr = _g(rp, "operacions_corrents", "drn")
    if rc_corr is not None and en.get("ingressos_corrents") is not None:
        c.igualtat("EN_ING", "Ingressos corrents (estalvi net) = DRN corrents (resultat pressupostari)",
                   rc_corr, en["ingressos_corrents"], nivell=3)

    # Deute (art. 53 TRLRHL)
    de = d.get("endeutament") or {}
    if de.get("deute_viu_llarg") is not None and de.get("deute_viu_curt") is not None:
        c.igualtat("DEU_VIU", "Deute viu = llarg + curt termini", de["deute_viu_llarg"] + de["deute_viu_curt"],
                   de.get("deute_viu_total"))
    base_deute = en.get("ingressos_corrents_ajustats") or en.get("ingressos_corrents")
    if de.get("deute_viu_total") is not None and base_deute:
        c.igualtat("DEU_RATIO", "Ràtio de deute viu = deute viu / ingressos corrents ajustats",
                   de["deute_viu_total"] / base_deute * 100, de.get("ratio_deute_viu_pct"), tol=TOL_PCT, unitat="pct")

    # Control intern
    ci = d.get("control_intern") or {}
    for b in ci.get("bestretes") or []:
        if (b.get("antiguitat_anys") or 0) >= 1 and "pendent" in (b.get("estat") or ""):
            c.avis("BESTRETA_ANTIGA", f"Bestreta {b['codi']} pendent de justificar des de fa {b['antiguitat_anys']} anys",
                   nivell=5)
    return c.t


# ───────────────────────────── Operació de crèdit ─────────────────────────────

def operacio_credit(d: dict, expedient: dict) -> list[Troballa]:
    from quadre.nucli.cataleg import parametre

    c = _Comprovador()
    imp, base = d.get("import"), _g(d, "base_ratio", "ingressos_corrents")
    if imp is not None and base:
        ratio = imp / base * 100
        c.igualtat("OC_RATIO", "Ràtio = import / ingressos corrents de la base", ratio, d.get("ratio_pct"),
                   tol=TOL_PCT, unitat="pct")
        if d.get("classe") == "tresoreria":
            limit51 = parametre("LIMIT_OPERACIONS_TRESORERIA_PCT")
            if limit51 is not None and ratio > limit51:
                c.error("OC_ART51", f"L'operació sola ({pct(ratio)}) supera el límit del {pct(limit51, 0)} de l'art. 51 TRLRHL",
                        nivell=5)
            llindar = parametre("LLINDAR_COMPETENCIA_PLE_TRESORERIA_PCT")
        else:
            llindar = parametre("LLINDAR_COMPETENCIA_PLE_LLARG_PCT")
        organ = d.get("competencia") or expedient.get("organ")
        if llindar is not None and ratio > llindar and organ != "ple":
            c.error("OC_COMPETENCIA",
                    f"Ràtio {pct(ratio)} > {pct(llindar, 0)}: és competència del Ple (art. 52.2 TRLRHL), "
                    f"però la fitxa indica '{organ}'", nivell=5)
    ctm = _g(d, "prudencia", "cost_total_maxim") or {}
    if ctm.get("index_valor_pct") is not None and ctm.get("diferencial_pct") is not None:
        c.igualtat("OC_CTM", "Cost total màxim = valor de l'índex + diferencial",
                   ctm["index_valor_pct"] + ctm["diferencial_pct"], ctm.get("total_pct"), tol=Decimal("0.0005"),
                   unitat="pct")
    tae = _g(d, "formalitzacio", "tae_pct")
    if tae is not None and ctm.get("total_pct") is not None and tae > ctm["total_pct"]:
        c.error("OC_TAE", f"TAE formalitzada {pct(tae, 3)} > cost total màxim {pct(ctm['total_pct'], 3)} "
                          "(art. 48 bis TRLRHL: no es pot formalitzar)", nivell=5)
    for o in d.get("ofertes") or []:
        if o.get("tae_pct") is not None and ctm.get("total_pct") is not None and o["tae_pct"] > ctm["total_pct"]:
            c.avis("OC_OFERTA", f"L'oferta de {o['entitat']} (TAE {pct(o['tae_pct'], 3)}) supera el cost total màxim",
                   nivell=5)
    return c.t


# ───────────────────────────── PEF ─────────────────────────────

def pef(d: dict, expedient: dict) -> list[Troballa]:
    c = _Comprovador()
    q = d.get("quantificacio") or {}
    if all(q.get(k) is not None for k in ("exces", "deduccio_rtdg", "deduccio_exces_afectat")):
        c.igualtat("PEF_IMPORT", "Import a corregir = excés − deducció RTDG − deducció excés afectat",
                   q["exces"] - q["deduccio_rtdg"] - q["deduccio_exces_afectat"], q.get("import_a_corregir"))
    if q.get("criteri_confirmat_tutela") is False:
        c.avis("PEF_TUTELA", "El criteri de quantificació encara no està confirmat amb la tutela", nivell=5)
    if expedient.get("estat_tramit") in ("aprovat", "publicat", "executat") and expedient.get("organ") not in (None, "ple"):
        c.error("PEF_ORGAN", "El PEF l'aprova el Ple (art. 23.4 LOEPSF)", nivell=5)
    for t in d.get("trajectoria") or []:
        if t.get("limit") is not None and t.get("despesa_computable") is not None and t.get("marge") is not None:
            c.igualtat("PEF_MARGE", f"Marge {t['exercici']} = límit − despesa computable",
                       t["limit"] - t["despesa_computable"], t["marge"])
    return c.t


# ───────────────────────────── Modificació de crèdit ─────────────────────────────

def modificacio_credit(d: dict, expedient: dict) -> list[Troballa]:
    c = _Comprovador()
    linies = d.get("linies") or []
    altes = _suma(*(l["import"] for l in linies if l["sentit"] == "alta"))
    baixes = _suma(*(l["import"] for l in linies if l["sentit"] == "baixa"))
    recursos = _suma(*(r["import"] for r in d.get("recursos") or []))
    mod = d.get("modalitat")
    if mod in ("credit_extraordinari", "suplement", "transferencia", "generacio", "incorporacio"):
        c.igualtat("MC_QUADRA", "Σ altes = Σ baixes + Σ recursos", baixes + recursos, altes)
    if mod in ("credit_extraordinari", "suplement") and expedient.get("organ") not in (None, "ple"):
        c.error("MC_ORGAN", "Els crèdits extraordinaris i suplements de crèdit els aprova el Ple (art. 177.2 TRLRHL)",
                nivell=5)
    if any(r["tipus"] == "rtdg" for r in d.get("recursos") or []):
        c.avis("MC_RTDG", "Finançament amb RTDG: augmenta la despesa computable i pot afectar l'estabilitat "
                          "(regla de despesa i art. 11 LOEPSF)", nivell=5)
    return c.t


# ───────────────────────────── Tipus sense identitats específiques ─────────────────────────────

def per_tipus(tipus: str, dades: dict, expedient: dict) -> list[Troballa]:
    if tipus == "liquidacio":
        t = liquidacio(dades)
        if expedient.get("estat_tramit") in ("aprovat", "publicat") and expedient.get("organ") not in (None, "alcaldia"):
            t.append(Troballa(5, "error", "LIQ_ORGAN", "La liquidació l'aprova la Presidència (art. 191.3 TRLRHL)"))
        return t
    if tipus == "operacio_credit":
        return operacio_credit(dades, expedient)
    if tipus == "pef":
        return pef(dades, expedient)
    if tipus == "modificacio_credit":
        return modificacio_credit(dades, expedient)
    return []
