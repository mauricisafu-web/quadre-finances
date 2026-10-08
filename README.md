# Quadre de comandament financer — Ajuntament de la Torre de l'Espanyol

Aplicació local (Python + SQLite + Plotly) que converteix els expedients econòmics treballats amb Claude en dades
validades, i en genera un quadre de comandament i un calendari de remissió d'informació.

- Arquitectura: [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md)
- Obligacions de remissió: [docs/REMISSIO.md](docs/REMISSIO.md)
- Com connectar-hi els xats de Claude: [docs/PROJECTE_CLAUDE.md](docs/PROJECTE_CLAUDE.md)

## Ús diari

Doble clic a **`Quadre.bat`**: importa el que hi hagi a la safata, regenera el quadre i l'obre amb Chrome.

```bash
.venv\Scripts\python -m quadre importa                 # importa la safata d'entrada
.venv\Scripts\python -m quadre quadre                  # genera sortida\quadre.html i l'obre
.venv\Scripts\python -m quadre estat                   # regles fiscals i alertes, a la consola
.venv\Scripts\python -m quadre remissio                # calendari de trameses (--tots, --ics per a Outlook)
.venv\Scripts\python -m quadre remissio marca MIN_LIQUIDACIO 2025 --data 2026-10-02 --justificant "REG-…"
.venv\Scripts\python -m quadre valida fitxer.json      # valida sense importar
.venv\Scripts\python -m quadre discrepancies           # discrepàncies obertes
.venv\Scripts\python -m quadre copia                   # còpia de seguretat de la BD
.venv\Scripts\python -m pytest proves                  # proves (valors d'or 2024-2025)
```

## Carpetes

| Carpeta | Contingut |
|---|---|
| `safata\entrada` | Fitxes JSON pendents d'importar (hi escriu Claude) |
| `safata\processades`, `safata\rebutjades` | Fitxes ja tractades; les rebutjades porten un `.err.txt` |
| `registre\<exercici>\<tipus>\<expedient>` | Constància de cada expedient: totes les versions + `FITXA.md` |
| `dades\finances.db` | Base de dades (fora d'OneDrive; fes-ne còpies amb `copia`) |
| `sortida` | `quadre.html`, `remissio.ics` |
| `cataleg` | Magnituds, paràmetres normatius i obligacions (YAML editable) |
| `dades_inicials` | Fitxes de càrrega inicial (liquidacions 2024-2025, pòlissa, PEF) |

## Còpies de seguretat

Crea `config.ini` a partir de `config.ini.example` i indica-hi les carpetes de còpia (OneDrive, ARXIU del
servidor). Després programa `Copia.bat` al Programador de tasques de Windows (diari).

## Estat (v0.1, 24/09/2026)

Fet: fase 1 de l'arquitectura (models, validació en 5 nivells, BD bitemporal, importació, registre a carpetes,
quadre HTML amb vista Intervenció/Alcaldia) + mòdul de remissió + servidor MCP (avançat de la fase 2).
Pendent: extractor directe de l'Excel ABSIS, web Flask amb autenticació, informes Word/PDF, simulador d'escenaris.
