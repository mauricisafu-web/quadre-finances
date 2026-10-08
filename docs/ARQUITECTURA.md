# Quadre de comandament financer — Ajuntament de la Torre de l'Espanyol
### Document d'arquitectura (v0.1 · 24/09/2026)

> Abast: captura de dades dels expedients econòmics treballats amb Claude, model de dades, arquitectura, catàleg de KPI, visualització i full de ruta.
> Destinatari: el secretari-interventor (que també fa de tresorer), com a propietari funcional i tècnic.
> Carpeta del projecte (proposada): `C:\Users\secretari\quadre-finances` (projecte nou i independent; **no toca** `expedients-nomines-beta` ni la `v2`).

---

## 0. Resum de decisions

| Qüestió | Decisió | Per què, en una línia |
|---|---|---|
| Font de veritat | **Les dades, no els documents ni el xat.** El xat produeix una *fitxa* estructurada validada; els documents i el quadre en són vistes | Avui la mateixa xifra és escrita a mà com a text en 4 scripts diferents (vegeu el §0.1) |
| Captura | 4 canals, per ordre de fiabilitat: (1) extractor directe de l'Excel ABSIS, (2) eina MCP `registrar_fitxa`, (3) fitxer JSON a una safata d'entrada escrit per Claude Code / Cowork, (4) parser de l'exportació de claude.ai | Com més a prop de la comptabilitat, menys risc que un número sigui inventat o mal copiat |
| Validació | 5 nivells: esquema → identitats comptables → coherència creuada → plausibilitat → estat jurídic | Un model de llenguatge pot errar un dígit; les identitats del RD 500/1990 no |
| Stack | **Python 3.12 + SQLite + Flask + Plotly**, amb el mateix patró que l'app de nòmines. Sense Electron ni Tauri | Ja teniu Python, Flask, openpyxl, python-docx, PyInstaller i LibreOffice instal·lats i provats |
| Emmagatzematge | SQLite local (WAL) **fora d'OneDrive**, amb còpia de seguretat diària a OneDrive i a `\\servidor2012\E\ARXIU` | Una BD SQLite dins una carpeta sincronitzada es pot corrompre |
| Històric | Registre **immutable** de fitxes (cap UPDATE ni DELETE) + taula de fets **bitemporal** (data de referència i data de registre) | Permet respondre «què sabíem el dia X» i reconstruir qualsevol informe passat |
| Visualització | Plotly: mateixa definició de gràfic per al navegador (interactiu) i per al Word/PDF (PNG via kaleido) | Una sola definició, dues sortides |
| MVP | Sense servidor: fitxes JSON → validador → SQLite → **un HTML estàtic** que s'obre amb Chrome | Zero infraestructura; el primer quadre en una o dues sessions de treball |

### 0.1 Diagnòstic de partida (fets comprovats avui)

Abans de dissenyar, he revisat els generadors de `liquidació\_scripts` i he passat les xifres clau del traspàs per les identitats comptables. Resultats:

1. **Les xifres estan duplicades com a text.** `1.496.005,42 €` apareix literalment a `lib.js`, `gen2.js`, `gen5.js` i `gen8.js`; `3.279.611,57 €` a `lib.js`, `gen2.js` i `gen8.js`. Si una dada es corregeix (p. ex. el compte 418), s'ha de tocar a mà a cada fitxer. És el problema que aquest projecte ha de resoldre primer.
2. **Identitats que quadren al cèntim** (calculades amb `Decimal`):
   - RP 2025 = 3.279.611,57 − 2.337.461,47 = 942.150,10 ✔
   - RP ajustat 2025 = 942.150,10 + 105.422,08 + 35.667,06 − 1.047.593,90 = 35.645,34 ✔
   - RT 2025 = 1.180.327,58 + 477.830,95 − 162.153,11 = 1.496.005,42 ✔
   - RTDG 2025 = 1.496.005,42 − 188.636,69 − 1.008.818,81 = 298.549,92 ✔ · ajustat (−413 = 4.440,58) = 294.109,34 ✔
   - Marge regla de despesa = 1.003.313,10 − 1.179.558,48 = −176.245,38 ✔ · PEF: 176.245,38 − 105.422,08 − 27.845,49 = 42.977,81 ✔
   - Pòlissa: 275.000 / 1.291.602,94 = 21,29 % ✔ · 15 % = 193.740,44 ✔ · 30 % = 387.480,88 ✔
   - RP 2024 i RP ajustat 2024 ✔ · RTDG 2024 ✔
3. **Identitat que NO quadra: romanent de tresoreria 2024.** 229.964,51 + 490.784,35 − 152.401,49 = 568.347,37, però el RT total és 554.914,59: hi falten **−13.432,78 €**. Probablement és el component 4 de l'estat del romanent (partides pendents d'aplicació, cobraments pendents d'aplicar), que el resum del traspàs no recull. No és necessàriament un error, però el validador ho ha de detectar i obligar a informar el component 4. *Exemple perfecte de per què cal el nivell 2 de validació.*
4. **Discrepància coneguda del compte 418** (0,00 a l'annex 5 i 215,82 a l'estalvi net i al superàvit). El sistema l'ha de mostrar com a **discrepància oberta** fins que la resolguis, amb els dos valors i l'efecte (RTDG ajustat 294.109,34 o 293.893,52).
5. **Semàntica ambigua a la regla de despesa.** La «variació 17,57 %» coincideix exactament amb despesa computable / límit − 1 (1.179.558,48 / 1.003.313,10 = 1,1757), no amb la variació interanual de la despesa computable. Si el límit és base 2024 × 1,032, la variació interanual seria diferent. A verificar al full `LIQ_Regla de la despesa N`; l'esquema ha de tenir camps diferents per a cada concepte perquè això no torni a passar.
6. **Alertes de calendari visibles avui (24/09/2026)**, a confirmar per tu: la tramesa de la liquidació 2025 al Ministeri està vençuda des del 31/03/2026 i és la causa de la no elegibilitat al FIE (cost total màxim Euribor + 0,45 % en lloc de + 0,20 %); a més, en els propers dies i setmanes vencen el Compte General 2025 (Ple abans de l'1/10, rendició abans del 15/10), l'execució del 3T (31/10) i el cost efectiu dels serveis (1/11). El quadre ha de fer visible això el primer dia.

---

## 1. Captura de dades i context dels xats

### 1.1 Principi rector: el xat és un canal, no una font

Un informe redactat en un xat conté xifres que venen d'una font primària (ABSIS, l'Excel de comprovacions de tancament, un decret aprovat). Si el quadre s'alimenta de text lliure extret dels xats, hereta tres riscos: transcripció (un dígit), interpretació (quina magnitud és realment) i obsolescència (una xifra d'un esborrany que després es va corregir). Per això s'estableix una **jerarquia de fonts** que el sistema aplica automàticament quan dues fonts discrepen:

| Rang | Font | Qualitat per defecte | Exemple |
|---|---|---|---|
| 1 | Extractor directe de fitxer comptable (Excel ABSIS, llistats exportats) | `definitiu` si l'expedient està aprovat; si no, `provisional` | Full `LIQ_ANNEXOS I` del `comprovacions tancament v14` |
| 2 | Document aprovat i signat (decret, acord de Ple, certificat) | `definitiu` | Decret 2025-0000144 (liquidació 2024) |
| 3 | Fitxa emesa per Claude en un xat, validada | `provisional` fins que l'expedient es marqui aprovat | Fitxa de la pòlissa de crèdit |
| 4 | Entrada manual al quadre | `provisional` | Saldo bancari d'un dia |

Una fitxa de rang 3 mai sobreescriu un fet de rang 1 o 2: si discrepa, genera una **discrepància** i una alerta.

### 1.2 Canals de captura

#### Canal A — Safata d'entrada de fitxers (MVP; Claude Code i Cowork)

Treballes amb Claude Code i Cowork, que tenen accés al disc. Per tant, **no cal copiar i enganxar res**: Claude escriu la fitxa directament a:

```
C:\Users\secretari\quadre-finances\safata\entrada\<exercici>_<tipus>_<num-expedient>_<AAAAMMDD-HHMM>.json
```

i tot seguit executa el validador (`python -m quadre valida <fitxer>`). Si hi ha errors, Claude els veu a la sortida i els corregeix en la mateixa sessió. **Aquest bucle «escriure → validar → corregir» és el mecanisme de fiabilitat més important de tot el sistema.** La importació a la base de dades és un pas separat (`python -m quadre importa`), perquè tu decideixis quan una fitxa entra.

Estats de la safata: `entrada\` → `acceptades\` (importades, amb el hash al nom) o `rebutjades\` (amb un `.err.txt` al costat explicant per què).

#### Canal B — Servidor MCP local `finances-torre` (fase 2; el més robust)

Un servidor MCP (Model Context Protocol) en Python que s'executa a l'ordinador i que Claude Code, Cowork i Claude Desktop veuen com a eines pròpies:

| Eina | Què fa |
|---|---|
| `registrar_fitxa(fitxa)` | Valida contra l'esquema i les regles i la desa a la safata o a la BD. Si falla, retorna els errors a Claude, que els corregeix |
| `consultar_magnitud(codi, exercici)` | Retorna el valor vigent, la qualitat i la font (p. ex. el RTDG ajustat per redactar una modificació de crèdit) |
| `estat_financer(exercici)` | Resum de les regles fiscals, el deute, la tresoreria i les alertes obertes |
| `simular(escenari)` (fase 3) | «Què passa si…»: retorna l'impacte en estabilitat, regla de despesa, deute i estalvi net |

L'avantatge és doble: (1) l'esquema s'aplica a la frontera de l'eina (Claude no pot «oblidar» un camp obligatori sense rebre un error), i (2) el flux és **bidireccional**: quan redactes un expedient nou, Claude llegeix les xifres de la BD en lloc de tornar-les a demanar o, pitjor, recordar-les.

Esquelet:

```python
# quadre/mcp_server.py
from mcp.server.fastmcp import FastMCP
from quadre.nucli import validacio, repositori

mcp = FastMCP("finances-torre")

@mcp.tool()
def registrar_fitxa(fitxa: dict) -> dict:
    """Valida i registra una fitxa d'expedient econòmic (esquema torre-finances/expedient@1).
    Retorna {estat, errors, avisos, sha256}. Si hi ha errors, corregeix la fitxa i torna-hi."""
    informe = validacio.valida(fitxa)
    if informe.errors:
        return informe.com_dict()
    return repositori.desa_a_safata(fitxa, informe)

