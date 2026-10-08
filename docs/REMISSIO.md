# Obligacions de remissió d'informació — Ajuntament de la Torre de l'Espanyol

Anàlisi feta el 24/09/2026 per al mòdul de remissió del quadre. El catàleg executable és
`cataleg/obligacions.yaml`; aquest document n'explica el perquè.

## 1. Perfil de l'entitat (el que determina les obligacions)

| Característica | Valor | Efecte |
|---|---|---|
| Població | 641 h | **Art. 16.10 OM HAP/2105/2012**: exempt de la informació trimestral dels trimestres 1r a 3r, **excepte** el pla de tresoreria i deute viu (apt. 7) i el PMP (apt. 8). El 4t trimestre s'envia complet |
| Model de finançament | Règim comú, **no** model de cessió (arts. 111 i 135 TRLRHL) | PMP i seguiment trimestrals (no mensuals); el seguiment del PEF de l'art. 9.3 OM no aplica |
| Tutela financera | **Generalitat de Catalunya** (art. 218.5 EAC) | Doble canal: Ministeri (Oficina Virtual EELL) i Generalitat (EACAT). La tutela rep les dades del Ministeri (art. 4.3 OM), però **això no eximeix de les trameses pròpies de l'Ordre ECF/138/2007** |
| Deute viu | 0 € (pòlissa de 275.000 € en tràmit) | En formalitzar-la neixen dues comunicacions noves (CIR Local i CT-0/CT-1) |

## 2. Catàleg

### 2.1 Ministeri d'Hisenda (Oficina Virtual EELL; centralitza la Intervenció, art. 4.1.b OM; signatura electrònica, art. 5)

| Codi | Obligació | Termini (data límit que mostra el quadre) | Fonament |
|---|---|---|---|
| MIN_PLANS_MIG_TERMINI | Plans pressupostaris a mitjà termini | Abans del 15/3 (14/3) | art. 6 OM |
| MIN_LINIES_FONAMENTALS | Línies fonamentals del pressupost n+1 | Abans del 15/9 (14/9) | art. 15.1 OM; art. 27.2 LOEPSF |
| MIN_PRESSUPOST | Pressupost aprovat o prorrogat | Abans del 31/1 (30/1) | art. 15.3 OM |
| MIN_LIQUIDACIO | Liquidació | Abans del 31/3 n+1 (30/3) | art. 15.4 OM; art. 193.5 TRLRHL |
| MIN_COMPTE_GENERAL | Còpia del Compte General | Amb anterioritat al 31/10 n+1 (30/10) | art. 15.5 OM |
| MIN_COST_EFECTIU | Cost efectiu dels serveis | Abans de l'1/11 n+1 (31/10) | art. 15.2 OM; art. 116 ter LBRL |
| MIN_TRIMESTRAL_PMP_TRESORERIA | PMP + pla de tresoreria i deute (T1-T3) | Abans del darrer dia del mes següent | art. 16.7, 16.8, 16.10 OM |
| MIN_TRIMESTRAL_4T | Informació trimestral completa del 4t trimestre | Gener n+1 | art. 16 OM |
| MIN_PEF | PEF aprovat | 5 dies naturals des de l'aprovació | art. 9.2 OM |
| MIN_OPERACIO_ENDEUTAMENT | Formalització, modificació o cancel·lació d'operacions (CIR Local) | 1 mes | art. 17 OM |

Novetat 2026: l'**OM HAC/1518/2025** (en vigor l'1/1/2026) afegeix als plans a mitjà termini, al pressupost i a
la liquidació informació sobre **pasius contingents** (garanties, préstecs dubtosos, catàstrofes i clima) i
participacions en societats.

### 2.2 Generalitat de Catalunya (EACAT)

| Codi | Obligació | Destinatari | Termini | Fonament |
|---|---|---|---|---|
| GEN_PRESSUPOST | Pressupost aprovat o prorrogat, amb modificacions | Presidència (Administració Local), aplicació TIPGAH | 31/3 | art. 169.4 TRLRHL; web «Hisendes locals» |
| GEN_LIQUIDACIO | Liquidació de l'exercici anterior | Presidència, TIPGAH | 31/3 n+1 | art. 193.5 TRLRHL |
| GEN_ESTAT_DEUTE | Estat del deute a 31/12 (ED-0, ED-1, ED-2; formulari 15) | Economia (DGPFAT) | 1r semestre n+1 (30/6) | art. 12 Ordre ECF/138/2007 |
| GEN_OPERACIO_CURT | Operació de tresoreria (CT-0, CT-1) | Economia (DGPFAT) | 10 primers dies del mes següent a la formalització | art. 5.1 Ordre ECF/138/2007 |
| GEN_OPERACIO_LLARG | Operació a llarg termini no subjecta a autorització | Economia (DGPFAT) | 10 primers dies del mes següent | art. 4.1 Ordre ECF/138/2007 |
| GEN_PEF | PEF aprovat | Economia (DGPFAT) | Sense termini a l'Ordre (s'aplica el de 5 dies per analogia) | Ordre ECF/138/2007, annex 2.5 |

