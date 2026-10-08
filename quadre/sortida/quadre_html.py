"""Genera el quadre de comandament com un únic HTML autònom (Plotly incrustat, sense xarxa)."""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from html import escape
from pathlib import Path

import plotly.offline

from quadre.nucli import regles
from quadre.nucli.numeros import eur, pct
from quadre.remissio import calendari

E = escape


def _f(v) -> float | None:
    return None if v is None else float(v)


# ───────────────────────────── gràfics (especificacions Plotly; colors per rol, resolts en JS) ─────────────────────────────

def _cascada(id_, titol, passos, nota=""):
    """passos: [(etiqueta, valor, mesura)] amb mesura 'absolute' | 'relative' | 'total'."""
    passos = [p for p in passos if p[1] is not None]
    fig = {
        "data": [{
            "type": "waterfall", "orientation": "v",
            "x": [p[0] for p in passos], "y": [_f(p[1]) for p in passos], "measure": [p[2] for p in passos],
            "text": [eur(p[1], decimals=0) for p in passos], "textposition": "outside", "cliponaxis": False,
            "textfont": {"size": 11}, "constraintext": "none",
            "hovertemplate": "%{x}<br>%{text}<extra></extra>",
            "increasing": {"marker": {"color": "role:series1"}},
            "decreasing": {"marker": {"color": "role:series2"}},
            "totals": {"marker": {"color": "role:total"}},
            "connector": {"line": {"color": "role:axis", "width": 1}},
        }],
        "layout": {"showlegend": False, "yaxis": {"tickformat": ",.0f", "ticksuffix": " €"}, "margin": {"t": 30}},
    }
    taula = "".join(f"<tr><td>{E(p[0])}</td><td class=num>{eur(p[1])}</td></tr>" for p in passos)
    return _bloc_grafic(id_, titol, fig, nota, f"<table><thead><tr><th>Concepte</th><th>Import</th></tr></thead>"
                                               f"<tbody>{taula}</tbody></table>",
                        llegenda="<span class=lleg><i class=s1></i>Suma</span><span class=lleg><i class=s2></i>Resta</span>"
                                 "<span class=lleg><i class=tot></i>Subtotal</span>")


def _barres(id_, titol, categories, series, nota="", apilat=False):
    """series: [(nom, [valors], rol)]."""
    fig = {"data": [{
        "type": "bar", "name": nom, "x": categories, "y": [_f(v) for v in vals],
        "marker": {"color": f"role:{rol}"}, "text": [eur(v, decimals=0) if v is not None else "" for v in vals],
        "textposition": "inside" if apilat else "outside",
        "hovertemplate": nom + " %{x}<br>%{text}<extra></extra>"} for nom, vals, rol in series],
        "layout": {"barmode": "stack" if apilat else "group", "bargap": 0.35, "bargroupgap": 0.08,
                   "yaxis": {"tickformat": ",.0f", "ticksuffix": " €"}, "legend": {"orientation": "h", "y": -0.15},
                   "margin": {"t": 30}}}
    cap = "".join(f"<th>{E(n)}</th>" for n, _, _ in series)
    files = "".join("<tr><td>" + E(str(c)) + "</td>" + "".join(f"<td class=num>{eur(s[1][i])}</td>" for s in series)
                    + "</tr>" for i, c in enumerate(categories))
    return _bloc_grafic(id_, titol, fig, nota, f"<table><thead><tr><th></th>{cap}</tr></thead><tbody>{files}</tbody></table>")


def _bloc_grafic(id_, titol, fig, nota, taula, llegenda=""):
    return (f"<figure class=grafic><figcaption><h3>{E(titol)}</h3>{llegenda}</figcaption>"
            f"<div class=plot id='{id_}' data-fig='{E(json.dumps(fig, ensure_ascii=False))}'></div>"
            + (f"<p class=nota>{nota}</p>" if nota else "")
            + f"<details><summary>Veure les dades</summary>{taula}</details></figure>")


# ───────────────────────────── seccions ─────────────────────────────

ICONA = {"bo": "✔", "avis": "▲", "critic": "✖", "sense_dades": "–"}
ETIQ = {"bo": "Compleix", "avis": "Atenció", "critic": "No compleix", "sense_dades": "Sense dades"}