@mcp.tool()
def consultar_magnitud(codi: str, exercici: int) -> dict:
    """Valor vigent d'una magnitud (p. ex. 'RT.RTDG_AJ', 2025) amb qualitat i font."""
    return repositori.magnitud_vigent(codi, exercici)

if __name__ == "__main__":
    mcp.run()  # transport stdio
```

Registre a Claude Code (àmbit d'usuari, perquè funcioni des de qualsevol carpeta):

```bash
claude mcp add --scope user finances-torre -- C:\Users\secretari\quadre-finances\.venv\Scripts\python.exe -m quadre.mcp_server
```

Per a Claude Desktop i Cowork, la mateixa ordre es posa a `claude_desktop_config.json` dins de `mcpServers`.

#### Canal C — Exportació de claude.ai (històric i xats web)

Per als xats fets a claude.ai (web o app), l'única via fiable és l'**exportació de dades** (Configuració → Privadesa → Exporta les dades), que envia per correu un zip amb `conversations.json`. No hi ha webhooks ni API per llegir els xats de claude.ai, i no val la pena construir-hi res més. L'estructura (a verificar amb la primera exportació real) és una llista de converses amb `uuid`, `name`, `created_at` i `chat_messages`; cada missatge té `sender` (`human` / `assistant`), `created_at` i el text.

El parser només mira missatges de l'assistent i busca **blocs marcats** amb la clau `"$fitxa"`:

```python
import json, re, zipfile

BLOC = re.compile(r"```json\s*(\{\s*\"\$fitxa\"\s*:\s*\"torre-finances/.*?\})\s*```", re.S)

def fitxes_de_exportacio(ruta_zip):
    with zipfile.ZipFile(ruta_zip) as z:
        converses = json.loads(z.read("conversations.json"))
    for c in converses:
        for m in c.get("chat_messages", []):
            if m.get("sender") != "assistant":
                continue
            for bloc in BLOC.findall(m.get("text", "")):
                fitxa = json.loads(bloc)
                fitxa.setdefault("font", {})["sessio"] = f"claude.ai:{c['uuid']}:{m.get('uuid')}"
                yield fitxa
