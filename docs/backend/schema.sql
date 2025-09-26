-- SQLite Schema for Requirements Evaluation Backend
-- Hinweis: Kein Klartext-Requirement im Ruhezustand speichern
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- Table: criterion
CREATE TABLE IF NOT EXISTS criterion (
  key TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  weight REAL NOT NULL DEFAULT 1.0,
  active INTEGER NOT NULL DEFAULT 1
);

-- Table: evaluation
CREATE TABLE IF NOT EXISTS evaluation (
  id TEXT PRIMARY KEY,
  requirement_checksum TEXT NOT NULL,
  model TEXT NOT NULL,
  latency_ms INTEGER,
  score REAL,
  verdict TEXT CHECK (verdict IN ('pass','fail')),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_evaluation_created_at ON evaluation (created_at);
CREATE INDEX IF NOT EXISTS idx_evaluation_checksum ON evaluation (requirement_checksum);

-- Table: evaluation_detail
CREATE TABLE IF NOT EXISTS evaluation_detail (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  evaluation_id TEXT NOT NULL,
  criterion_key TEXT NOT NULL,
  score REAL,
  passed INTEGER NOT NULL,
  feedback TEXT,
  FOREIGN KEY (evaluation_id) REFERENCES evaluation(id) ON DELETE CASCADE,
  FOREIGN KEY (criterion_key) REFERENCES criterion(key)
);

-- Table: suggestion
CREATE TABLE IF NOT EXISTS suggestion (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  evaluation_id TEXT NOT NULL,
  text TEXT NOT NULL,
  priority TEXT,
  FOREIGN KEY (evaluation_id) REFERENCES evaluation(id) ON DELETE CASCADE
);

-- Table: rewritten_requirement
CREATE TABLE IF NOT EXISTS rewritten_requirement (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  evaluation_id TEXT NOT NULL,
  text TEXT NOT NULL,
  FOREIGN KEY (evaluation_id) REFERENCES evaluation(id) ON DELETE CASCADE
);

-- Unique index to ensure one detail row per criterion per evaluation
CREATE UNIQUE INDEX IF NOT EXISTS ux_eval_detail
  ON evaluation_detail(evaluation_id, criterion_key);

-- Table: correction_decision
CREATE TABLE IF NOT EXISTS correction_decision (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  evaluation_id TEXT NOT NULL,
  rewritten_id INTEGER NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('accepted','rejected')),
  decided_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  decided_by TEXT,
  FOREIGN KEY (evaluation_id) REFERENCES evaluation(id) ON DELETE CASCADE,
  FOREIGN KEY (rewritten_id) REFERENCES rewritten_requirement(id) ON DELETE CASCADE
);

-- Unique je Evaluation
CREATE UNIQUE INDEX IF NOT EXISTS ux_correction_decision_eval ON correction_decision(evaluation_id);
COMMIT;

-- Optional: Seed-Daten für Prototyp
-- INSERT OR IGNORE INTO criterion(key, name, description, weight, active) VALUES
--   ('clarity', 'Klarheit', 'Ist die Anforderung eindeutig und verständlich', 0.4, 1),
--   ('testability', 'Testbarkeit', 'Kann die Anforderung verifiziert werden', 0.3, 1),
--   ('measurability', 'Messbarkeit', 'Sind messbare Kriterien definiert', 0.3, 1);