def _tiles(rs):
    out = []
    for r in rs:
        out.append(
            f"<article class='tile st-{r.estat}'>"
            f"<header><span class=ic aria-hidden=true>{ICONA[r.estat]}</span><span class=etiq>{ETIQ[r.estat]}</span>"
            + ("<span class=prov title='Expedient no aprovat'>provisional</span>" if r.provisional else "")
            + f"</header><h3>{E(r.nom)}</h3><p class=valor>{E(r.text_valor)}</p>"
            f"<p class=frase>{E(r.frase)}</p><p class='detall tecnic'>{E(r.detall)}</p></article>")
    return "<div class=tiles>" + "".join(out) + "</div>"


SEV = {"critica": ("✖", "Crítica"), "greu": ("▲", "Greu"), "avis": ("●", "Avís"), "info": ("i", "Info")}


def _alertes(als):
    if not als:
        return "<p>No hi ha alertes.</p>"
    files = []
    for a in als:
        ic, et = SEV[a.severitat]
        cls = "tecnic" if a.severitat == "info" else ""
        files.append(f"<li class='al sev-{a.severitat} {cls}'><span class=badge><span aria-hidden=true>{ic}</span> {et}</span>"
                     f"<div><strong>{E(a.titol)}</strong><br><span class=muted>{E(a.detall)}</span>"
                     + (f"<br><span class=fon>{E(a.fonament)}</span>" if a.fonament else "") + "</div></li>")
    return "<ul class=alertes>" + "".join(files) + "</ul>"


EST_REM = {"vencuda": "✖", "propera": "▲", "futura": "○", "complerta": "✔", "complerta_fora_termini": "✔",
           "no_escau": "–", "esdeveniment_pendent": "◇"}
AMBIT = {"estatal": "Estat", "autonomic": "Generalitat", "control_extern": "Control extern", "intern": "Fita interna"}


def _taula_remissio(vs, avui):
    files = []
    for v in vs:
        venc = v.venciment.strftime("%d/%m/%Y") if v.venciment else "—"
        dies = "" if v.dies is None or v.estat.startswith("complerta") else (
            f"fa {-v.dies} dies" if v.dies < 0 else "avui" if v.dies == 0 else f"d'aquí {v.dies} dies")
        comp = ""
        if v.compliment:
            comp = f"<br><span class=muted>Tramesa {E(v.compliment.get('data_tramesa') or '')} {E(v.compliment.get('justificant') or '')}</span>"
        contingut = "".join(f"<li>{E(c)}</li>" for c in v.contingut)
        files.append(
            f"<tr class='rem-{v.estat} amb-{v.ambit}' data-ambit='{v.ambit}' data-estat='{v.estat}'>"
            f"<td><span class='badge rem-b-{v.estat}'><span aria-hidden=true>{EST_REM[v.estat]}</span> {E(v.etiqueta)}</span></td>"
            f"<td class=num>{venc}<br><span class=muted>{dies}</span></td>"
            f"<td><strong>{E(v.nom)}</strong> · {E(v.titol)}{comp}"
            f"<details class=tecnic><summary>Contingut, canal i conseqüències</summary><ul>{contingut}</ul>"
            f"<p><b>Canal:</b> {E(v.canal)}<br><b>Termini legal:</b> {E(v.text_termini)}<br>"
            f"<b>Incompliment:</b> {E(v.consequencies)}"
            + (f"<br><b>Nota:</b> {E(v.notes)}" if v.notes else "")
            + (f"<br><b>Confiança del termini:</b> {E(v.confianca)} — verificar" if v.confianca != "alta" else "")
            + f"</p><p class=muted>Registrar: <code>python -m quadre remissio marca {v.codi} {E(v.periode)} --data AAAA-MM-DD --justificant \"…\"</code></p>"
            f"</details></td>"
            f"<td>{E(AMBIT.get(v.ambit, v.ambit))}<br><span class=muted>{E(v.organisme)}</span></td>"
            f"<td class=tecnic><span class=fon>{E(v.fonament)}</span></td></tr>")
    return ("<table class=rem><thead><tr><th>Estat</th><th>Venciment</th><th>Obligació</th><th>Destinatari</th>"
            "<th class=tecnic>Fonament</th></tr></thead><tbody>" + "".join(files) + "</tbody></table>")