```

Si una conversa conté diverses fitxes del mateix expedient, s'importen totes (el registre és immutable) i la darrera passa a ser la vigent; les anteriors queden com a versions.

Els Artifacts no aporten res aquí: afegeixen una capa de publicació que no necessitem per a dades internes.

#### Canal D — Extractors directes (la font més fiable)

L'Excel `comprovacions tancament v14 ABSIS` ja conté totes les magnituds de la liquidació en fulls amb una estructura estable. Un extractor que llegeixi cel·les concretes és més fiable que qualsevol xat:

```python
from openpyxl import load_workbook
wb = load_workbook(ruta, read_only=True, data_only=True)   # data_only: valors calculats, no fórmules
```

- El mapatge magnitud → (full, cel·la) va en un fitxer `mapatges/comprovacions_v14.yaml`, **versionat per plantilla** (si la Diputació o l'ABSIS canvien la v14 per la v15, es fa un mapatge nou i no es toca el codi).
- `data_only=True` llegeix el darrer valor desat per Excel: el fitxer s'ha d'haver obert i desat amb Excel després de l'últim canvi. L'extractor ho comprova (si una cel·la amb fórmula no té valor, error).
- Ruta amb «ó» de `liquidació`: normalitzar amb `unicodedata.normalize("NFC", …)` i passar sempre la ruta com a argument (problema NFD documentat al traspàs).
- L'extractor **genera una fitxa** del mateix esquema amb `origen: "extractor"` i passa pel mateix validador. Així hi ha un sol camí d'entrada.

#### Canal E — Invertir el flux dels generadors de documents

Els `gen*.js` haurien de llegir les xifres d'un fitxer de dades i no tenir-les escrites. Proposta mínima: `dades\liquidacio_2025.json` (la mateixa fitxa del §1.4) i un helper `eur(v)` que formati `1496005.42` com `1.496.005,42 €`. Aleshores la fitxa alimenta **alhora** els documents i el quadre, i una correcció es fa una sola vegada. No és imprescindible per a la fase 1, però és el pas que elimina la causa del problema del §0.1.

### 1.3 Convencions de dades (obligatòries en tots els canals)

| Convenció | Regla |
|---|---|
| Imports | Número JSON amb punt decimal i exactament 2 decimals, sense separador de milers: `1496005.42`. A Python sempre `Decimal`, mai `float`. A la BD, enters en cèntims |
| Percentatges | En tant per cent amb fins a 4 decimals: `21.2914` (no `0.2129`) |
| Dates | ISO 8601: `2026-09-24` |
| Aplicació pressupostària | Camps separats: `organica` (opcional), `programa` (Ordre EHA/3565/2008, fins a subprograma), `economica` (fins a subconcepte). Mai «1532.61900» en un sol text |
| Valors desconeguts | `null` **i** una entrada a `pendents[]` amb el camp i el motiu. Equivalent al «PENDENT: …» dels documents. Mai un zero inventat |
| Valors calculats | Si Claude calcula una xifra (no la llegeix d'una font), `"calculat": true` i la fórmula a `formula` |
| Traçabilitat | Cada bloc de dades porta `font_ref`: fitxer + full + cel·la, o document + pàgina/annex |
| Signe | Marges i resultats amb el seu signe (marge regla de despesa −176245.38) |

### 1.4 Esquema de dades: la fitxa (`torre-finances/expedient@1`)

#### 1.4.1 Sobre comú

```json
{
  "$fitxa": "torre-finances/expedient@1",
  "entitat": { "nif": "P4315400D" },
  "tipus": "liquidacio",
  "expedient": {
    "num": "4315200000-2026-0000642",
    "exercici": 2025,
    "titol": "Liquidació del pressupost 2025",
    "estat_tramit": "en_tramit",
    "organ": "alcaldia",
    "resolucio": { "num": null, "data": null }
  },
  "font": {
    "origen": "claude_code",
    "sessio": null,
    "generat_el": "2026-09-24T10:30:00+02:00",
    "fitxers": [
      { "ruta": "liquidació/Còpia_comprovacions tancament v14 ABSIS_2025_La Torre (1).xlsx", "sha256": null }
    ]
  },
  "dades": { },
  "pendents": [ ],
  "incoherencies": [ ]
}
```

`tipus` ∈ `liquidacio`, `pressupost`, `modificacio_credit`, `pef`, `operacio_credit`, `tresoreria`, `pmp`, `control_intern`, `compte_general`, `tramesa`.
`estat_tramit` ∈ `esborrany`, `en_tramit`, `aprovat_inicial`, `aprovat`, `publicat`, `executat`, `arxivat`, `anullat`.
`organ` ∈ `alcaldia`, `ple`, `junta_govern` (no hi ha comissió informativa).

Regla d'estat jurídic: `estat_tramit` = `aprovat` exigeix `resolucio.num` i `resolucio.data`. Sense això, tots els fets de la fitxa queden com a `provisional`. (Cas actual: la liquidació 2025 no té número ni data de decret → provisional.)

#### 1.4.2 `dades` per tipus

**a) Liquidació** (art. 191-193 bis TRLRHL; arts. 89-105 RD 500/1990; ICAL; art. 3, 11-13 LOEPSF; art. 53 TRLRHL)

| Bloc | Camps |
|---|---|
| `execucio_ingressos` | `previsions_inicials`, `modificacions`, `previsions_definitives`, `drn`, `recaptacio_neta`, `pendent_cobrament`; opcionalment `per_capitol[]` {capitol, previsions_definitives, drn, recaptacio} |
| `execucio_despeses` | `credits_inicials`, `modificacions`, `credits_definitius`, `autoritzat`, `compromes`, `orn`, `ordenat`, `pagaments`, `pendent_pagament`, `romanents_credit`; `per_capitol[]` |
| `tancats` | `drets_pendents_inici`, `modificacions_drets`, `anul·lacions_drets`, `cancel·lacions`, `recaptacio`, `drets_pendents_final`; igual per a obligacions |
| `resultat_pressupostari` | `operacions_corrents`{drn, orn}, `operacions_capital`{drn, orn}, `actius_financers`, `passius_financers`, `rp`, `ajust_despeses_rtdg`, `ajust_desviacions_negatives`, `ajust_desviacions_positives`, `rp_ajustat` |
| `romanent_tresoreria` | `fons_liquids`, `drets_pendents`{corrent, tancats, no_pressupostaris, cobraments_pendents_aplicacio}, `obligacions_pendents`{corrent, tancats, no_pressupostaries, pagaments_pendents_aplicacio}, `partides_pendents_aplicacio`, `rt_total`, `saldos_dubtos_cobrament`, `exces_financament_afectat`, `rtdg`, `saldo_413`, `saldo_418`, `rtdg_ajustat` |
| `romanents_credit` | `total`, `incorporacio_obligatoria`, `incorporacio_voluntaria`, `no_incorporables` |
| `estabilitat` | `ingressos_no_financers`, `despeses_no_financeres`, `ajustos_sec[]` {concepte, import}, `capacitat_financament` |
| `regla_despesa` | `despesa_computable_n_1`, `taxa_referencia`, `limit_n`, `augments_permanents`, `disminucions_permanents`, `despesa_computable_n`, `marge`, `variacio_interanual_pct` (computable n / computable n−1 − 1), `exces_sobre_limit_pct` (computable n / límit − 1), `compleix` |
| `estalvi_net` | `ingressos_corrents`, `ingressos_extraordinaris`, `ingressos_corrents_ajustats`, `despeses_corrents_1_2_4`, `anualitat_teorica`, `estalvi_net`, `estalvi_net_ajustat` |
| `endeutament` | `deute_viu_llarg`, `deute_viu_curt`, `deute_viu_total`, `ratio_deute_viu_pct` |
| `pmp` | `pmp_dies`, `periode_referencia` |
| `control_intern` | `objeccions`, `omissions_fiscalitzacio`, `anomalies_ingressos`, `pagaments_justificar_pendents`, `bestretes[]` {codi, titular_id, import, estat, antiguitat_anys} |
| `desti_superavit` | `superavit_estabilitat`, `rtdg_ajustat`, `import_amortitzacio`, `import_ifs`, `import_413` |

Els camps `variacio_interanual_pct` i `exces_sobre_limit_pct` separats resolen l'ambigüitat del §0.1.5.

**b) Modificació de crèdit** (arts. 172-182 TRLRHL; arts. 34-51 RD 500/1990; bases d'execució)

```json
"dades": {
  "modalitat": "credit_extraordinari",
  "linies": [
    { "sentit": "alta", "programa": "1532", "economica": "61900", "descripcio": "…", "import": 50000.00 }
  ],
  "recursos": [
    { "tipus": "rtdg", "concepte_ingressos": "87000", "import": 50000.00 }
  ],
  "impacte": {
    "afecta_estabilitat": true, "afecta_regla_despesa": true,
    "informe_estabilitat": "incompliment_previst"
  }
}
```

`modalitat` ∈ `credit_extraordinari` / `suplement` (art. 177; Ple; arts. 35-38 RD 500/1990), `ampliacio` (art. 178), `transferencia` (arts. 179-180), `generacio` (art. 181), `incorporacio` (art. 182; arts. 47-48 RD 500/1990), `baixa_anullacio` (arts. 49-51 RD 500/1990).
`recursos[].tipus` ∈ `rtdg`, `rt_afectat`, `nous_majors_ingressos`, `baixes_anullacio`, `operacio_credit`, `aportacio_compromis_ferm`, `exces_financament_afectat`.
Validació: Σ altes = Σ recursos + Σ baixes (quadrament de l'expedient); un crèdit extraordinari o suplement exigeix `organ: "ple"`; una transferència entre àrees de despesa diferents també és del Ple (llevat de les de capítol 1), segons l'art. 179.2 i les bases.

**c) PEF** (arts. 21 i 23 LOEPSF; art. 116 bis LBRL; art. 9 OM HAP/2105/2012)

| Bloc | Camps |
|---|---|
| `constatacio` | `exercici_incompliment`, `regles_incomplertes[]` (`estabilitat`, `regla_despesa`, `deute`), `data_constatacio` (= aprovació de la liquidació) |
| `quantificacio` | `exces`, `deduccio_rtdg`, `deduccio_exces_afectat`, `import_a_corregir`, `fonament_deduccio` ("RDL 13/2026, art. 4"), `criteri_confirmat_tutela` (bool) |
| `trajectoria[]` | per any: `exercici`, `capacitat_financament`, `despesa_computable`, `limit`, `marge`, `deute_viu_pct`, `es_projeccio` |
| `mesures[]` | `codi`, `descripcio`, `tipus` (ingressos / despeses / no quantificada), `import_anual`, `exercici`, `indicador_seguiment` |
| `tramit` | `data_elaboracio`, `data_ple`, `data_comunicacio_tutela`, `data_publicacio` |

El sistema deriva els terminis de l'art. 23 LOEPSF (presentació en un mes des de la constatació, aprovació en dos mesos des de la presentació, posada en marxa en tres mesos des de la constatació) a partir de `data_constatacio`, i els posa al calendari d'alertes.

**d) Operació de crèdit** (arts. 48-55 TRLRHL; DA 14a RDL 20/2011; art. 48 bis TRLRHL i resolucions de prudència financera; art. 50 RDL 17/2014)

```json
"dades": {
  "classe": "tresoreria",
  "import": 275000.00,
  "termini_mesos": 12,
  "tipus_interes": { "modalitat": "variable", "index": "EURIBOR_12M", "diferencial_pct": null },
  "amortitzacio": "unica_venciment",
  "liquidacio_interessos": "anual",
  "base_ratio": { "ingressos_corrents": 1291602.94, "exercici_base": 2025 },
  "ratio_pct": 21.2914,
  "llindar_competencia_pct": 15, "competencia": "ple", "fonament_competencia": "art. 52.2 TRLRHL; art. 22.2.m LBRL",
  "limit_art51_pct": 30,
  "prudencia": {
    "resolucio": "Resolució de 8/9/2026 (BOE 11/9/2026), annex 1",
    "elegible_fie": false,
    "cost_total_maxim": { "index": "EURIBOR_12M", "diferencial_pct": 0.45, "index_valor_pct": 3.218, "data_index": "2026-09-23", "total_pct": 3.668 },
    "cost_total_maxim_si_regularitza": { "diferencial_pct": 0.20 }
  },
  "delegacio": { "organ_delegat": "alcaldia", "condicio": "TAE <= cost total màxim, acreditat per Intervenció", "data_acord_ple": "2026-09-24" },
  "ofertes": [],
  "formalitzacio": { "data": null, "entitat": null, "tae_pct": null, "venciment": null },
  "comunicacions": [
    { "desti": "tutela_generalitat", "data": null }, { "desti": "ministeri_cir_local", "data": null }
  ]
}
```

`classe` ∈ `tresoreria` (art. 51, fins a un any) / `llarg_termini` (arts. 49, 52-53). Per a les de llarg termini s'hi afegeix `quadre_amortitzacio[]` {data, capital, interessos, capital_viu}, que calcula la `anualitat_teorica` per a l'estalvi net.

**e) Tresoreria i PMP** (art. 187 TRLRHL; RD 635/2014; Llei 15/2010)

- `tresoreria`: `data_tall`, `saldos[]` {compte (5710…/5730…), entitat, import}, `fons_liquids`, `pressupost_tresoreria[]` {mes, cobraments_previstos, pagaments_previstos}, `pla_disposicio_fons` (referència).
- `pmp`: `periode` (`2026-T2`), `ratio_operacions_pagades`, `import_pagat`, `ratio_operacions_pendents`, `import_pendent`, `pmp_dies`, `data_tramesa`.

**f) Control intern** (RD 424/2017; arts. 213-218 TRLRHL)

`informes[]` {tipus: `fiscalitzacio_previa` / `control_financer` / `informe_resum` / `omissio`, num, data, resultat, objeccions[] {motiu, efecte suspensiu (art. 216.2), resolucio_discrepancia (art. 217), data}}.

**g) Tramesa** (per al calendari d'obligacions): `obligacio_codi`, `periode`, `data_tramesa`, `justificant`.

#### 1.4.3 Exemple complet: fitxa de la liquidació 2025 (xifres del traspàs)

```json
{
  "$fitxa": "torre-finances/expedient@1",
  "entitat": { "nif": "P4315400D" },
  "tipus": "liquidacio",
  "expedient": {
    "num": "4315200000-2026-0000642", "exercici": 2025,
    "titol": "Liquidació del pressupost 2025",
    "estat_tramit": "en_tramit", "organ": "alcaldia",
    "resolucio": { "num": null, "data": null }
  },
  "font": {
    "origen": "claude_code", "generat_el": "2026-09-24T10:30:00+02:00",
    "fitxers": [{ "ruta": "liquidació/Còpia_comprovacions tancament v14 ABSIS_2025_La Torre (1).xlsx" }]
  },
  "dades": {
    "execucio_ingressos": { "drn": 3279611.57, "recaptacio_neta": 3091997.30 },
    "execucio_despeses": {
      "credits_inicials": 3400474.50, "modificacions": 296583.25, "credits_definitius": 3697057.75,
      "autoritzat": 3547100.67, "compromes": 3547100.67, "orn": 2337461.47,
      "ordenat": 2234066.47, "pagaments": 2234066.47, "pendent_pagament": 103395.00
    },
    "resultat_pressupostari": {
      "operacions_corrents": { "drn": 1291602.94, "orn": 1199958.30 },
      "operacions_capital": { "drn": 1988008.63, "orn": 1137503.17 },
      "rp": 942150.10,
      "ajust_despeses_rtdg": 105422.08,
      "ajust_desviacions_negatives": 35667.06,
      "ajust_desviacions_positives": 1047593.90,
      "rp_ajustat": 35645.34
    },
    "romanent_tresoreria": {
      "fons_liquids": 1180327.58,
      "drets_pendents_total": 477830.95,
      "obligacions_pendents_total": 162153.11,
      "partides_pendents_aplicacio": 0.00,
      "rt_total": 1496005.42,
      "saldos_dubtos_cobrament": 188636.69,
      "exces_financament_afectat": 1008818.81,
      "rtdg": 298549.92,
      "saldo_413": 4440.58,
      "saldo_418": null,
      "rtdg_ajustat": 294109.34
    },
    "romanents_credit": { "total": 1359596.28, "incorporacio_obligatoria": 1198210.23, "incorporacio_voluntaria": 2408.35 },
    "estabilitat": { "capacitat_financament": 930562.64 },
    "regla_despesa": {
      "taxa_referencia": 3.2, "limit_n": 1003313.10, "despesa_computable_n": 1179558.48,
      "marge": -176245.38, "exces_sobre_limit_pct": 17.57, "variacio_interanual_pct": null, "compleix": false
    },
    "estalvi_net": {
      "ingressos_corrents": 1291602.94, "ingressos_corrents_ajustats": 1291602.94,
      "estalvi_net": 146276.72, "estalvi_net_ajustat": 148624.59
    },
    "endeutament": { "deute_viu_total": 0.00, "ratio_deute_viu_pct": 0.0 },
    "pmp": { "pmp_dies": 10.14 },
    "control_intern": {
      "objeccions": 0, "omissions_fiscalitzacio": 0, "anomalies_ingressos": 0, "pagaments_justificar_pendents": 0,
      "bestretes": [
        { "codi": "2019000002", "import": 200.00, "estat": "pendent_justificar" }
      ],
      "saldos_a_depurar": [
        { "compte": "5741", "import": 800.00, "nota": "600 € d'una bestreta de 2016 fora del llistat" },
        { "compte": "5751", "import": 145.02, "nota": "llum 2016" }
      ]
    }
  },
  "pendents": [
    { "camp": "romanent_tresoreria.saldo_418", "motiu": "Annex 5 = 0,00; estalvi net i superàvit = 215,82. Pendent de confirmar" },
    { "camp": "expedient.resolucio", "motiu": "Falta número i data del decret de liquidació" },
    { "camp": "regla_despesa.variacio_interanual_pct", "motiu": "Cal llegir-la del full LIQ_Regla de la despesa N" },
    { "camp": "annex2.devolucio_ingressos", "motiu": "La cel·la dona #N/A" }
  ],
  "incoherencies": [
    { "descripcio": "RTDG ajustat depèn del saldo 418", "valors": { "418=0": 294109.34, "418=215.82": 293893.52 } }
  ]
}
```

(Els titulars de bestretes no es desen al quadre: només el codi. Vegeu el §2.7.)

#### 1.4.4 Models Pydantic (font única de l'esquema)

L'esquema JSON **no s'escriu a mà**: es genera a partir dels models Pydantic v2 (`Model.model_json_schema()`), i aquest JSON Schema és el que es dona a Claude (a la skill i a l'eina MCP). Així el validador i les instruccions no divergeixen mai.

```python
# quadre/nucli/models.py
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, Field, model_validator

