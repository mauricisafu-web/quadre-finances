# Com alimentar el quadre des dels xats de Claude

## 1. Valoració de la proposta: «un projecte amb una instrucció que deixi constància en carpetes»

**La idea és bona, però depèn d'on s'executi el xat.**

| On treballes | Pot escriure a les carpetes de l'ordinador? | Per què |
|---|---|---|
| **claude.ai web o app mòbil** (Projectes normals) | **No** | El xat s'executa als servidors d'Anthropic. Una skill pujada a claude.ai s'executa en un entorn aïllat (d'aquí les rutes `/mnt/user-data/outputs` dels vostres scripts): el fitxer es pot descarregar, però no arriba sol a `C:\`. |
| **Claude Desktop — Cowork** | **Sí** | Cowork treballa sobre una carpeta local que tu li autoritzes. |
| **Claude Desktop — xat (també dins d'un Projecte)** amb el servidor MCP local `finances-torre` | **Sí** | El servidor s'executa al teu PC; Claude el crida com una eina. |
| **Claude Code** (aquesta sessió) | **Sí** | Accés directe al disc i a la línia d'ordres. |

**Recomanació (més favorable que la proposta original):**

1. **No facis que Claude decideixi carpetes.** Una instrucció del tipus «desa-ho a la carpeta X segons el tipus
   d'expedient» falla de maneres silencioses: rutes mal escrites, carpetes noves per error, versions
   sobreescrites. En lloc d'això, Claude envia sempre la fitxa a **un sol lloc** (la safata d'entrada, o millor,
   l'eina MCP), la fitxa **es valida en el moment** (si hi ha un error, Claude el veu i el corregeix en el mateix
   xat) i és **l'aplicació** la que arxiva automàticament a:

   ```
   quadre-finances\registre\<exercici>\<tipus>\<expedient>\
       v01_<hash>.json    ← cada versió, immutable
       v02_<hash>.json
       FITXA.md           ← resum llegible: magnituds, pendents, canvis entre versions
   ```

   Així tens les carpetes que volies («que en quedi constància»), però ordenades per la màquina, amb historial i
   sense duplicats.

2. **Treballa els expedients d'Intervenció-Tresoreria en un Projecte de Claude Desktop** (no a claude.ai web),
   amb el servidor MCP `finances-torre` connectat. El Projecte aporta les instruccions i el coneixement comú
   (format de documents, dades de l'Ajuntament); el MCP aporta l'escriptura validada i, a més, la **lectura**: quan
   redactes una modificació de crèdit, Claude pot consultar el RTDG ajustat vigent en lloc de demanar-te'l.

3. **Per als xats que facis des del mòbil o la web**, la fitxa surt com un bloc JSON al final de la resposta; el
   deses a `safata\entrada` i l'importes. És el camí menys còmode, i per això el secundari.

4. **Importar és decisió teva** (`python -m quadre importa`, o el fitxer `Quadre.bat`). Claude escriu a la safata;
   res entra a la base de dades sense que ho vegis.

## 2. Configuració pas a pas

### 2.1 Servidor MCP a Claude Desktop

Claude Desktop → Configuració → Desenvolupador → «Edita la configuració». S'obre `claude_desktop_config.json`.
Afegeix-hi (si ja hi ha una secció `mcpServers`, afegeix només l'entrada `finances-torre`):

```json
{
  "mcpServers": {
    "finances-torre": {
      "command": "C:\\Users\\secretari\\quadre-finances\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\secretari\\quadre-finances\\quadre\\mcp_server.py"]
    }
  }
}
```

Tanca i torna a obrir Claude Desktop. Al xat, a la icona d'eines, hi ha de sortir `finances-torre` amb sis eines:
`esquema_fitxa`, `validar_fitxa`, `registrar_fitxa`, `consultar_magnitud`, `estat_financer`, `obligacions_remissio`.

### 2.2 Servidor MCP a Claude Code

```bash
claude mcp add --scope user finances-torre -- C:\Users\secretari\quadre-finances\.venv\Scripts\python.exe C:\Users\secretari\quadre-finances\quadre\mcp_server.py
```

### 2.3 Projecte «Intervenció i Tresoreria» (Claude Desktop)

Crea el projecte i enganxa això a les **instruccions del projecte**:

```text
Treballo com a secretari-interventor (amb funcions de tresoreria) de l'Ajuntament de la Torre de l'Espanyol.
Tots els expedients d'aquest projecte són econòmics: pressupost, liquidació, modificacions de crèdit, PEF,
operacions de crèdit, tresoreria, PMP, control intern i trameses d'informació.

QUADRE DE COMANDAMENT. Quan acabis o actualitzis de manera significativa un expedient, o quan confirmi una tramesa
d'informació (Ministeri, EACAT, Sindicatura, IGAE), registra'l al quadre:
1. Si tens l'eina `finances-torre`: crida `esquema_fitxa` (si no tens l'esquema), construeix la fitxa i crida
   `registrar_fitxa`. Si retorna errors, corregeix-los i torna-hi fins que sigui vàlida. Explica'm els avisos.
2. Si no tens l'eina: afegeix al final de la resposta un únic bloc ```json amb la fitxa
   {"$fitxa": "torre-finances/expedient@1", ...}.
Regles de la fitxa: només xifres llegides de fonts (indica font_ref); desconegut = null + pendents (mai zeros
inventats); imports amb punt decimal i 2 decimals; percentatges en tant per cent; "aprovat" només amb número i data
de resolució; incoherències entre fonts a "incoherencies" amb tots els valors; cap nom de persona física.

Quan necessitis una xifra ja registrada (RTDG, marge de la regla de despesa, ingressos corrents, PMP…), consulta-la
amb `consultar_magnitud` abans de demanar-me-la, i digues-me si és provisional o definitiva.
```

Al **coneixement del projecte** hi pots pujar `skill\fitxa-financera\SKILL.md` i `skill\fitxa-financera\esquema.json`.

### 2.4 Claude Code i Cowork

La skill `fitxa-financera` s'ha instal·lat a `C:\Users\secretari\.claude\skills\fitxa-financera\` i s'activa sola
quan treballes un expedient econòmic. En Cowork, les instruccions del projecte (2.3) fan la mateixa funció.

## 3. Flux diari

```
Xat (Desktop/Cowork/Code) ──registrar_fitxa──► safata\entrada\*.json  (validada)
                                                  │  Quadre.bat  (o: python -m quadre importa)
                                                  ▼
                                   finances.db  +  registre\<exercici>\<tipus>\<expedient>\
                                                  │
                                                  ▼
                                   sortida\quadre.html  (s'obre amb Chrome)
```
