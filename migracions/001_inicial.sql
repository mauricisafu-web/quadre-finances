-- 001 · Esquema inicial del quadre de comandament financer
-- Imports en cèntims (INTEGER); percentatges i dies com a text decimal canònic.

CREATE TABLE entitat (
  id        INTEGER PRIMARY KEY,
  nif       TEXT NOT NULL UNIQUE,
  nom       TEXT NOT NULL,
  poblacio  INTEGER,
  tutela    TEXT
);

CREATE TABLE cat_magnitud (
  codi      TEXT PRIMARY KEY,
  nom       TEXT NOT NULL,
  unitat    TEXT NOT NULL CHECK (unitat IN ('eur','pct','dies','nombre')),
  grup      TEXT NOT NULL,
  fonament  TEXT
);

-- Registre immutable de totes les fitxes acceptades
CREATE TABLE fitxa (
  id                INTEGER PRIMARY KEY,
  sha256            TEXT NOT NULL UNIQUE,
  esquema           TEXT NOT NULL,
  tipus             TEXT NOT NULL,
  clau_expedient    TEXT NOT NULL,
  exercici          INTEGER NOT NULL,
  origen            TEXT NOT NULL,
  rang_font         INTEGER NOT NULL CHECK (rang_font BETWEEN 1 AND 4),
  fitxer_origen     TEXT,
  cos_json          TEXT NOT NULL CHECK (json_valid(cos_json)),
  informe_validacio TEXT CHECK (informe_validacio IS NULL OR json_valid(informe_validacio)),
  rebuda_el         TEXT NOT NULL
);
CREATE TRIGGER fitxa_no_update BEFORE UPDATE ON fitxa
BEGIN SELECT RAISE(ABORT, 'El registre de fitxes és immutable'); END;
CREATE TRIGGER fitxa_no_delete BEFORE DELETE ON fitxa
BEGIN SELECT RAISE(ABORT, 'El registre de fitxes és immutable'); END;

CREATE TABLE expedient (
  id              INTEGER PRIMARY KEY,
  entitat_id      INTEGER NOT NULL REFERENCES entitat(id),
  clau            TEXT NOT NULL UNIQUE,      -- número del gestor o '<tipus>-<exercici>'
  num_expedient   TEXT,
  tipus           TEXT NOT NULL,
  exercici        INTEGER NOT NULL,
  titol           TEXT NOT NULL,
  estat_tramit    TEXT NOT NULL,
  organ           TEXT,
  resolucio_num   TEXT,
  resolucio_data  TEXT,
  versio_vigent   INTEGER NOT NULL,
  actualitzat_el  TEXT NOT NULL
);

CREATE TABLE expedient_versio (
  expedient_id  INTEGER NOT NULL REFERENCES expedient(id),
  versio        INTEGER NOT NULL,
  fitxa_id      INTEGER NOT NULL REFERENCES fitxa(id),
  creada_el     TEXT NOT NULL,
  resum_canvis  TEXT,
  PRIMARY KEY (expedient_id, versio)
);

-- Fets: taula central, bitemporal (data_referencia = temps vàlid; registrat/substituit = temps de transacció)
CREATE TABLE fet (
  id               INTEGER PRIMARY KEY,
  entitat_id       INTEGER NOT NULL REFERENCES entitat(id),
  exercici         INTEGER NOT NULL,
  codi             TEXT NOT NULL REFERENCES cat_magnitud(codi),
  data_referencia  TEXT NOT NULL,
  valor_cent       INTEGER,
  valor_dec        TEXT,
  qualitat         TEXT NOT NULL CHECK (qualitat IN ('definitiu','provisional','previsio','simulacio')),
  calculat         INTEGER NOT NULL DEFAULT 0,
  rang_font        INTEGER NOT NULL,
  fitxa_id         INTEGER NOT NULL REFERENCES fitxa(id),
  expedient_id     INTEGER REFERENCES expedient(id),
  font_ref         TEXT,
  registrat_el     TEXT NOT NULL,
  substituit_el    TEXT,
  substituit_per   INTEGER REFERENCES fet(id),
  CHECK ((valor_cent IS NULL) <> (valor_dec IS NULL))
);
CREATE UNIQUE INDEX fet_un_vigent ON fet (entitat_id, exercici, codi, data_referencia, qualitat)
  WHERE substituit_el IS NULL AND qualitat IN ('previsio','simulacio');
CREATE UNIQUE INDEX fet_un_real_vigent ON fet (entitat_id, exercici, codi, data_referencia)
  WHERE substituit_el IS NULL AND qualitat IN ('definitiu','provisional');
CREATE INDEX fet_consulta ON fet (codi, exercici, data_referencia);

CREATE TABLE discrepancia (
  id            INTEGER PRIMARY KEY,
  codi          TEXT,                 -- magnitud (si se'n pot identificar)
  camp          TEXT,                 -- ruta del camp a la fitxa
  exercici      INTEGER,
  descripcio    TEXT NOT NULL,
  valors_json   TEXT NOT NULL CHECK (json_valid(valors_json)),
  origen        TEXT NOT NULL CHECK (origen IN ('declarada','creuada','precedencia')),
  expedient_id  INTEGER REFERENCES expedient(id),
  fitxa_id      INTEGER REFERENCES fitxa(id),
  estat         TEXT NOT NULL CHECK (estat IN ('oberta','resolta','acceptada','resolta_nova_versio','resolta_per_precedencia')),
  resolucio     TEXT,
  oberta_el     TEXT NOT NULL,
  tancada_el    TEXT
);

CREATE TABLE operacio_credit (
  expedient_id          INTEGER PRIMARY KEY REFERENCES expedient(id),
  classe                TEXT NOT NULL,
  import_cent           INTEGER NOT NULL,
  termini_mesos         INTEGER NOT NULL,
  ratio_pct             TEXT,
  cost_total_maxim_pct  TEXT,
  entitat_financera     TEXT,
  data_formalitzacio    TEXT,
  data_venciment        TEXT,
  tae_pct               TEXT,
  estat                 TEXT NOT NULL
);

-- Compliment de les obligacions de remissió (alimentat per fitxes de tipus 'tramesa')
CREATE TABLE compliment (
  obligacio      TEXT NOT NULL,
  periode        TEXT NOT NULL,
  estat          TEXT NOT NULL CHECK (estat IN ('tramesa','no_escau')),
  data_tramesa   TEXT,
  justificant    TEXT,
  observacions   TEXT,
  fitxa_id       INTEGER NOT NULL REFERENCES fitxa(id),
  registrat_el   TEXT NOT NULL,
  PRIMARY KEY (obligacio, periode)
);

CREATE TABLE registre_auditoria (
  id       INTEGER PRIMARY KEY,
  moment   TEXT NOT NULL,
  usuari   TEXT NOT NULL,
  accio    TEXT NOT NULL,
  objecte  TEXT,
  detall   TEXT
);