def _remissio(vs, avui):
    compt = {}
    for v in vs:
        compt[v.estat] = compt.get(v.estat, 0) + 1
    resum = "".join(
        f"<span class='badge rem-b-{k}'><span aria-hidden=true>{EST_REM[k]}</span> {calendari.ETIQUETES[k]}: {n}</span> "
        for k, n in compt.items())
    filtres = ("<div class=filtres role=group aria-label='Filtre per àmbit'>"
               "<button data-f=tots class=actiu>Tots</button><button data-f=estatal>Ministeri</button>"
               "<button data-f=autonomic>Generalitat</button><button data-f=control_extern>Control extern</button>"
               "<button data-f=intern>Fites internes</button></div>")
    return (f"<p class=resum>{resum}</p>{filtres}{_taula_remissio(vs, avui)}"
            "<p class=nota>Criteri de dates: quan la norma diu «abans del dia X», la data límit que es mostra és el dia "
            "anterior (criteri conservador). Una tramesa sense constància es marca com a vençuda fins que la registres; "
            "el sistema no pot saber què s'ha tramès si no ho registres. Calendari exportable a Outlook: "
            "<code>python -m quadre remissio --ics</code>.</p>")


def _deute(repo, ex):
    pf = regles.deute_pro_forma(repo, ex)
    if not pf:
        return "<p>Sense dades d'ingressos corrents.</p>"
    files = "".join(
        f"<tr><td>{E(o['titol'])}<br><span class=muted>{E(o['clau'])}</span></td><td>{E(o['classe'])}</td>"
        f"<td class=num>{eur(o['import'])}</td><td class=num>{pct(o['import'] / pf['base'] * 100)}</td>"
        f"<td>{E(o['estat'])}</td><td class=num>{pct(Decimal(o['cost_total_maxim_pct']), 3) if o['cost_total_maxim_pct'] else '—'}</td></tr>"
        for o in pf["operacions"])
    return (f"<p>Base: ingressos corrents liquidats (ajustats, si escau) {ex} = <strong>{eur(pf['base'])}</strong>. "
            f"Deute viu a 31/12/{ex}: {eur(pf['viu'])}.</p>"
            "<table><thead><tr><th>Operació</th><th>Classe</th><th>Import</th><th>% ingr. corrents</th><th>Estat</th>"
            f"<th>Cost total màxim</th></tr></thead><tbody>{files or '<tr><td colspan=6>Cap operació</td></tr>'}</tbody></table>"
            f"<p><strong>Deute pro forma: {pct(pf['ratio'])}</strong> (límit sense autorització 75 %; màxim 110 %). "
            f"Operacions de tresoreria: {pct(pf['tresoreria'] / pf['base'] * 100)} (límit art. 51 TRLRHL: 30 %).</p>")


def _discrepancies(repo):
    ds = repo.discrepancies()
    if not ds:
        return "<p>No hi ha discrepàncies obertes.</p>"
    files = "".join(
        f"<tr><td>{d['id']}</td><td>{E(d['descripcio'])}<br><span class=muted>{E(d.get('camp') or d.get('codi') or '')}</span></td>"
        f"<td>{E(', '.join(f'{k}: {v}' for k, v in d['valors'].items()))}</td><td>{E(d.get('clau_expedient') or '')}</td>"
        f"<td>{E(d['origen'])}</td></tr>" for d in ds)
    return ("<table><thead><tr><th>#</th><th>Discrepància</th><th>Valors</th><th>Expedient</th><th>Origen</th></tr></thead>"
            f"<tbody>{files}</tbody></table><p class=nota>Resoldre: <code>python -m quadre discrepancies resol ID "
            "--estat resolta --text \"…\"</code> o, millor, importar una versió nova de la fitxa amb el valor bo.</p>")


