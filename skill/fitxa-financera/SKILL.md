---
name: fitxa-financera
description: Genera, valida i registra la fitxa estructurada (JSON torre-finances/expedient@1) d'un expedient econòmic de l'Ajuntament de la Torre de l'Espanyol perquè alimenti el quadre de comandament financer. Usa-la SEMPRE en acabar o actualitzar una liquidació, pressupost, modificació de crèdit, PEF, operació de crèdit (pòlissa, préstec), estat de tresoreria, PMP, informe de control intern o compte general, i quan es faci una tramesa d'informació al Ministeri, la Generalitat, la Sindicatura o l'IGAE. També quan l'usuari digui «fitxa», «registra-ho al quadre», «actualitza el quadre» o «marca la tramesa».
---

# Fitxa financera per al quadre de comandament

El quadre (`C:\Users\secretari\quadre-finances`) s'alimenta de fitxes JSON validades. Aquesta skill diu com generar-les.
L'esquema complet és a `esquema.json` (al costat d'aquest fitxer); el camp `dades` segueix `dades_per_tipus[tipus]`.

## Regles (no negociables)

1. **Només xifres llegides d'una font** (Excel ABSIS, document aprovat, llistat). Indica-la a `font_ref` del bloc
   (fitxer + full + cel·la, o document + annex). Si calcules una xifra, posa el nom del camp a `calculats`.
2. **Desconegut = `null` + entrada a `pendents`** (`{"camp": ..., "motiu": ...}`). Mai un zero per omissió.
3. **Format**: imports amb punt decimal i 2 decimals, sense milers (`1496005.42`); percentatges en tant per cent
   (`21.2914`); dates ISO (`2026-09-24`); `entitat.nif` = `P4315400D`.
4. **Estat**: `aprovat`/`publicat`/`executat` només si hi ha `resolucio.num` i `resolucio.data`. Si no, `en_tramit`.
5. **Incoherències entre fonts**: no en triïs cap; posa tots els valors a `incoherencies`.
6. **Sense dades personals**: codis, no noms (bestreta `2019000002`, no el titular).
7. **Número d'expedient** del gestor (`4315200000-AAAA-NNNNNNN`) si n'hi ha; si no, `null`.
8. Una versió nova d'un expedient ja registrat és **una fitxa nova completa** amb el mateix número: el sistema
   en guarda l'historial i marca els canvis.

## Com registrar-la

**Opció A — eina MCP `finances-torre` disponible** (Claude Desktop, Cowork o Claude Code amb el servidor configurat):
crida `esquema_fitxa` si no tens l'esquema, després `registrar_fitxa(fitxa)`. Si retorna `valida: false`,
corregeix els errors i torna-hi. No cal res més.

**Opció B — accés al disc sense MCP** (Claude Code, Cowork):
1. Desa-la a `C:\Users\secretari\quadre-finances\safata\entrada\<exercici>_<tipus>_<num-o-clau>_<AAAAMMDD-HHMM>.json`
2. Executa `C:\Users\secretari\quadre-finances\.venv\Scripts\python.exe -m quadre valida <fitxer>` (des de la
   carpeta `C:\Users\secretari\quadre-finances`).
3. Corregeix fins que digui «Fitxa vàlida». Els AVISOS s'han de llegir i, si escau, explicar a l'usuari.

**Opció C — sense disc ni MCP** (claude.ai web o mòbil): al final de la resposta, un únic bloc ` ```json ` que
comenci per `{"$fitxa": "torre-finances/expedient@1", ...}`. L'usuari el desarà a la safata.

**No importis mai a la BD**: la importació (`python -m quadre importa`) la fa l'usuari.

## Trameses d'informació

Quan l'usuari faci o confirmi una tramesa (Ministeri, EACAT, Sindicatura, IGAE), registra-la:

```
python -m quadre remissio marca <CODI> <PERIODE> --data AAAA-MM-DD --justificant "núm. registre / justificant"
```

Codis: `cataleg/obligacions.yaml` (p. ex. `MIN_LIQUIDACIO 2025`, `MIN_TRIMESTRAL_PMP_TRESORERIA 2026-T3`,
`GEN_ESTAT_DEUTE 2025`, `SIN_COMPTE_GENERAL 2025`, `SIN_218_3 2025`, `IGAE_INFORME_RESUM 2025`).
Per a una obligació que no aplica aquell període: `--no-escau`. Amb MCP: fitxa de tipus `tramesa`.

## Esquelet mínim

```json
{
  "$fitxa": "torre-finances/expedient@1",
  "entitat": { "nif": "P4315400D" },
  "tipus": "liquidacio",
  "expedient": { "num": "4315200000-2026-0000642", "exercici": 2025, "titol": "Liquidació del pressupost 2025",
                 "estat_tramit": "en_tramit", "organ": "alcaldia", "resolucio": { "num": null, "data": null } },
  "font": { "origen": "claude_code", "fitxers": [ { "ruta": "…" } ] },
  "dades": { "romanent_tresoreria": { "rt_total": 1496005.42, "font_ref": "comprovacions v14!LIQ_ANNEXOS I" } },
  "pendents": [ { "camp": "expedient.resolucio", "motiu": "Falta el decret" } ],
  "incoherencies": []
}
```

Exemples complets: `C:\Users\secretari\quadre-finances\dades_inicials\*.json`.
