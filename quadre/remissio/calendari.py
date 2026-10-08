"""Calendari d'obligacions de remissió: genera els venciments i en calcula l'estat.

Fonts dels venciments: `cataleg/obligacions.yaml`.
Fonts dels compliments: fitxes de tipus `tramesa` (taula `compliment`).
Fonts dels esdeveniments: operacions de crèdit i PEF registrats a la BD.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from quadre.config import Entitat
from quadre.nucli.cataleg import obligacions

DIES_PROPERA = 30

ETIQUETES = {
    "vencuda": "Vençuda sense constància",
    "propera": "Propera",
    "futura": "Futura",
    "complerta": "Tramesa",
    "complerta_fora_termini": "Tramesa fora de termini",
    "no_escau": "No escau",
    "esdeveniment_pendent": "S'activarà amb l'esdeveniment",
}


@dataclass
class Venciment:
    codi: str
    nom: str
    organisme: str
    ambit: str
    periode: str
    titol: str
    venciment: date | None
    estat: str
    dies: int | None
    fonament: str
    canal: str
    text_termini: str
    confianca: str
    contingut: list[str] = field(default_factory=list)
    consequencies: str = ""
    notes: str = ""
    compliment: dict | None = None
    esdeveniment: str | None = None

    @property
    def etiqueta(self) -> str:
        return ETIQUETES[self.estat]


def _fi_mes(a: int, m: int) -> date:
    return date(a, m, calendar.monthrange(a, m)[1])


def _suma_mesos(d: date, n: int) -> date:
    m = d.month - 1 + n
    a, m = d.year + m // 12, m % 12 + 1
    return date(a, m, min(d.day, calendar.monthrange(a, m)[1]))


def _aplica(o: dict, ent: Entitat) -> bool:
    c = o.get("aplica") or {}
    if "poblacio_max" in c and ent.poblacio > c["poblacio_max"]:
        return False
    if "poblacio_min" in c and ent.poblacio < c["poblacio_min"]:
        return False
    if "model_cessio" in c and ent.model_cessio != c["model_cessio"]:
        return False
    if "tutela" in c and ent.tutela != c["tutela"]:
        return False
    return True


def _estat(venc: date | None, compliment: dict | None, avui: date) -> tuple[str, int | None]:
    dies = (venc - avui).days if venc else None
    if compliment:
        if compliment["estat"] == "no_escau":
            return "no_escau", dies
        dt = compliment.get("data_tramesa")
        if dt and venc and date.fromisoformat(dt) > venc:
            return "complerta_fora_termini", dies
        return "complerta", dies
    if venc is None:
        return "esdeveniment_pendent", None
    if venc < avui:
        return "vencuda", dies
    if dies <= DIES_PROPERA:
        return "propera", dies
    return "futura", dies


def _esdeveniments(repo) -> dict[str, list[tuple[str, str, date | None]]]:
    """{event: [(clau_expedient, titol, data|None)]} a partir de la BD."""
    ev: dict[str, list] = {}

    def afegeix(nom, clau, titol, d):
        ev.setdefault(nom, []).append((clau, titol, d))

    if repo is None:
        return ev
    for op in repo.operacions():
        df = date.fromisoformat(op["data_formalitzacio"]) if op["data_formalitzacio"] else None
        dv = date.fromisoformat(op["data_venciment"]) if op["data_venciment"] else None
        if op["estat"] == "cancel·lada":
            continue
        afegeix("formalitzacio_operacio", op["clau"], op["titol"], df)
        afegeix(f"formalitzacio_operacio_{'tresoreria' if op['classe'] == 'tresoreria' else 'llarg'}",
                op["clau"], op["titol"], df)
        if df:
            afegeix("cancellacio_operacio", op["clau"], op["titol"], dv)
    for f in repo.fitxes_vigents("pef"):
        clau = f["expedient"].get("num") or f"pef-{f['expedient']['exercici']}"
        titol = f["expedient"]["titol"]
        d = f["dades"]
        dple = (d.get("tramit") or {}).get("data_ple")
        dcons = (d.get("constatacio") or {}).get("data_constatacio")
        afegeix("aprovacio_pef", clau, titol, date.fromisoformat(str(dple)) if dple else None)
        afegeix("constatacio_pef", clau, titol, date.fromisoformat(str(dcons)) if dcons else None)
    return ev


def genera(repo=None, entitat: Entitat | None = None, avui: date | None = None,
           des_de: date | None = None, fins: date | None = None) -> list[Venciment]:
    entitat = entitat or (repo.cfg.entitat if repo else Entitat())
    avui = avui or date.today()
    if des_de is None:
        des_de = date.fromisoformat(repo.cfg.remissio_des_de) if repo else date(avui.year, 1, 1)
    fins = fins or avui + timedelta(days=400)
    compliments = repo.compliments() if repo else {}
    esdeveniments = _esdeveniments(repo)
    out: list[Venciment] = []

    for codi, o in obligacions().items():
        if not _aplica(o, entitat):
            continue
        t = o["termini"]
        condicional = (o.get("aplica") or {}).get("condicional", False)

        def nou(periode: str, titol: str, venc: date | None, esdev: str | None = None):
            comp = compliments.get((codi, periode))
            estat, dies = _estat(venc, comp, avui)
            out.append(Venciment(
                codi=codi, nom=o["nom"], organisme=o["organisme"], ambit=o["ambit"], periode=periode, titol=titol,
                venciment=venc, estat=estat, dies=dies, fonament=o["fonament"], canal=o["canal"],
                text_termini=o["text_termini"], confianca=o.get("confianca", "alta"),
                contingut=o.get("contingut") or [], consequencies=o.get("consequencies", ""),
                notes=o.get("notes", ""), compliment=comp, esdeveniment=esdev))

        if t["tipus"] == "anual":
            for p in range(des_de.year - 2, fins.year + 3):
                venc = date(p + t.get("offset_any", 0), t["mes"], t["dia"])
                if t.get("abans_de"):
                    venc -= timedelta(days=1)
                if not (des_de <= venc <= fins):
                    continue
                if condicional and (codi, str(p)) not in compliments:
                    continue
                nou(str(p), o["titol_periode"].format(p=p, p1=p + 1, p3=p + 3), venc)

        elif t["tipus"] == "trimestral":
            for p in range(des_de.year - 1, fins.year + 2):
                for q in t["trimestres"]:
                    mes_seg = q * 3 + 1
                    a = p + (1 if mes_seg > 12 else 0)
                    venc = _fi_mes(a, (mes_seg - 1) % 12 + 1)
                    if t.get("abans_de"):
                        venc -= timedelta(days=1)
                    if not (des_de <= venc <= fins):
                        continue
                    periode = f"{p}-T{q}"
                    nou(periode, o["titol_periode"].format(p=periode), venc)

        elif t["tipus"] == "esdeveniment":
            events = t["event"] if isinstance(t["event"], list) else [t["event"]]
            for ev in events:
                for clau, titol_exp, data_ev in esdeveniments.get(ev, []):
                    periode = f"{clau}:{ev}"
                    titol = o["titol_periode"].format(exp=clau, event=ev.replace("_", " "))
                    if data_ev is None:
                        nou(periode, titol, None, esdev=ev)
                        continue
                    if "dies" in t:
                        venc = data_ev + timedelta(days=t["dies"])
                    elif "mesos" in t:
                        venc = _suma_mesos(data_ev, t["mesos"])
                    else:
                        seg = _suma_mesos(date(data_ev.year, data_ev.month, 1), 1)
                        venc = seg.replace(day=t["dia_mes_seguent"])
                    nou(periode, titol, venc, esdev=ev)

    ordre = {"vencuda": 0, "propera": 1, "esdeveniment_pendent": 2, "futura": 3,
             "complerta_fora_termini": 4, "complerta": 5, "no_escau": 6}
    out.sort(key=lambda v: (ordre[v.estat], v.venciment or date.max, v.codi))
    return out


def a_ics(venciments: list[Venciment]) -> str:
    """Exporta els venciments pendents a iCalendar (Outlook, Google Calendar), amb avís 7 dies abans."""
    ara = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    linies = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Ajuntament Torre de l'Espanyol//Quadre finances//CA",
              "CALSCALE:GREGORIAN", "X-WR-CALNAME:Remissió d'informació econòmica"]
    for v in venciments:
        if v.venciment is None or v.estat in ("complerta", "complerta_fora_termini", "no_escau", "vencuda"):
            continue  # les vençudes ja surten al quadre; a Outlook només hi van els venciments futurs
        d = v.venciment.strftime("%Y%m%d")
        d2 = (v.venciment + timedelta(days=1)).strftime("%Y%m%d")
        desc = f"{v.organisme}\n{v.canal}\n{v.fonament}\nTermini: {v.text_termini}"
        linies += [
            "BEGIN:VEVENT", f"UID:{v.codi}-{v.periode}@quadre-finances.torre", f"DTSTAMP:{ara}",
            f"DTSTART;VALUE=DATE:{d}", f"DTEND;VALUE=DATE:{d2}",
            f"SUMMARY:{esc('Remissió · ' + v.nom + ' · ' + v.titol)}", f"DESCRIPTION:{esc(desc)}",
            "BEGIN:VALARM", "TRIGGER:-P7D", "ACTION:DISPLAY", f"DESCRIPTION:{esc(v.nom)}", "END:VALARM",
            "END:VEVENT"]
    linies.append("END:VCALENDAR")
    return "\r\n".join(linies) + "\r\n"