def _expedients(repo):
    files = []
    for e in repo.expedients():
        f = repo.fitxa_vigent(e["clau"]) or {}
        pend = len(f.get("pendents") or [])
        fites = f.get("expedient", {}).get("fites") or []
        fetes = sum(1 for x in fites if x.get("estat") == "fet")
        files.append(
            f"<tr><td>{E(e['titol'])}<br><span class=muted>{E(e['num_expedient'] or e['clau'])}</span></td>"
            f"<td>{E(e['tipus'])}</td><td>{e['exercici']}</td><td>{E(e['estat_tramit'])}</td>"
            f"<td>{E(e['resolucio_num'] or '—')}</td><td class=num>{fetes}/{len(fites) if fites else '—'}</td>"
            f"<td class=num>{pend}</td><td class=num>v{e['versio_vigent']}</td></tr>")
    return ("<table><thead><tr><th>Expedient</th><th>Tipus</th><th>Exercici</th><th>Estat</th><th>Resolució</th>"
            "<th>Fites</th><th>Pendents</th><th>Versió</th></tr></thead><tbody>" + "".join(files) + "</tbody></table>")


# ───────────────────────────── pàgina ─────────────────────────────

def genera(repo, desti: Path, avui: date | None = None) -> Path:
    avui = avui or date.today()
    vs = calendari.genera(repo, avui=avui)
    als = regles.alertes(repo, vs)
    exs = repo.exercicis()
    ex = max(exs) if exs else avui.year - 1
    v = lambda c, e=ex: repo.valor(c, e)  # noqa: E731

    rp = _cascada("g_rp", f"Del resultat pressupostari al resultat ajustat · {ex}", [
        ("DRN", v("LIQ.DRN"), "absolute"), ("ORN", -v("LIQ.ORN") if v("LIQ.ORN") is not None else None, "relative"),
        ("Resultat pressupostari", v("LIQ.RP"), "total"),
        ("+ Despeses amb RTDG", v("LIQ.AJ_RTDG"), "relative"), ("+ Desviacions negatives", v("LIQ.AJ_DESV_NEG"), "relative"),
        ("− Desviacions positives", -v("LIQ.AJ_DESV_POS") if v("LIQ.AJ_DESV_POS") is not None else None, "relative"),
        ("Resultat ajustat", v("LIQ.RPA"), "total")],
        "Les desviacions positives de finançament (ingressos afectats cobrats abans que la despesa) expliquen la major part de la reducció.")

    pp = v("RT.PARTIDES_PEND")
    rt = _cascada("g_rt", f"Del romanent total al romanent lliure · {ex}", [
        ("Fons líquids", v("RT.FONS_LIQUIDS"), "absolute"), ("+ Drets pendents", v("RT.DRETS_PENDENTS"), "relative"),
        ("− Obligacions pendents", -v("RT.OBLIG_PENDENTS") if v("RT.OBLIG_PENDENTS") is not None else None, "relative"),
        ("± Partides pendents", pp if pp else None, "relative"),
        ("Romanent total", v("RT.TOTAL"), "total"),
        ("− Dubtós cobrament", -v("RT.DUBTOS") if v("RT.DUBTOS") is not None else None, "relative"),
        ("− Excés afectat", -v("RT.EXCES_AFECTAT") if v("RT.EXCES_AFECTAT") is not None else None, "relative"),
        ("RTDG", v("RT.RTDG"), "total"),
        ("− Saldo 413", -v("RT.SALDO_413") if v("RT.SALDO_413") is not None else None, "relative"),
        ("RTDG ajustat", v("RT.RTDG_AJ"), "total")],
        "Del romanent total, només el RTDG es pot destinar lliurement a despesa; l'excés afectat està compromès amb projectes finançats.")

    rd_parts = ""
    lim, comp = v("RD.LIMIT"), v("RD.COMPUTABLE")
    if lim is not None and comp is not None:
        rd_parts = _barres("g_rd", f"Regla de despesa · {ex}", ["Límit", "Despesa computable"],
                           [("Import", [lim, comp], "series1")],
                           f"Marge: {eur(v('RD.MARGE'))} ({pct(v('RD.EXCES_PCT'))} per sobre del límit)."
                           if v("RD.MARGE") is not None and v("RD.MARGE") < 0 else "")
    pef_html = ""
    pefs = repo.fitxes_vigents("pef")
    if pefs:
        q = pefs[-1]["dades"].get("quantificacio") or {}
        if q.get("exces") is not None:
            pef_html = _cascada("g_pef", "Quantificació del PEF", [
                ("Excés sobre el límit", Decimal(str(q["exces"])), "absolute"),
                ("− Part per RTDG", -Decimal(str(q["deduccio_rtdg"])), "relative"),
                ("− Part per excés afectat", -Decimal(str(q["deduccio_exces_afectat"])), "relative"),
                ("A corregir amb el PEF", Decimal(str(q["import_a_corregir"])), "total")],
                E(q.get("fonament_deduccio") or "") + (" · Criteri pendent de confirmar amb la tutela."
                                                       if q.get("criteri_confirmat_tutela") is False else ""))

    evol = ""
    if len(exs) >= 1:
        corr = [v("LIQ.DRN_CORRENTS", e) or v("EN.ING_CORRENTS", e) for e in exs]
        tot = [v("LIQ.DRN", e) for e in exs]
        cap = [(t - c) if (t is not None and c is not None) else None for t, c in zip(tot, corr)]
        evol = _barres("g_evol", "Drets reconeguts nets: corrents i altres (capital i financers)", [str(e) for e in exs],
                       [("Corrents (cap. 1-5)", corr, "series1"), ("Capital i financers (cap. 6-9)", cap, "series2")],
                       "Capital i financers = DRN totals − DRN corrents (calculat).", apilat=True)
        evol += _barres("g_orn", "Drets i obligacions reconeguts", [str(e) for e in exs],
                        [("DRN", tot, "series1"), ("ORN", [v("LIQ.ORN", e) for e in exs], "series2")])

    provisional = any(r.provisional for r in regles.regles_fiscals(repo, ex))
    plotly_js = plotly.offline.get_plotlyjs()
    html = PLANTILLA.format(
        generat=datetime.now().strftime("%d/%m/%Y %H:%M"), ex=ex,
        avis_prov=("<p class=avisprov>▲ Les xifres de " + str(ex) + " són <strong>provisionals</strong>: "
                   "l'expedient de liquidació encara no té decret.</p>") if provisional else "",
        n_crit=(lambda n: "cap crítica" if n == 0 else "1 crítica" if n == 1 else f"{n} crítiques")(sum(1 for a in als if a.severitat == "critica")),
        alertes=_alertes(als), tiles=_tiles(regles.regles_fiscals(repo, ex)),
        remissio=_remissio(vs, avui), rp=rp, rt=rt, rd=rd_parts, pef=pef_html, deute=_deute(repo, ex), evol=evol,
        discrepancies=_discrepancies(repo), expedients=_expedients(repo), plotly=plotly_js)
    desti.parent.mkdir(parents=True, exist_ok=True)
    desti.write_text(html, encoding="utf-8")
    return desti


