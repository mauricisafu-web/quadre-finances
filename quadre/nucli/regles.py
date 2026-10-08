"""Regles fiscals, KPI i alertes a partir dels fets vigents de la BD."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from quadre.nucli.cataleg import font_parametre, parametre
from quadre.nucli.numeros import eur, pct

VERD, TARONJA, VERMELL, GRIS = "bo", "avis", "critic", "sense_dades"


@dataclass
class Regla:
    codi: str
    nom: str
    valor: Decimal | None
    text_valor: str
    estat: str
    frase: str          # llenguatge planer (vista executiva)
    detall: str         # llindar i fonament (vista tècnica)
    llindar: Decimal | None = None
    provisional: bool = False


@dataclass
class Alerta:
    severitat: str  # 'critica' | 'greu' | 'avis' | 'info'
    titol: str
    detall: str
    fonament: str = ""


def _fet(repo, codi, ex):
    return repo.fet_vigent(codi, ex)


def regles_fiscals(repo, exercici: int) -> list[Regla]:
    out: list[Regla] = []
    ref = date(exercici, 12, 31)

    def prov(*fets):
        return any(f and f["qualitat"] != "definitiu" for f in fets)

    cf = _fet(repo, "EST.CF", exercici)
    if cf:
        v = cf["valor"]
        out.append(Regla("EST", "Estabilitat pressupostària", v, eur(v, decimals=0), VERD if v >= 0 else VERMELL,
                         f"{'Complim' if v >= 0 else 'No complim'}: {'capacitat' if v >= 0 else 'necessitat'} de "
                         f"finançament de {eur(abs(v), decimals=0)}",
                         "Capacitat ≥ 0 · arts. 3 i 11 LOEPSF", Decimal(0), prov(cf)))
    else:
        out.append(Regla("EST", "Estabilitat pressupostària", None, "—", GRIS, "Sense dades", "arts. 3 i 11 LOEPSF"))

    marge, lim = _fet(repo, "RD.MARGE", exercici), _fet(repo, "RD.LIMIT", exercici)
    if marge:
        v = marge["valor"]
        out.append(Regla("RD", "Regla de despesa", v, eur(v, decimals=0), VERD if v >= 0 else VERMELL,
                         f"Marge de {eur(v, decimals=0)} fins al límit" if v >= 0 else
                         f"Ens hem passat {eur(-v, decimals=0)} del límit: cal un PEF",
                         f"Marge = límit {eur(lim['valor']) if lim else '—'} − despesa computable · art. 12 LOEPSF",
                         Decimal(0), prov(marge)))
    else:
        out.append(Regla("RD", "Regla de despesa", None, "—", GRIS, "Sense dades", "art. 12 LOEPSF"))

    ratio = _fet(repo, "DEU.RATIO", exercici)
    l75 = parametre("LLINDAR_DEUTE_SENSE_AUTORITZACIO", ref) or Decimal(75)
    l110 = parametre("LLINDAR_DEUTE_MAXIM", ref) or Decimal(110)
    if ratio:
        v = ratio["valor"]
        estat = VERD if v < l75 else TARONJA if v <= l110 else VERMELL
        out.append(Regla("DEU", "Deute viu", v, pct(v), estat,
                         "Sense deute" if v == 0 else f"Deute viu del {pct(v)} dels ingressos corrents",
                         f"< {pct(l75, 0)} sense autorització · ≤ {pct(l110, 0)} màxim · {font_parametre('LLINDAR_DEUTE_MAXIM')}",
                         l75, prov(ratio)))
    else:
        out.append(Regla("DEU", "Deute viu", None, "—", GRIS, "Sense dades", "art. 53 TRLRHL"))

    en = _fet(repo, "EN.ESTALVI_NET_AJ", exercici) or _fet(repo, "EN.ESTALVI_NET", exercici)
    if en:
        v = en["valor"]
        out.append(Regla("EN", "Estalvi net", v, eur(v, decimals=0), VERD if v > 0 else VERMELL,
                         f"Estalvi net {'positiu' if v > 0 else 'negatiu'}: {eur(v, decimals=0)}",
                         "> 0 per concertar deute a llarg sense autorització · art. 53.1 TRLRHL", Decimal(0), prov(en)))

    pmp = _fet(repo, "TES.PMP", exercici)
    lim_pmp = parametre("PMP_MAXIM_DIES", ref) or Decimal(30)
    if pmp:
        v = pmp["valor"]
        out.append(Regla("PMP", "Període mitjà de pagament", v, f"{eur(v, simbol=False)} dies",
                         VERD if v <= lim_pmp else VERMELL,
                         f"Paguem els proveïdors en {eur(v, simbol=False, decimals=0)} dies (límit {lim_pmp:.0f})",
                         f"≤ {lim_pmp:.0f} dies · art. 13.6 LOEPSF; RD 635/2014", lim_pmp, prov(pmp)))
    return out


def deute_pro_forma(repo, exercici_base: int) -> dict | None:
    """Ràtio de deute incloent les operacions vigents o projectades (no cancel·lades ni vençudes)."""
    base = repo.valor("EN.ING_CORR_AJ", exercici_base) or repo.valor("EN.ING_CORRENTS", exercici_base)
    viu = repo.valor("DEU.VIU", exercici_base) or Decimal(0)
    if not base:
        return None
    avui = date.today()
    ops = [o for o in repo.operacions()
           if o["estat"] != "cancel·lada" and (not o["data_venciment"] or date.fromisoformat(o["data_venciment"]) >= avui)]
    total = viu + sum((o["import"] for o in ops), Decimal(0))
    return {"base": base, "viu": viu, "operacions": ops, "total": total, "ratio": total / base * 100,
            "tresoreria": sum((o["import"] for o in ops if o["classe"] == "tresoreria"), Decimal(0))}


def alertes(repo, venciments) -> list[Alerta]:
    out: list[Alerta] = []
    ex = max(repo.exercicis() or [date.today().year - 1])

    for r in regles_fiscals(repo, ex):
        if r.estat == VERMELL:
            out.append(Alerta("greu", f"{r.nom} {ex}: incompliment", r.frase, r.detall))
        if r.provisional and r.estat != GRIS:
            out.append(Alerta("info", f"{r.nom} {ex}: dada provisional",
                              "L'expedient d'origen encara no està aprovat (sense número i data de resolució)."))

    pf = deute_pro_forma(repo, ex)
    if pf and pf["operacions"]:
        l75 = parametre("LLINDAR_DEUTE_SENSE_AUTORITZACIO") or Decimal(75)
        l30 = parametre("LIMIT_OPERACIONS_TRESORERIA_PCT") or Decimal(30)
        rt = pf["tresoreria"] / pf["base"] * 100
        if pf["ratio"] >= l75:
            out.append(Alerta("greu", "Deute pro forma per sobre del 75 %", f"Amb les operacions en curs: {pct(pf['ratio'])}",
                              "DA 14a RDL 20/2011"))
        if rt > l30:
            out.append(Alerta("critica", "Operacions de tresoreria per sobre del 30 %", f"{pct(rt)}", "art. 51 TRLRHL"))

    for d in repo.discrepancies():
        out.append(Alerta("avis", f"Discrepància oberta: {d['descripcio']}",
                          ", ".join(f"{k}: {v}" for k, v in d["valors"].items())
                          + (f" · expedient {d['clau_expedient']}" if d.get("clau_expedient") else "")))

    vencudes = [v for v in venciments if v.estat == "vencuda"]
    for ambit, sev, que in (("extern", "critica", "trameses vençudes sense constància"),
                            ("intern", "greu", "fites internes vençudes")):
        grup = [v for v in vencudes if (v.ambit == "intern") == (ambit == "intern")]
        if grup:
            llista = "; ".join(f"{v.nom} · {v.titol} ({v.venciment:%d/%m/%Y})" for v in grup)
            out.append(Alerta(sev, f"{len(grup)} {que}", llista + ". Si ja s'han fet, registra-les (secció Remissió)."))
    for v in venciments:
        if v.estat == "propera":
            out.append(Alerta("avis", f"{'Fita' if v.ambit == 'intern' else 'Tramesa'} propera ({v.dies} dies): {v.nom} ({v.titol})",
                              f"Venciment {v.venciment:%d/%m/%Y} · {v.organisme}", v.fonament))

    for f in repo.fitxes_vigents("liquidacio"):
        for p in f.get("pendents") or []:
            out.append(Alerta("info", f"Pendent a la liquidació {f['expedient']['exercici']}: {p['camp']}", p["motiu"]))

    ordre = {"critica": 0, "greu": 1, "avis": 2, "info": 3}
    out.sort(key=lambda a: ordre[a.severitat])
    return out