Eur = Annotated[Decimal, Field(max_digits=15, decimal_places=2)]
Pct = Annotated[Decimal, Field(max_digits=9, decimal_places=4)]

EstatTramit = Literal["esborrany", "en_tramit", "aprovat_inicial", "aprovat", "publicat", "executat", "arxivat", "anullat"]

class Resolucio(BaseModel):
    num: str | None = None
    data: date | None = None

class Expedient(BaseModel):
    num: str = Field(pattern=r"^\d{10}-\d{4}-\d{7}$")
    exercici: int = Field(ge=2000, le=2100)
    titol: str
    estat_tramit: EstatTramit
    organ: Literal["alcaldia", "ple", "junta_govern"] | None = None
    resolucio: Resolucio = Resolucio()

    @model_validator(mode="after")
    def aprovat_exigeix_resolucio(self):
        if self.estat_tramit in ("aprovat", "publicat", "executat") and not (self.resolucio.num and self.resolucio.data):
            raise ValueError("Un expedient aprovat ha de tenir número i data de resolució")
        return self

class Pendent(BaseModel):
    camp: str
    motiu: str

class RomanentTresoreria(BaseModel):
    fons_liquids: Eur
    drets_pendents_total: Eur
    obligacions_pendents_total: Eur
    partides_pendents_aplicacio: Eur | None = None
    rt_total: Eur
    saldos_dubtos_cobrament: Eur
    exces_financament_afectat: Eur
    rtdg: Eur
    saldo_413: Eur | None = None
    saldo_418: Eur | None = None
    rtdg_ajustat: Eur | None = None

class DadesLiquidacio(BaseModel):
    resultat_pressupostari: "ResultatPressupostari"
    romanent_tresoreria: RomanentTresoreria
    # … resta de blocs del §1.4.2.a

class Fitxa(BaseModel):
    fitxa: Literal["torre-finances/expedient@1"] = Field(alias="$fitxa")
    entitat: dict
    tipus: Literal["liquidacio", "pressupost", "modificacio_credit", "pef", "operacio_credit",
                   "tresoreria", "pmp", "control_intern", "compte_general", "tramesa"]
    expedient: Expedient
    font: dict
    dades: dict          # es valida després amb el model concret segons `tipus`
    pendents: list[Pendent] = []
    incoherencies: list[dict] = []
```

Els imports es llegeixen amb `json.loads(text, parse_float=Decimal)` perquè cap valor passi per `float`.

### 1.5 Esquema SQL (SQLite)

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ============ Referència ============
CREATE TABLE entitat (
  id INTEGER PRIMARY KEY,
  nif TEXT NOT NULL UNIQUE,
  nom TEXT NOT NULL,
  poblacio INTEGER,
  regim TEXT,                 -- 'comu'
  tutela TEXT                 -- 'generalitat'
);

CREATE TABLE cat_magnitud (          -- catàleg: què és cada xifra
  codi TEXT PRIMARY KEY,             -- 'RT.RTDG_AJ', 'RD.MARGE', 'DEU.RATIO'…
  nom TEXT NOT NULL,
  unitat TEXT NOT NULL CHECK (unitat IN ('eur','pct','dies','nombre')),
  grup TEXT NOT NULL,                -- 'liquidacio','estabilitat','regla_despesa','deute','tresoreria'…
  formula TEXT,                      -- expressió sobre altres codis, per al motor d'identitats
  fonament TEXT                      -- 'art. 191.2 TRLRHL; arts. 101-105 RD 500/1990'
);

CREATE TABLE parametre_normatiu (    -- valors que canvien per any o per norma
  codi TEXT NOT NULL,                -- 'TAXA_REF_RD','LLINDAR_DEUTE_AUTORITZACIO','DIF_FIE_NO_ELEGIBLE'…
  valor TEXT NOT NULL,               -- decimal canònic
  vigent_des_de TEXT NOT NULL,
  vigent_fins TEXT,
  font TEXT NOT NULL,                -- norma o acord
  PRIMARY KEY (codi, vigent_des_de)
);

-- ============ Registre immutable d'entrada ============
CREATE TABLE fitxa (
  id INTEGER PRIMARY KEY,
  sha256 TEXT NOT NULL UNIQUE,       -- hash del JSON canònic: evita duplicats
  esquema TEXT NOT NULL,             -- 'torre-finances/expedient@1'
  tipus TEXT NOT NULL,
  num_expedient TEXT,
  exercici INTEGER NOT NULL,
  origen TEXT NOT NULL CHECK (origen IN ('claude_code','cowork','claude_ai','mcp','extractor','manual')),
  rang_font INTEGER NOT NULL CHECK (rang_font BETWEEN 1 AND 4),
  cos_json TEXT NOT NULL CHECK (json_valid(cos_json)),
  rebuda_el TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  informe_validacio TEXT CHECK (informe_validacio IS NULL OR json_valid(informe_validacio))
);
CREATE TRIGGER fitxa_no_update BEFORE UPDATE ON fitxa
BEGIN SELECT RAISE(ABORT, 'El registre de fitxes és immutable'); END;
CREATE TRIGGER fitxa_no_delete BEFORE DELETE ON fitxa
BEGIN SELECT RAISE(ABORT, 'El registre de fitxes és immutable'); END;

-- ============ Expedients i versions ============
CREATE TABLE expedient (
  id INTEGER PRIMARY KEY,
  entitat_id INTEGER NOT NULL REFERENCES entitat(id),
  num_expedient TEXT NOT NULL UNIQUE,
  tipus TEXT NOT NULL,
  subtipus TEXT,                     -- modalitat de modificació, classe d'operació…
  exercici INTEGER NOT NULL,
  titol TEXT NOT NULL,
  estat_tramit TEXT NOT NULL,
  organ TEXT,
  resolucio_num TEXT,
  resolucio_data TEXT,
  versio_vigent INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE expedient_versio (
  expedient_id INTEGER NOT NULL REFERENCES expedient(id),
  versio INTEGER NOT NULL,
  fitxa_id INTEGER NOT NULL REFERENCES fitxa(id),
  creada_el TEXT NOT NULL,
  resum_canvis TEXT,                 -- diff calculat respecte de la versió anterior
  PRIMARY KEY (expedient_id, versio)
);

CREATE TABLE fita_tramit (           -- línia de temps de l'expedient
  id INTEGER PRIMARY KEY,
  expedient_id INTEGER NOT NULL REFERENCES expedient(id),
  fita TEXT NOT NULL,                -- 'provisio_inici','informe_intervencio','acord_ple','publicacio_bop'…
  data TEXT,
  document TEXT,
  estat TEXT NOT NULL CHECK (estat IN ('pendent','fet','no_escau'))
);

-- ============ Fets (taula central, bitemporal) ============
CREATE TABLE fet (
  id INTEGER PRIMARY KEY,
  entitat_id INTEGER NOT NULL REFERENCES entitat(id),
  exercici INTEGER NOT NULL,
  codi TEXT NOT NULL REFERENCES cat_magnitud(codi),
  data_referencia TEXT NOT NULL,     -- temps vàlid: 2025-12-31 per a la liquidació; data de tall per a tresoreria
  valor_cent INTEGER,                -- per a unitat 'eur' (exacte)
  valor_dec TEXT,                    -- per a 'pct','dies','nombre' (decimal canònic)
  qualitat TEXT NOT NULL CHECK (qualitat IN ('definitiu','provisional','previsio','simulacio')),
  calculat INTEGER NOT NULL DEFAULT 0,
  rang_font INTEGER NOT NULL,
  fitxa_id INTEGER NOT NULL REFERENCES fitxa(id),
  expedient_id INTEGER REFERENCES expedient(id),
  font_ref TEXT,                     -- 'comprovacions v14!LIQ_ANNEXOS I!F42'
  registrat_el TEXT NOT NULL,        -- temps de transacció
  substituit_el TEXT,
  substituit_per INTEGER REFERENCES fet(id),
  CHECK ((valor_cent IS NULL) <> (valor_dec IS NULL))
);
CREATE UNIQUE INDEX fet_un_vigent
  ON fet (entitat_id, exercici, codi, data_referencia, qualitat)
  WHERE substituit_el IS NULL;
CREATE INDEX fet_consulta ON fet (codi, exercici, data_referencia);

CREATE VIEW v_fet_vigent AS
SELECT f.*, c.nom, c.unitat, c.grup
FROM fet f JOIN cat_magnitud c USING (codi)
WHERE f.substituit_el IS NULL AND f.qualitat IN ('definitiu','provisional');

-- ============ Detall per tipus ============
CREATE TABLE mc_linia (              -- modificacions de crèdit
  id INTEGER PRIMARY KEY,
  expedient_id INTEGER NOT NULL REFERENCES expedient(id),
  sentit TEXT NOT NULL CHECK (sentit IN ('alta','baixa')),
  organica TEXT, programa TEXT NOT NULL, economica TEXT NOT NULL,
  descripcio TEXT,
  import_cent INTEGER NOT NULL CHECK (import_cent > 0)
);
CREATE TABLE mc_recurs (
  id INTEGER PRIMARY KEY,
  expedient_id INTEGER NOT NULL REFERENCES expedient(id),
  tipus TEXT NOT NULL,
  concepte_ingressos TEXT,
  import_cent INTEGER NOT NULL CHECK (import_cent > 0)
);

CREATE TABLE operacio_credit (
  id INTEGER PRIMARY KEY,
  expedient_id INTEGER NOT NULL UNIQUE REFERENCES expedient(id),
  classe TEXT NOT NULL CHECK (classe IN ('tresoreria','llarg_termini')),
  import_cent INTEGER NOT NULL,
  termini_mesos INTEGER NOT NULL,
  index_ref TEXT, diferencial_pct TEXT, tae_pct TEXT,
  cost_total_maxim_pct TEXT,
  entitat_financera TEXT,
  data_formalitzacio TEXT, data_venciment TEXT,
  estat TEXT NOT NULL CHECK (estat IN ('projectada','autoritzada','formalitzada','cancel·lada'))
);
CREATE TABLE oc_quadre_amortitzacio (
  operacio_id INTEGER NOT NULL REFERENCES operacio_credit(id),
  data TEXT NOT NULL,
  capital_cent INTEGER NOT NULL, interessos_cent INTEGER NOT NULL, capital_viu_cent INTEGER NOT NULL,
  PRIMARY KEY (operacio_id, data)
);

CREATE TABLE pef_any (
  expedient_id INTEGER NOT NULL REFERENCES expedient(id),
  exercici INTEGER NOT NULL,
  capacitat_cent INTEGER, despesa_computable_cent INTEGER, limit_cent INTEGER,
  es_projeccio INTEGER NOT NULL,
  PRIMARY KEY (expedient_id, exercici)
);
CREATE TABLE pef_mesura (
  id INTEGER PRIMARY KEY,
  expedient_id INTEGER NOT NULL REFERENCES expedient(id),
  codi TEXT NOT NULL, descripcio TEXT NOT NULL, tipus TEXT NOT NULL,
  import_anual_cent INTEGER, exercici INTEGER, indicador TEXT
);

CREATE TABLE saldo_tresoreria (
  data_tall TEXT NOT NULL, compte TEXT NOT NULL, entitat_financera TEXT,
  import_cent INTEGER NOT NULL, fitxa_id INTEGER REFERENCES fitxa(id),
  PRIMARY KEY (data_tall, compte)
);

-- ============ Calendari, alertes i discrepàncies ============
CREATE TABLE obligacio (
  codi TEXT PRIMARY KEY,             -- 'LIQ_MINHAC','EXEC_TRIM','LINIES_FONAMENTALS','CG_PLE','CG_SINDICATURA'…
  descripcio TEXT NOT NULL,
  fonament TEXT NOT NULL,
  regla_termini TEXT NOT NULL,       -- 'anual:03-31:n+1', 'trimestral:+1m', 'relatiu:data_constatacio+1m'…
  desti TEXT                         -- 'MINHAC (Autoriza/plataforma EELL)','EACAT','Sindicatura'…
);
CREATE TABLE obligacio_periode (
  obligacio_codi TEXT NOT NULL REFERENCES obligacio(codi),
  periode TEXT NOT NULL,             -- '2025', '2026-T3'
  venciment TEXT NOT NULL,
  data_compliment TEXT,
  justificant TEXT,
  PRIMARY KEY (obligacio_codi, periode)
);

CREATE TABLE discrepancia (
  id INTEGER PRIMARY KEY,
  codi TEXT NOT NULL, exercici INTEGER NOT NULL,
  fet_a INTEGER NOT NULL REFERENCES fet(id),
  fet_b INTEGER NOT NULL REFERENCES fet(id),
  diferencia_cent INTEGER,
  estat TEXT NOT NULL CHECK (estat IN ('oberta','resolta_a','resolta_b','acceptada')),
  resolucio TEXT, resolta_el TEXT
);

CREATE TABLE alerta (
  id INTEGER PRIMARY KEY,
  regla TEXT NOT NULL,               -- codi de la regla que la genera
  severitat TEXT NOT NULL CHECK (severitat IN ('info','avis','greu','critica')),
  titol TEXT NOT NULL, detall TEXT, fonament TEXT,
  exercici INTEGER, generada_el TEXT NOT NULL, tancada_el TEXT
);

CREATE TABLE registre_auditoria (    -- qui ha fet què
  id INTEGER PRIMARY KEY, moment TEXT NOT NULL, usuari TEXT NOT NULL,
  accio TEXT NOT NULL, objecte TEXT, detall TEXT
);
```