Incompliment: **suspensió dels pagaments de subvencions i transferències de la Generalitat** (hi ha un Inventari
públic de compliment per ens).

### 2.3 Òrgans de control extern

| Codi | Obligació | Destinatari | Termini | Fonament |
|---|---|---|---|---|
| SIN_COMPTE_GENERAL | Rendició del Compte General | Sindicatura de Comptes | Abans del 15/10 n+1 (14/10) | art. 212.5 TRLRHL |
| SIN_218_3 | Acords contraris a objeccions, omissions i anomalies d'ingressos (o certificació negativa) | Sindicatura (EACAT) | 30/4 n+1 | art. 218.3 TRLRHL |
| IGAE_INFORME_RESUM | Informe resum del control intern | IGAE (i Ple) | Primer quadrimestre (30/4) | art. 37.2 RD 424/2017 |

### 2.4 Fites internes que condicionen les trameses

Aprovació del pressupost (abans del 31/12), aprovació de la liquidació (abans de l'1/3), Compte General a la
**Comissió Especial de Comptes** (abans de l'1/6) i al Ple (abans de l'1/10), i terminis del PEF (art. 23.1
LOEPSF: presentació en 1 mes i posada en marxa en 3 mesos des de la constatació).

> **Atenció:** la Comissió Especial de Comptes és obligatòria a **tots** els municipis (art. 20.1.e i 116 LBRL),
> encara que l'Ajuntament no tingui comissions informatives. El Compte General no pot anar directament al Ple.

## 3. Situació a 24/09/2026 (segons el quadre, sense constància de cap tramesa)

El quadre no pot saber què s'ha tramès fins que ho registres. Ara mateix marca **12 trameses vençudes sense
constància** i **2 fites internes vençudes**. Les que el traspàs confirma com a pendents són la **liquidació 2025
al Ministeri** (i, per tant, també a la Generalitat) i l'aprovació de la liquidació. Les altres probablement
estan fetes: registra-les amb `python -m quadre remissio marca …` perquè deixin de sortir.

Urgents de veritat:

1. **Compte General 2025 al Ple**: la data límit és el 30/09/2026 (6 dies). Abans hi ha d'haver l'informe de la
   Comissió Especial de Comptes i l'exposició pública (15 dies + 8).
2. **Línies fonamentals 2027**: vençudes el 14/09/2026, si no s'han enviat.
3. **Liquidació 2025**: decret i tramesa. És la causa de la no elegibilitat al FIE (diferencial de +0,45 % en lloc
   de +0,20 % a la pòlissa).
4. **PMP i tresoreria del 3T 2026**: fins al 30/10/2026.
5. **Pòlissa**: quan es formalitzi, CT-0/CT-1 a la Generalitat (10 primers dies del mes següent) i CIR Local (1 mes).
   El quadre ho calcula sol quan s'importa la fitxa amb la data de formalització.

## 4. Criteris i límits

- **Dates conservadores**: «abans del dia X» = el dia anterior. Així una alerta no arriba mai tard.
- **Confiança «mitjana»** (GEN_PRESSUPOST, GEN_LIQUIDACIO, GEN_PEF): terminis presos de la informació web de la
  Generalitat o per analogia. Cal verificar-los cada any a EACAT.
- **Fora del catàleg**, perquè corresponen a Secretaria i no a Intervenció-Tresoreria: relació anual de contractes
  a la Sindicatura (art. 335 LCSP), convenis (art. 53 Llei 40/2015), extractes d'actes (art. 56 LBRL),
  transparència (Llei 19/2014). Es poden afegir al YAML sense tocar codi.

## 5. Fonts consultades

- OM HAP/2105/2012, text consolidat (BOE, actualització 26/12/2025): https://www.boe.es/buscar/act.php?id=BOE-A-2012-12423
- OM HAC/1518/2025, de 22 de desembre: https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-26606
- Ordre ECF/138/2007, text consolidat: https://economia.gencat.cat/web/.content/70_corporacions_locals/arxius/Text-consolidat-de-lOrdre-ECF-138-2007.pdf
- Nota informativa de tutela financera 2026 (DGPFAT): https://economia.gencat.cat/ca/ambits-actuacio/corporacions-locals/normativa-notes-informatives/nota-vigent/
- Hisendes locals (Generalitat): https://web.gencat.cat/ca/ens-locals/serveis-tramits/administracio-local/hisendes-locals
- Sindicatura, informació de control intern: https://www.sindicatura.cat/en/tramesa-informacio-exercici-control-intern