PLANTILLA = """<!doctype html>
<html lang=ca>
<head>
<meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>Quadre financer</title>
<style>
:root {{
  color-scheme: light;
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781; --grid:#e1e0d9; --axis:#c3c2b7;
  --border:rgba(11,11,11,.10); --series1:#2a78d6; --series2:#eb6834; --total:#52514e;
  --good:#0ca30c; --good-ink:#006300; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b; --accent:#2a78d6;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835;
    --border:rgba(255,255,255,.10); --series1:#3987e5; --series2:#d95926; --total:#c3c2b7; --good-ink:#0ca30c; --accent:#3987e5;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835;
  --border:rgba(255,255,255,.10); --series1:#3987e5; --series2:#d95926; --total:#c3c2b7; --good-ink:#0ca30c; --accent:#3987e5;
}}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--page); color:var(--ink); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif }}
header.top {{ padding:20px 16px 8px; max-width:1200px; margin:auto; display:flex; flex-wrap:wrap; gap:12px; align-items:end; justify-content:space-between }}
header.top h1 {{ margin:0; font-size:22px }}
header.top p {{ margin:2px 0 0; color:var(--ink2) }}
main {{ max-width:1200px; margin:auto; padding:0 16px 48px }}
section {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:16px 18px; margin:16px 0 }}
section h2 {{ margin:0 0 12px; font-size:18px }}
h3 {{ font-size:15px; margin:0 }}
.muted, .nota, .fon {{ color:var(--ink2) }}
.fon {{ font-size:12.5px }}
.nota {{ font-size:13px }}
code {{ font-size:12.5px; background:var(--page); padding:1px 4px; border-radius:4px; word-break:break-all }}
table {{ border-collapse:collapse; width:100%; font-size:14px }}
th, td {{ text-align:left; padding:7px 8px; border-bottom:1px solid var(--grid); vertical-align:top }}
th {{ color:var(--ink2); font-weight:600; font-size:13px }}
td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap }}
.vista {{ display:flex; gap:4px; background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:3px }}
.vista button, .filtres button {{ font:inherit; font-size:13px; border:0; background:transparent; color:var(--ink2); padding:5px 10px; border-radius:6px; cursor:pointer }}
.vista button.actiu, .filtres button.actiu {{ background:var(--page); color:var(--ink); font-weight:600; box-shadow:0 0 0 1px var(--border) }}
.filtres {{ display:flex; flex-wrap:wrap; gap:4px; margin:8px 0 }}
body.executiva .tecnic {{ display:none }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px }}
.tile {{ border:1px solid var(--border); border-radius:10px; padding:12px 14px; border-top:4px solid var(--muted) }}
.tile header {{ display:flex; gap:6px; align-items:center; font-size:12.5px; font-weight:600 }}
.tile .valor {{ font-size:26px; font-weight:650; margin:4px 0 2px }}
.tile .frase {{ margin:0; color:var(--ink) }}
.tile .detall {{ margin:6px 0 0; font-size:12.5px; color:var(--ink2) }}
.st-bo {{ border-top-color:var(--good) }} .st-bo .ic, .st-bo .etiq {{ color:var(--good-ink) }}
.st-avis {{ border-top-color:var(--warning) }}
.st-critic {{ border-top-color:var(--critical) }} .st-critic .ic, .st-critic .etiq {{ color:var(--critical) }}
.prov {{ margin-left:auto; font-weight:500; color:var(--ink2); border:1px dashed var(--axis); border-radius:4px; padding:0 5px }}
.avisprov {{ border-left:4px solid var(--warning); padding:6px 10px; background:var(--page); border-radius:4px }}
.badge {{ display:inline-flex; gap:4px; align-items:center; white-space:nowrap; font-size:12.5px; font-weight:600;
         border-radius:999px; padding:2px 9px; border:1px solid var(--border); background:var(--page) }}
.alertes {{ list-style:none; margin:0; padding:0 }}
.al {{ display:grid; grid-template-columns:110px 1fr; gap:10px; padding:8px 0; border-bottom:1px solid var(--grid); align-items:start }}
.al .badge {{ justify-self:start }}
.sev-critica .badge {{ color:var(--critical); border-color:var(--critical) }}
.sev-greu .badge {{ color:var(--serious); border-color:var(--serious) }}
.sev-avis .badge {{ border-color:var(--warning) }}
.rem-b-vencuda {{ color:var(--critical); border-color:var(--critical) }}
.rem-b-propera {{ border-color:var(--warning) }}
.rem-b-complerta, .rem-b-complerta_fora_termini {{ color:var(--good-ink); border-color:var(--good) }}
.rem-b-esdeveniment_pendent {{ border-style:dashed }}
table.rem details summary {{ cursor:pointer; color:var(--ink2); font-size:13px }}
.resum .badge {{ margin:0 4px 4px 0 }}
.graella {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,480px),1fr)); gap:16px }}
figure.grafic {{ margin:0 }}
figure.grafic figcaption {{ display:flex; flex-wrap:wrap; gap:6px 14px; align-items:baseline }}
.lleg {{ font-size:12.5px; color:var(--ink2); display:inline-flex; gap:5px; align-items:center }}
.lleg i {{ width:10px; height:10px; border-radius:2px; display:inline-block }}
.lleg .s1 {{ background:var(--series1) }} .lleg .s2 {{ background:var(--series2) }} .lleg .tot {{ background:var(--total) }}
.plot {{ height:340px }}
details > summary {{ cursor:pointer }}
@media (max-width:640px) {{ .al {{ grid-template-columns:1fr }} th.tecnic, td.tecnic {{ display:none }} .plot {{ height:300px }} }}
@media print {{ .vista, .filtres, details > summary {{ display:none }} section {{ break-inside:avoid }} }}
</style>
</head>
<body>
<header class=top>
  <div><h1>Quadre de comandament financer</h1>
  <p>Ajuntament de la Torre de l'Espanyol · darrer exercici liquidat: {ex} · generat el {generat}</p></div>
  <div class=vista role=group aria-label="Vista">
    <button data-v=tecnica class=actiu>Intervenció</button><button data-v=executiva>Alcaldia i Ple</button>
  </div>
</header>
<main>
{avis_prov}
<section id=alertes><h2>Alertes · {n_crit}</h2>{alertes}</section>
<section id=regles><h2>Regles fiscals · {ex}</h2>{tiles}</section>
<section id=remissio><h2>Remissió d'informació (Ministeri, Generalitat i control extern)</h2>{remissio}</section>
<section id=liquidacio><h2>Liquidació {ex}</h2><div class=graella>{rp}{rt}</div></section>
<section id=regla><h2>Regla de despesa i pla economicofinancer</h2><div class=graella>{rd}{pef}</div></section>
<section id=deute><h2>Deute i operacions de crèdit</h2>{deute}</section>
<section id=evolucio><h2>Evolució</h2><div class=graella>{evol}</div></section>
<section id=discrepancies class=tecnic><h2>Discrepàncies obertes</h2>{discrepancies}</section>
<section id=expedients class=tecnic><h2>Expedients registrats</h2>{expedients}</section>
<p class=nota>Font: fitxes validades del registre d'expedients (quadre-finances). Les xifres provisionals provenen
d'expedients sense resolució. Aquest document no substitueix els informes preceptius.</p>
</main>
<script>{plotly}</script>
<script>
(function() {{
  const css = n => getComputedStyle(document.documentElement).getPropertyValue('--' + n).trim();
  const rol = o => {{
    if (typeof o === 'string' && o.startsWith('role:')) return css(o.slice(5));
    if (Array.isArray(o)) return o.map(rol);
    if (o && typeof o === 'object') {{ const r = {{}}; for (const k in o) r[k] = rol(o[k]); return r; }}
    return o;
  }};
  function dibuixa() {{
    document.querySelectorAll('.plot').forEach(el => {{
      const f = JSON.parse(el.dataset.fig);
      const lay = Object.assign({{
        paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)', separators:',.',
        font:{{family:'system-ui, -apple-system, Segoe UI, sans-serif', size:12, color:css('ink2')}},
        xaxis:{{gridcolor:css('grid'), linecolor:css('axis'), automargin:true}},
        margin:{{l:70, r:16, t:24, b:60}}, hoverlabel:{{bgcolor:css('surface'), font:{{color:css('ink')}}}}
      }}, f.layout);
      lay.yaxis = Object.assign({{gridcolor:css('grid'), zerolinecolor:css('axis'), automargin:true}}, f.layout.yaxis || {{}});
      Plotly.react(el, rol(f.data), lay, {{displaylogo:false, responsive:true, locale:'ca',
        toImageButtonOptions:{{format:'png', scale:2}}, modeBarButtonsToRemove:['lasso2d','select2d']}});
    }});
  }}
  dibuixa();
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', dibuixa);
  document.querySelectorAll('.vista button').forEach(b => b.onclick = () => {{
    document.querySelectorAll('.vista button').forEach(x => x.classList.toggle('actiu', x === b));
    document.body.classList.toggle('executiva', b.dataset.v === 'executiva');
    try {{ localStorage.setItem('vista', b.dataset.v); }} catch (e) {{}}
    dibuixa();
  }});
  try {{ const v = localStorage.getItem('vista'); if (v) document.querySelector('.vista [data-v="' + v + '"]').click(); }} catch (e) {{}}
  document.querySelectorAll('.filtres button').forEach(b => b.onclick = () => {{
    document.querySelectorAll('.filtres button').forEach(x => x.classList.toggle('actiu', x === b));
    document.querySelectorAll('table.rem tbody tr').forEach(tr =>
      tr.hidden = !(b.dataset.f === 'tots' || tr.dataset.ambit === b.dataset.f));
  }});
}})();
</script>
</body>
</html>
"""