Notes de disseny:
- **Taula de fets + catàleg** (i no una columna per magnitud): quan la norma crea una magnitud nova no cal migrar l'esquema, i tota la sèrie temporal d'una magnitud es consulta igual.
- **Imports en cèntims** (`INTEGER`): les sumes en SQL són exactes. Els percentatges i els dies, com a text decimal canònic.
- **Bitemporalitat**: `data_referencia` (a quina data es refereix la xifra) i `registrat_el` / `substituit_el` (quan el sistema la va conèixer). Consulta «què sabíem el 15/06/2026»: `WHERE registrat_el <= '2026-06-15' AND (substituit_el IS NULL OR substituit_el > '2026-06-15')`.
- Migracions: fitxers `migracions/NNN_descripcio.sql` i `PRAGMA user_version`.

### 1.6 Com instruir Claude perquè emeti la fitxa

Tres peces, de més general a més concreta:

**(1) Una línia al `CLAUDE.md` global** (`C:\Users\secretari\.claude\CLAUDE.md`), perquè s'apliqui a tots els projectes:

```markdown
## Fitxa financera
Quan acabis (o avancis de manera significativa) un expedient econòmic, pressupostari, de tresoreria o de control intern
de l'Ajuntament, aplica la skill `fitxa-financera`: genera la fitxa `torre-finances/expedient@1` i valida-la.
```

**(2) Una skill `fitxa-financera`** (`C:\Users\secretari\.claude\skills\fitxa-financera\SKILL.md`), que conté l'esquema JSON generat, un exemple per tipus i les regles. Nucli de les instruccions:

```markdown
---
name: fitxa-financera
description: Genera i valida la fitxa estructurada (JSON torre-finances/expedient@1) d'un expedient econòmic de
  l'Ajuntament de la Torre de l'Espanyol (liquidació, pressupost, modificació de crèdit, PEF, operació de crèdit,
  tresoreria, PMP, control intern, compte general, trameses). Usa-la en acabar o actualitzar qualsevol d'aquests
  expedients, o quan l'usuari demani «fitxa», «registra-ho al quadre» o «actualitza el quadre».
---

1. Omple la fitxa NOMÉS amb xifres llegides d'una font (Excel ABSIS, document aprovat, llistat) i indica-la a `font_ref`.
   Si calcules una xifra, posa `"calculat": true` i la fórmula. Si no la tens, `null` i una entrada a `pendents`.
   Mai zeros per omissió.
2. Imports: número amb punt decimal i 2 decimals, sense milers (1496005.42). Percentatges en tant per cent (21.2914).
3. Estat: `aprovat` només si hi ha número i data de resolució.
4. Si detectes una incoherència entre fonts, no triïs: posa tots dos valors a `incoherencies`.
5. Claude Code / Cowork: desa-la a C:\Users\secretari\quadre-finances\safata\entrada\<exercici>_<tipus>_<num>_<AAAAMMDD-HHMM>.json
   i executa `C:\Users\secretari\quadre-finances\.venv\Scripts\python.exe -m quadre valida <fitxer>`.
   Corregeix els errors fins que passi. No importis: ho fa l'usuari.
   Si l'eina MCP `registrar_fitxa` està disponible, fes-la servir en lloc del fitxer.
6. claude.ai (sense accés al disc): al final de la resposta, un únic bloc ```json que comenci per
   {"$fitxa": "torre-finances/expedient@1", …}.
7. No posis a la fitxa noms de persones físiques: fes servir codis (bestreta 2019000002, no el titular).
```

**(3) Les instruccions de Projecte de claude.ai**: el mateix text dels punts 1-4, 6 i 7, i l'esquema JSON enganxat com a coneixement del projecte.

Per què una skill i no només un prompt al `CLAUDE.md`: ja feu servir skills (`expedients-ajuntament`, `acta-decret-anunci`), s'activa pel context sense que calgui recordar-ho, i l'esquema (llarg) només es carrega quan cal.

---

## 2. Arquitectura del sistema i stack tècnic

### 2.1 Comparativa d'opcions

| Opció | A favor | En contra | Veredicte |
|---|---|---|---|
| Electron + React | UI rica; app d'escriptori «de veritat» | Toolchain Node/React nou per a vosaltres; instal·lador de 150 MB+; actualitzacions i signatura de codi; la lògica fiscal hauria d'estar en JS o en un procés Python a part | No |
| Tauri + React | Lleuger i segur | Rust + Node; una corba d'aprenentatge que no aporta res a un sol usuari | No |
| Streamlit | MVP molt ràpid | Model de reexecució de tot l'script; control de maquetació i d'impressió limitat; autenticació feble; obligaria a reescriure a la fase 2 | No (a la fase 1, l'HTML estàtic és encara més simple) |
| CustomTkinter / Flet | Natiu, ja el feu servir (nòmines) | Gràfics interactius pobres; no es pot obrir des d'un altre equip | No per al quadre |
| **Python + Flask + SQLite + Plotly (web local)** | **Mateix stack que `expedients-nomines`** (Flask, flask-login, TOTP, openpyxl, python-docx, PyInstaller); nucli Python compartit per CLI, web, MCP i informes; s'obre a Chrome; es pot servir a la LAN o al servidor si cal | Cal un procés local (com ja feu amb les nòmines al port 5003) | **Sí** |
| FastAPI en lloc de Flask | Tipatge i OpenAPI automàtics | Un segon framework per mantenir; Flask ja el domines | Flask |

«Aplicació d'escriptori» es resol com ja ho feu: un `.exe` fet amb PyInstaller (o un `.bat`) que arrenca el servidor local al port **5005** (5002 v2, 5003 beta i 5004 control horari ja estan ocupats) i obre Chrome a `http://127.0.0.1:5005`.

### 2.2 Components

```
                 ┌──────────────── FONTS ────────────────┐
  Excel ABSIS ──►│ Extractors (openpyxl, mapatges YAML)  │
  Claude Code ──►│ Safata d'entrada (JSON)               │
  Cowork/Desktop►│ Servidor MCP finances-torre           │
  claude.ai zip ►│ Parser d'exportació                   │
  Manual ───────►│ Formulari web                         │
                 └───────────────┬───────────────────────┘
                                 ▼  (totes generen una FITXA)
                 ┌───────────────────────────────────────┐
                 │ NUCLI  quadre/nucli (Python pur)       │
                 │  models Pydantic · validador 5 nivells │
                 │  motor d'identitats · regles fiscals   │
                 │  repositori SQLite · calendari        │
                 │  motor d'escenaris (fase 3)            │
                 └───────┬───────────────┬───────────────┘
                         ▼               ▼
      ┌──────────────────────┐   ┌────────────────────────────┐
      │ SQLite finances.db    │   │ Sortides                    │
      │ (fitxes immutables,   │   │  · HTML estàtic (fase 1)    │
      │  fets bitemporals,    │   │  · Web Flask :5005 (fase 2) │
      │  alertes)             │   │  · Informe Word/PDF         │
      └──────────────────────┘   │  · Eines MCP (lectura)      │
                                  └────────────────────────────┘
```

