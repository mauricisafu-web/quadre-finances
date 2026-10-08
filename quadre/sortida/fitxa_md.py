"""Resum llegible (FITXA.md) que es desa a cada carpeta del registre d'expedients."""
from __future__ import annotations

from quadre.nucli.cataleg import magnituds
from quadre.nucli.numeros import eur


def _fmt(codi, v):
    u = magnituds()[codi]["unitat"]
    return eur(v) if u == "eur" else f"{eur(v, simbol=False)}{' %' if u == 'pct' else ' dies' if u == 'dies' else ''}"


def resum_markdown(repo, clau: str, informe, canvis: list[str] | None) -> str:
    exp = next(e for e in repo.expedients() if e["clau"] == clau)
    fitxa = repo.fitxa_vigent(clau) or {}
    l = [f"# {exp['titol']}", "",
         "| | |", "|---|---|",
         f"| Expedient | {exp['num_expedient'] or '— (sense número)'} |",
         f"| Tipus · exercici | {exp['tipus']} · {exp['exercici']} |",
         f"| Estat | {exp['estat_tramit']} |",
         f"| Òrgan | {exp['organ'] or '—'} |",
         f"| Resolució | {exp['resolucio_num'] or 'PENDENT'} {('de ' + exp['resolucio_data']) if exp['resolucio_data'] else ''} |",
         f"| Versió vigent | v{exp['versio_vigent']} |", ""]

    fets = repo.con.execute(
        "SELECT codi FROM fet WHERE expedient_id=? AND substituit_el IS NULL ORDER BY codi", (exp["id"],)).fetchall()
    if fets:
        l += ["## Magnituds registrades", "", "| Magnitud | Valor | Qualitat |", "|---|---:|---|"]
        for (codi,) in fets:
            f = repo.fet_vigent(codi, exp["exercici"])
            if f:
                l.append(f"| {magnituds()[codi]['nom']} | {_fmt(codi, f['valor'])} | {f['qualitat']}"
                         f"{' · calculat' if f['calculat'] else ''} |")
        l.append("")

    if fitxa.get("pendents"):
        l += ["## Pendents", ""] + [f"- **{p['camp']}**: {p['motiu']}" for p in fitxa["pendents"]] + [""]
    if fitxa.get("incoherencies"):
        l += ["## Incoherències declarades", ""]
        for i in fitxa["incoherencies"]:
            l.append(f"- {i['descripcio']}: " + ", ".join(f"{k} = {v}" for k, v in (i.get("valors") or {}).items()))
        l.append("")

    if informe and informe.troballes:
        l += ["## Validació de la darrera versió", "", "```", informe.text(), "```", ""]
    if canvis:
        l += ["## Canvis respecte de la versió anterior", ""] + [f"- {c}" for c in canvis] + [""]

    l += ["## Historial de versions", ""]
    for v in repo.versions(clau):
        l.append(f"- v{v['versio']} · {v['creada_el'][:19].replace('T', ' ')} UTC")
    return "\n".join(l) + "\n"