Regla d'or: **tota la lògica fiscal viu al nucli** i té proves automàtiques. La web, el CLI i el MCP són capes primes que la criden.

### 2.3 Estructura del projecte

```
quadre-finances/
├─ quadre/
│  ├─ nucli/
│  │  ├─ models.py            # Pydantic: fitxa i dades per tipus
│  │  ├─ validacio.py         # 5 nivells
│  │  ├─ identitats.py        # RP, RPA, RT, RTDG, marges… (Decimal)
│  │  ├─ regles_fiscals.py    # estabilitat, RD, deute, estalvi net, PMP, límits art. 51-53
│  │  ├─ calendari.py         # obligacions i venciments
│  │  ├─ repositori.py        # accés SQLite, versions, discrepàncies
│  │  └─ escenaris.py         # fase 3
│  ├─ extractors/
│  │  ├─ comprovacions_absis.py
│  │  └─ claude_export.py
│  ├─ web/                    # Flask (fase 2)
│  ├─ informes/               # python-docx amb el format institucional
│  ├─ grafics.py              # figures Plotly (una definició, dues sortides)
│  ├─ mcp_server.py
│  └─ __main__.py             # CLI: valida | importa | extreu | quadre | informe | copia
├─ mapatges/comprovacions_v14.yaml
├─ cataleg/magnituds.yaml     # codi, nom, unitat, fórmula, fonament
├─ cataleg/obligacions.yaml
├─ cataleg/parametres.yaml    # taxes de referència, llindars, diferencials
├─ migracions/001_inicial.sql
├─ safata/{entrada,acceptades,rebutjades}/
├─ vendor/plotly.min.js       # sense CDN
├─ proves/                    # pytest amb xifres reals 2024-2025 com a «valors d'or»
├─ requirements.txt           # versions fixades, com a nòmines
└─ docs/ARQUITECTURA.md
```

La BD va a `C:\Users\secretari\quadre-finances\dades\finances.db` (disc local, **no** OneDrive).

### 2.4 Flux d'importació

```
fitxa JSON ─► [1] parseig (Decimal) ─► [2] hash canònic ─► ja existeix? ─sí─► «duplicat», s'ignora
                                                   │no
                                                   ▼
                                  [3] validació 5 nivells ─ errors ─► rebutjades\ + .err.txt
                                                   │ (pot tenir avisos)
                                                   ▼
                     [4] INSERT fitxa (immutable) · upsert expedient · nova expedient_versio
                                                   ▼
             [5] per cada magnitud: fet vigent existent?
                   · no ─► INSERT fet
                   · sí, igual valor ─► res
                   · sí, diferent i rang_font nou ≤ rang existent ─► substitueix (substituit_el/per)
                   · sí, diferent i rang_font nou > rang existent ─► INSERT discrepancia (oberta) + alerta
                                                   ▼
                            [6] recàlcul d'alertes i regles fiscals ─► acceptades\
```

Tot el pas 4-6 va dins **una sola transacció**: o entra sencera o no entra.

Hash canònic: `json.dumps(fitxa_sense_font_generat_el, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` amb els decimals normalitzats (`1496005.4` i `1496005.40` donen el mateix hash). Excloure `generat_el` fa que la mateixa fitxa emesa dues vegades es reconegui com a duplicada.

### 2.5 Validació en cinc nivells

| Nivell | Què comprova | Resultat si falla | Exemples |
|---|---|---|---|
| 1. Esquema | Tipus, camps obligatoris, formats, enumeracions | Error | Import amb coma; `estat_tramit` desconegut; expedient aprovat sense decret |
| 2. Identitats comptables (tolerància 0,01 €) | Relacions que ha de complir qualsevol liquidació | Error | RP = DRN − ORN · RPA = RP + RTDG aplicat + desv. negatives − desv. positives · RT = fons líquids + drets pendents − obligacions pendents + partides pendents d'aplicació · RTDG = RT − dubtós − excés afectat · RTDG ajustat = RTDG − 413 (− 418 si escau) · marge RD = límit − computable · DRN = Σ capítols · Σ altes MC = Σ recursos |
| 3. Coherència creuada | La mateixa magnitud d'altres fitxes o fonts | Discrepància + avís | Saldo 418: 0,00 vs 215,82 · ingressos corrents de la fitxa de la pòlissa vs els de la liquidació |
| 4. Plausibilitat | Variacions estranyes | Avís | DRN +84,5 % interanual (subvencions de capital: plausible, però s'ha de justificar) · PMP negatiu · ràtio de deute > 100 % sense operacions |
| 5. Estat jurídic i normatiu | Coherència amb el tràmit i la norma | Avís o error | Crèdit extraordinari aprovat per Alcaldia (error) · pòlissa > 15 % sense acord de Ple (error) · PEF sense data de constatació (avís) |

Amb les xifres actuals, el nivell 2 passa en tots els casos del §0.1 **excepte el RT 2024** (−13.432,78), que obligarà a informar les partides pendents d'aplicació d'aquell any; el nivell 3 obrirà la discrepància del 418.

### 2.6 Històric, versionat, duplicats i errors

- **Històric**: la taula `fitxa` no admet UPDATE ni DELETE (triggers). Una correcció és una fitxa nova que genera una versió nova de l'expedient; els fets antics queden marcats com a substituïts, no s'esborren.
- **Versionat d'expedient**: `expedient_versio` guarda quina fitxa correspon a cada versió i un `resum_canvis` calculat (diff camp a camp: «saldo_418: null → 215,82»). A la fitxa de l'expedient es veu la història completa.
- **Duplicats**: exactes, pel hash (s'ignoren en silenci amb un avís al registre); semàntics (mateix expedient i mateixa magnitud amb el mateix valor), s'hi afegeix la font però no un fet nou.
- **Precedència**: rang de font (§1.1) i, dins el mateix rang, la més recent. `definitiu` preval sobre `provisional`.
- **Errors d'importació**: el fitxer va a `rebutjades\` amb un `.err.txt` llegible («Nivell 2 — RT: 1.180.327,58 + 477.830,95 − 162.153,11 = 1.496.005,42 ≠ 1.496.050,42; diferència 45,00 €»).
- **Proves**: els valors d'or 2024 i 2025 es fan servir com a casos de prova de pytest. Cap canvi al nucli s'accepta si les proves no passen.

### 2.7 Privacitat i seguretat

- **Dades**: majoritàriament agregats pressupostaris, que són informació pública un cop aprovats (portal de transparència, Llei 19/2014). Però hi ha **esborranys no aprovats** i algunes **dades personals** (titulars de bestretes, creditors). Criteri de minimització (art. 5.1.c RGPD): el quadre desa codis, no noms. Si cal un nom, es consulta a ABSIS.
- **Sense sortides noves de dades**: tot és local. Claude ja veu aquestes dades als xats; el sistema no n'envia enlloc més. Les llibreries JavaScript es copien a `vendor/` (sense CDN).
- **ENS (RD 311/2022)**: sistema de categoria BÀSICA. Mesures proporcionades: accés amb usuari i TOTP a la fase 2 (reutilitzant el mòdul provat de nòmines, **copiat**, no importat, per no crear dependències amb la beta), registre d'auditoria, BitLocker al disc, còpies xifrades.
- **Xarxa**: el servidor escolta només a `127.0.0.1`. No cal accés extern per a aquest quadre (a diferència de vacances). Si més endavant cal mostrar-lo a l'Alcaldia en un altre equip, es fa amb l'informe PDF o obrint-lo a la LAN amb l'autenticació activada.
- **Còpies de seguretat**: `python -m quadre copia` fa servir l'API de backup de SQLite (còpia coherent encara que la BD estigui oberta) cap a OneDrive i `\\servidor2012\E\ARXIU\quadre-finances\`, amb rotació (7 diàries, 4 setmanals, 12 mensuals). Una tasca programada de Windows ho fa cada dia.
- **Per què no OneDrive per a la BD viva**: OneDrive sincronitza fitxers, no transaccions; amb WAL hi ha tres fitxers (`.db`, `-wal`, `-shm`) que es poden pujar desincronitzats i corrompre la BD.

### 2.8 Instal·lació

```bash
cd C:\Users\secretari\quadre-finances
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m quadre init
```

`requirements.txt` (versions a fixar a la primera instal·lació, com a nòmines): `pydantic`, `openpyxl`, `pyyaml`, `plotly`, `kaleido`, `python-docx`, `flask`, `flask-login`, `flask-wtf`, `pyotp`, `mcp`, `pytest`. LibreOffice ja hi és per al PDF. Kaleido v1 fa servir el Chrome instal·lat per generar les imatges.

---

## 3. Quadre de comandament i visualització

### 3.1 Catàleg de magnituds i KPI

| Codi | Magnitud | Fórmula / definició | Fonament | Llindar / semàfor | 2025 | 2024 |
|---|---|---|---|---|---|---|
| EST.CF | Capacitat (+) / necessitat (−) de finançament | Ingressos no financers (cap. 1-7) − despeses no financeres (cap. 1-7) ± ajustos SEC | Art. 3 i 11 LOEPSF; art. 16 RD 1463/2007 | ≥ 0 verd; < 0 vermell (PEF) | 930.562,64 | 312.979,47 |
| RD.MARGE | Marge de la regla de despesa | Límit − despesa computable | Art. 12 LOEPSF | ≥ 0 verd; < 0 vermell (PEF) | −176.245,38 | +34.809,76 |
| RD.EXCES_PCT | Excés sobre el límit | Computable / límit − 1 | — | ≤ 0 % verd | 17,57 % | — |
| DEU.RATIO | Deute viu / ingressos corrents ajustats | Capital viu curt + llarg / ingressos corrents liquidats ajustats | Art. 53 TRLRHL; DA 14a RDL 20/2011 | < 75 % verd; 75-110 % taronja (autorització de la tutela); > 110 % vermell (prohibit) | 0 % (pro forma amb pòlissa: 21,29 %) | 0 % |
| EN.ESTALVI_NET | Estalvi net (ajustat) | Ingressos corrents − despeses cap. 1, 2 i 4 − anualitat teòrica | Art. 53.1 TRLRHL | > 0 verd; < 0 vermell (autorització) | 148.624,59 | 174.772,91 |
| TES.LIMIT_ART51 | Ús del límit d'operacions de tresoreria | Σ operacions de tresoreria vives / ingressos corrents | Art. 51 TRLRHL | < 30 % | 21,29 % pro forma | 0 % |
| TES.PMP | Període mitjà de pagament | RD 635/2014 | Art. 13.6 LOEPSF | ≤ 30 dies verd | 10,14 | 8,61 |
| LIQ.RPA | Resultat pressupostari ajustat | §2.5 | Arts. 96-97 RD 500/1990 | ≥ 0 | 35.645,34 | 292.891,37 |
| RT.RTDG_AJ | RTDG ajustat | RTDG − 413 (− 418) | Art. 191.2 TRLRHL; DA 6a LOEPSF | > 0; % sobre despesa corrent | 294.109,34 (o 293.893,52) | 321.916,68 |
| RT.PES_AFECTAT | Pes de l'excés afectat sobre el RT | Excés afectat / RT total | — | Informatiu | 67,4 % | 5,4 % |
| RT.COBERTURA_DUBTOS | Cobertura del dubtós cobrament | Dubtós / drets pendents | Art. 193 bis TRLRHL | ≥ mínims legals per antiguitat | 39,5 % | 39,9 % |
| LIQ.EXEC_DESP | Grau d'execució de despeses | ORN / crèdits definitius | ICAL | Informatiu; < 60 % en inversions: avís | 63,2 % | — |
| LIQ.REAL_PAG | Grau de realització de pagaments | Pagaments / ORN | ICAL | > 90 % | 95,6 % | — |
| ROM.COBERTURA_INC | Cobertura de les incorporacions obligatòries | Excés afectat / incorporació obligatòria | Art. 182 TRLRHL; art. 48 RD 500/1990 | < 100 %: la diferència necessita un altre finançament | 84,2 % | — |
| CI.OBJECCIONS | Objeccions i omissions de fiscalització | Recompte | Arts. 215-218 TRLRHL; art. 28 RD 424/2017 | 0 verd | 0 | — |
| CI.SALDOS_DEPURAR | Saldos antics sense aplicar (5741, 5751, bestretes) | Suma i antiguitat | Arts. 69-76 RD 500/1990 | > 0 i > 1 any: avís | 945,02 € + 200 € | — |
| TRAM.RETARD | Trameses vençudes | Recompte i dies de retard | OM HAP/2105/2012 | 0 verd | ≥ 1 (liquidació 2025) | — |

Els % calculats (execució 2.337.461,47 / 3.697.057,75; realització 2.234.066,47 / 2.337.461,47; cobertura 2024 195.810,06 / 490.784,35) es marquen com a `calculat` al sistema.

### 3.2 Vista d'Intervenció (tècnica)

Una pàgina per exercici, amb selector d'exercici i de data de coneixement (bitemporal):

1. **Tauler de les quatre regles** — *bullet chart* per regla: valor, llindar i marge, amb el color del semàfor i el fonament en passar-hi el cursor. És el primer que es veu.
2. **Cascada del resultat pressupostari** — DRN → − ORN → RP → + RTDG aplicat → + desviacions negatives → − desviacions positives → RPA. Mostra com les desviacions positives (1.047.593,90) expliquen la caiguda de 942.150 a 35.645.
3. **Cascada del romanent** — fons líquids → + drets pendents → − obligacions pendents → ± partides pendents → RT → − dubtós → − excés afectat → RTDG → − 413/418 → RTDG ajustat.
4. **Regla de despesa detallada** — cascada base n−1 → × (1 + taxa) → ± canvis normatius → límit, al costat de la computable, i sèrie plurianual computable vs límit. Amb la **descomposició del PEF**: excés 176.245,38 = RTDG 105.422,08 + excés afectat 27.845,49 + **a corregir 42.977,81**.
5. **Trajectòria del PEF** — línia de la projecció 2026-2027 vs l'objectiu, i punts reals trimestrals quan arribin les execucions (seguiment de l'art. 24 LOEPSF).
6. **Discrepàncies obertes** — taula amb els dos valors, les fonts, l'efecte en les magnituds dependents i un botó «resol».
7. **Qualitat de les dades** — per a cada magnitud clau, qualitat (definitiu / provisional), rang de la font i data de l'últim registre. Una xifra provisional es mostra sempre amb una marca visual.
8. **Control intern** — objeccions, omissions, bestretes i saldos a depurar, amb antiguitat; ageing dels drets pendents per any d'origen contra els percentatges mínims de l'art. 193 bis (25 % anys −1 i −2; 50 % −3; 75 % −4 i −5; 100 % anteriors).
9. **Calendari d'obligacions** (§3.4).
10. **Expedients en curs** — línia de temps (Gantt) amb les fites de cada expedient: pòlissa (oferta → informe TAE → decret → donar compte al Ple → BOPT → tutela i CIR Local), PEF, liquidació.

### 3.3 Vista executiva (Alcaldia i Ple)

Llenguatge planer, poques xifres i totes arrodonides, sense perdre el rigor (cada targeta enllaça el detall tècnic):

1. **Quatre semàfors amb una frase**: «Estabilitat: complim, amb 0,93 M€ de marge» · «Regla de despesa: ens hem passat 176.000 €; hem d'aprovar un PEF» · «Deute: zero» · «Pagament a proveïdors: 10 dies (límit 30)».
2. **«Tenim 1,5 milions, però només 0,3 són lliures»** — cascada del romanent simplificada en tres barres (total, afectat a projectes, dubtós). És el gràfic que més ajuda a explicar al Ple per què amb molta caixa es necessita una pòlissa.
3. **Evolució d'ingressos i despeses** — barres per exercici, separant corrents i de capital. Explica que el salt de 2025 (DRN 3,28 M€ vs 1,78 M€) és de capital (subvencions) mentre els ingressos corrents baixen (1,29 vs 1,47 M€).
4. **D'on ve i on va cada euro** — diagrama Sankey: fonts de finançament (impostos, taxes, transferències corrents, subvencions de capital, romanent) → grans àrees de despesa.
5. **Caixa prevista** (fase 3) — saldo mensual previst amb el mínim operatiu i l'efecte de la pòlissa.
6. **Capacitat d'endeutament disponible** — «podríem demanar fins a X € sense autorització», a partir del marge fins al 75 % i de l'estalvi net.
7. **Estat de les inversions** — per projecte: pressupostat, adjudicat, executat, finançament rebut.

### 3.4 Calendari d'obligacions i alertes

Catàleg inicial (`cataleg/obligacions.yaml`). Els terminis són els generals: s'han de revisar un cop amb la normativa vigent i amb la plataforma d'informació de les EELL del Ministeri abans de posar-los en producció.

| Obligació | Termini | Fonament | Estat a 24/09/2026 (a confirmar) |
|---|---|---|---|
| Aprovació de la liquidació | Abans de l'1 de març de n+1 | Art. 191.3 TRLRHL | 2025: sense decret (en tràmit) |
| Tramesa de la liquidació al Ministeri i a la CA | Abans del 31 de març de n+1 | Art. 193.5 TRLRHL; OM HAP/2105/2012 | **2025: vençuda**; efecte: no elegible al FIE |
| Informe resum de control intern (Ple i IGAE) | Primer quadrimestre (30 d'abril) | Art. 37 RD 424/2017 | A comprovar |
| Compte General: Comissió especial / Ple | Abans de l'1 de juny / abans de l'1 d'octubre | Art. 212 TRLRHL | **Ple abans de l'1/10: vençuda en una setmana** |
| Rendició del Compte General a la Sindicatura | Abans del 15 d'octubre | Art. 212.5 TRLRHL | Propera |
| Execució trimestral (Ministeri) | Final del mes següent al trimestre | Art. 16 OM HAP/2105/2012 | 3T: 31/10 |
| PMP i morositat | Trimestral | RD 635/2014; Llei 15/2010 | 3T: octubre |
| Cost efectiu dels serveis | Abans de l'1 de novembre | Art. 116 ter LBRL; OM HAP/2075/2014 | Propera |
| Línies fonamentals del pressupost n+1 | Tardor (vegeu l'OM) | Art. 27.2 LOEPSF; art. 15 OM HAP/2105/2012 | A comprovar |
| Aprovació del pressupost n+1 | Abans del 31 de desembre | Art. 169.2 TRLRHL | 2027 |
| PEF: presentació, aprovació, posada en marxa | 1 mes / 2 mesos / 3 mesos | Art. 23 LOEPSF | Depèn de la data de la liquidació |
| Comunicació d'operacions de crèdit | Després de la formalització | Art. 17 OM HAP/2105/2012; CIR Local | Pòlissa: pendent |
| Informació al Ple de l'execució | La periodicitat de les bases d'execució | Art. 207 TRLRHL | A comprovar |

Regles d'alerta (motor declaratiu, `cataleg/regles.yaml`):

| Regla | Condició | Severitat |
|---|---|---|
| `TRAM_VENCUDA` | venciment < avui i sense compliment | crítica |
| `TRAM_PROPERA` | venciment ≤ 15 dies | avís |
| `RD_INCOMPLIMENT` | RD.MARGE < 0 i sense PEF aprovat | greu |
| `PEF_TERMINI` | terminis de l'art. 23 LOEPSF | greu |
| `DEUTE_75` | DEU.RATIO (real o pro forma) ≥ 75 % | greu |
| `ESTALVI_NEGATIU` | EN.ESTALVI_NET < 0 | greu |
| `PMP_30` | TES.PMP > 30 | greu (retenció de la PIE si persisteix, art. 18.5 LOEPSF) |
| `OPERACIO_TAE` | TAE de l'oferta > cost total màxim vigent | crítica (no es pot adjudicar) |
| `DISCREPANCIA_OBERTA` | discrepància en estat `oberta` > 15 dies | avís |
| `SALDO_ANTIC` | saldo en 5741/5751/555 d'antiguitat > 1 any | avís |
| `DADA_PROVISIONAL_EN_INFORME` | un informe executiu fa servir fets provisionals | avís (marca d'aigua) |

### 3.5 Biblioteques i exportació

- **Plotly** (Python, amb `plotly.min.js` a `vendor/`). Té cascada (`go.Waterfall`), indicadors i bales (`go.Indicator`), Sankey (`go.Sankey`), Gantt (`px.timeline`) i mapes de calor. La mateixa figura es serialitza a JSON per al navegador (`fig.to_json()`) i s'exporta a PNG/SVG per als informes (`fig.write_image`, via kaleido).
- Per què no D3: potència màxima però molt codi a mà per gràfic. Chart.js i Recharts: no tenen cascada ni Sankey nadius, i Recharts obliga a React. ECharts és una bona alternativa, però no genera imatges des de Python sense un navegador extra.
- **Informes**: python-docx amb el format institucional del traspàs (Arial 11, marges de 1418 i 1701 DXA, logo a la capçalera, taula d'expedient, «Pàgina X de Y», signatura «La Torre de l'Espanyol, [data]. / Document signat electrònicament.»), gràfics inserits com a PNG a 200 ppp, i PDF amb `soffice --headless --convert-to pdf`. Dos models: *Informe de situació economicofinancera per al Ple* (vista executiva) i *Nota tècnica d'Intervenció* (vista tècnica).
- **Criteris gràfics**: cap pastís ni 3D; el color només per al semàfor i sempre acompanyat de text o icona (accessibilitat i impressió en blanc i negre); format numèric català (`1.496.005,42 €`, `21,29 %`); cada gràfic amb la font i la data de tall al peu; les xifres provisionals, amb una marca visible.

---

## 4. Full de ruta per fases

### Fase 1 — MVP: «de la fitxa al primer quadre» (2-3 setmanes de sessions curtes)

Objectiu: veure els KPI 2024-2025 validats en un HTML, sense servidor.

| # | Lliurable | Criteri d'acceptació |
|---|---|---|
| 1.1 | Projecte `quadre-finances`, entorn virtual, `requirements.txt` fixat | `python -m quadre --help` funciona |
| 1.2 | Models Pydantic de la fitxa (liquidació, operació de crèdit, PEF, tramesa) i JSON Schema generat | L'esquema es genera sense errors |
| 1.3 | Validador de nivells 1, 2 i 5 + CLI `valida` | Proves pytest amb els valors d'or del §0.1; detecta la diferència del RT 2024 |
| 1.4 | Skill `fitxa-financera` + línia al `CLAUDE.md` global | En una sessió real, Claude escriu la fitxa i la valida sense ajuda |
| 1.5 | Càrrega inicial: fitxes de la liquidació 2024 (Decret 2025-0000144) i 2025, pòlissa, PEF i trameses | Totes a `acceptades\`; la discrepància del 418 apareix oberta |
| 1.6 | SQLite (migració 001) + CLI `importa` amb hash, versions i discrepàncies | Tornar a importar la mateixa fitxa no crea res de nou |
| 1.7 | CLI `quadre` → `sortida\quadre.html` autònom (Plotly inclòs) amb: tauler de regles, cascada RP, cascada RT, regla de despesa + PEF, discrepàncies, calendari | S'obre a Chrome sense xarxa i mostra les alertes del §3.4 |
| 1.8 | `copia` i tasca programada de còpia diària | Hi ha còpia a OneDrive i a ARXIU |

Fora d'abast de la fase 1: web, autenticació, MCP, extractors d'Excel i informes Word.

### Fase 2 — Consolidació i automatització (4-6 setmanes)

| # | Lliurable | Criteri d'acceptació |
|---|---|---|
| 2.1 | Extractor `comprovacions_absis` + mapatge `v14.yaml` | L'extracció de 2025 coincideix al cèntim amb la fitxa manual; si no, discrepància |
| 2.2 | Servidor MCP `finances-torre` (`registrar_fitxa`, `consultar_magnitud`, `estat_financer`) | Des de Claude Code: «quin és el RTDG ajustat 2025?» respon amb el valor, la qualitat i la font |
| 2.3 | Web Flask a 127.0.0.1:5005 amb inici de sessió i TOTP (mòdul copiat de nòmines) | Vistes d'Intervenció i executiva; selector d'exercici i de data de coneixement |
| 2.4 | Mòduls de modificacions de crèdit, tresoreria (saldos) i PMP | Registre de l'estat de modificacions de l'exercici; sèrie del PMP amb el llindar de 30 dies |
| 2.5 | Validació de nivells 3 i 4; pantalla per resoldre discrepàncies | Resoldre el 418 regenera RTDG ajustat i alertes |
| 2.6 | Informes Word/PDF: *situació per al Ple* i *nota tècnica* | Format institucional idèntic al dels documents actuals |
| 2.7 | Parser de l'exportació de claude.ai | Importa les fitxes d'una exportació real |
| 2.8 | Refactor dels `gen*.js` perquè llegeixin `dades\*.json` | Una correcció es fa en un sol lloc |
| 2.9 | Execució pressupostària periòdica a partir de llistats d'ABSIS (execució per aplicació) | Grau d'execució mensual per capítol i programa |

### Fase 3 — Quadre avançat, simulació i control previ (6-8 setmanes)

**3.1 Motor d'escenaris («què passa si…»).** Un escenari és una llista de deltes sobre la base vigent; el motor recalcula totes les regles amb el mateix codi que el quadre real i desa el resultat com a fets amb qualitat `simulacio` (mai es barregen amb els reals). Escenaris inicials:

- *Operació de crèdit*: import, classe, termini, tipus → ràtio de deute (real i pro forma), anualitat teòrica i estalvi net, òrgan competent (llindars de l'art. 52.2 TRLRHL: 10 % dels recursos ordinaris per a les de llarg termini acumulades a l'exercici i 15 % dels ingressos corrents per a les de tresoreria), límit del 30 % de l'art. 51, i si cal autorització de la tutela. Exemple real: 275.000 € → 21,29 %, Ple, dins el 30 %, deute < 75 %.
- *Modificació de crèdit amb RTDG*: efecte en l'estabilitat (necessitat de finançament) i en la regla de despesa (més despesa computable), que és exactament el mecanisme que ha generat l'incompliment de 2025. El simulador ha de dir, abans d'aprovar la modificació, «aquesta modificació consumeix X € de marge de la regla de despesa».
- *Incorporació de romanents*: finançament amb excés afectat vs RTDG i l'efecte en les regles.
- *Tipus d'interès*: sensibilitat del cost de la pòlissa a ±50 / ±100 pb de l'Euribor.

**3.2 Previsió de tresoreria.** Model explicable, no una caixa negra: calendari conegut de cobraments (entregues a compte de la PIE i de la participació de la Generalitat, cobraments de la recaptació delegada, subvencions pendents amb la seva data prevista) i de pagaments (nòmines i SS mensuals, que es poden llegir de l'històric de l'app de nòmines; venciments de factures del registre comptable; amortitzacions), més un component estacional calculat sobre els exercicis anteriors. Resultat: saldo previst mensual amb una banda d'incertesa, el mínim operatiu i les alertes de tensió. Amb poques dades històriques, un model estadístic complex no és més precís i és menys auditable.

**3.3 Control intern previ.** Llista de comprovació dels requisits bàsics de fiscalització limitada prèvia per tipus d'expedient (art. 13 RD 424/2017 i l'acord del Consell de Ministres sobre requisits bàsics, si el Ple l'ha fet aplicable), amb comprovació automàtica del crèdit adequat i suficient al nivell de vinculació (art. 173.5 TRLRHL) a partir de l'execució importada. Registre d'objeccions i discrepàncies (arts. 215-218 TRLRHL) que alimenta automàticament l'informe resum de l'art. 37.

**3.4 Alertes proactives.** Una tasca programada diària recalcula el calendari i les regles i envia un avís (notificació d'escriptori o correu intern, a decidir) només quan hi ha una alerta nova greu o crítica.

**3.5 Preguntes en llenguatge natural via MCP.** Amb l'eina `simular` i les de consulta, des de Claude: «si incorporem 150.000 € amb RTDG, compliríem la regla de despesa el 2026?». Claude fa servir el motor, no calcula de memòria.

---

## 5. Riscos i mitigacions

| Risc | Probabilitat | Impacte | Mitigació |
|---|---|---|---|
| Una xifra errònia generada per Claude entra al quadre | Mitjana | Alt | Font obligatòria, identitats de nivell 2, precedència de l'extractor, marca de «provisional» |
| La plantilla v14 de comprovacions canvia | Alta (anual) | Mitjà | Mapatges versionats; l'extractor falla de manera explícita si una cel·la esperada és buida o no té el rètol esperat |
| Canvis normatius (taxa de referència, llindars, diferencials de prudència) | Alta | Mitjà | `parametre_normatiu` amb vigència; cap llindar escrit al codi |
| Dependència d'una sola persona | Alta | Alt | Aquest document, proves automàtiques, CLI senzill, dades en format obert (SQLite i JSON) |
| Corrupció o pèrdua de la BD | Baixa | Alt | Fora d'OneDrive, còpies diàries a dos llocs, registre immutable (la BD es pot reconstruir reimportant les fitxes acceptades) |
| Ús d'una dada provisional davant el Ple | Mitjana | Alt | Marca d'aigua automàtica i alerta `DADA_PROVISIONAL_EN_INFORME` |
| Sobredisseny | Mitjana | Mitjà | Fase 1 limitada a HTML estàtic; cada fase ha de ser útil per si sola |

---

## 6. Propers passos concrets

1. **Decidir** si s'accepta aquest disseny (sobretot: Python/Flask/SQLite/Plotly i la fitxa `expedient@1`).
2. **Sessió 1**: crear el projecte, els models i el validador, amb les proves dels valors d'or (lliurables 1.1-1.3).
3. **Sessió 2**: skill `fitxa-financera`, fitxes inicials i importació (1.4-1.6).
4. **Sessió 3**: HTML del quadre i còpies (1.7-1.8).
5. En paral·lel, fora del sistema i per la seva urgència: confirmar l'estat del **Compte General 2025** (Ple abans de l'1/10), la **tramesa de la liquidació 2025** i el **saldo 418**, perquè el primer quadre ja surti amb aquestes dades resoltes.
