# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import os, json

from . import settings

DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS criterion (
  key TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  weight REAL NOT NULL DEFAULT 1.0,
  active INTEGER NOT NULL DEFAULT 1
);

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

-- Sichert pro Evaluation nur eine Zeile je Kriterium
CREATE UNIQUE INDEX IF NOT EXISTS ux_eval_detail ON evaluation_detail (evaluation_id, criterion_key);

CREATE TABLE IF NOT EXISTS suggestion (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  evaluation_id TEXT NOT NULL,
  text TEXT NOT NULL,
  priority TEXT,
  FOREIGN KEY (evaluation_id) REFERENCES evaluation(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rewritten_requirement (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  evaluation_id TEXT NOT NULL,
  text TEXT NOT NULL,
  FOREIGN KEY (evaluation_id) REFERENCES evaluation(id) ON DELETE CASCADE
);

-- Entscheidung des Nutzers zu einer Korrektur (Accept/Reject)
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
"""


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.SQLITE_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema_migrations(conn: sqlite3.Connection) -> None:
    """
    Idempotente Migrationen für bestehende Datenbanken.
    - Erzwingt UNIQUE-Index für evaluation_detail(evaluation_id, criterion_key)
    - Legt correction_decision an, falls nicht vorhanden
    """
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_eval_detail ON evaluation_detail (evaluation_id, criterion_key)")
    except Exception:
        pass
    try:
        conn.execute("""
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
        -- Genau eine Entscheidung je Evaluation
        CREATE UNIQUE INDEX IF NOT EXISTS ux_correction_decision_eval ON correction_decision (evaluation_id);
        """)
    except Exception:
        pass


def purge_old_evaluations(conn: sqlite3.Connection, retention_h: int) -> None:
    try:
        cutoff = datetime.utcnow() - timedelta(hours=retention_h)
        conn.execute(
            "DELETE FROM evaluation WHERE datetime(created_at) < datetime(?)",
            (cutoff.isoformat(),),
        )
        # ON DELETE CASCADE säubert verbundene Tabellen
    except Exception:
        pass


def init_db() -> None:
    conn = get_db()
    with conn:
        conn.executescript(DDL)
        try:
            ensure_schema_migrations(conn)
        except Exception:
            pass

        cur = conn.execute("SELECT COUNT(*) AS c FROM criterion")
        c = cur.fetchone()["c"]
        if c == 0:
            conn.executemany(
                "INSERT INTO criterion(key, name, description, weight, active) VALUES (?, ?, ?, ?, ?)",
                [
                    ("clarity", "Klarheit", "Ist die Anforderung eindeutig und verständlich", 0.4, 1),
                    ("testability", "Testbarkeit", "Kann die Anforderung verifiziert werden", 0.3, 1),
                    ("measurability", "Messbarkeit", "Sind messbare Kriterien definiert", 0.3, 1),
                ],
            )

        # Konfigurierbare Kriterien aus Datei übernehmen (Upsert)
        _apply_criteria_config(conn)

        purge_old_evaluations(conn, settings.PURGE_RETENTION_H)


def load_criteria(conn: sqlite3.Connection, keys: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    if keys:
        q = "SELECT key, name, description, weight, active FROM criterion WHERE active = 1 AND key IN ({})".format(
            ",".join("?" * len(keys))
        )
        rows = conn.execute(q, keys).fetchall()
    else:
        rows = conn.execute(
            "SELECT key, name, description, weight, active FROM criterion WHERE active = 1"
        ).fetchall()
    return [dict(r) for r in rows]


def get_latest_evaluation_by_checksum(conn: sqlite3.Connection, checksum: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT id, requirement_checksum, model, latency_ms, score, verdict, created_at FROM evaluation WHERE requirement_checksum = ? ORDER BY datetime(created_at) DESC LIMIT 1",
        (checksum,),
    ).fetchone()


def get_suggestions_for_eval(conn: sqlite3.Connection, evaluation_id: str):
    return conn.execute(
        "SELECT id, text, priority FROM suggestion WHERE evaluation_id = ? ORDER BY id ASC",
        (evaluation_id,),
    ).fetchall()


def get_latest_rewrite_for_eval(conn: sqlite3.Connection, evaluation_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT text FROM rewritten_requirement WHERE evaluation_id = ? ORDER BY id DESC LIMIT 1",
        (evaluation_id,),
    ).fetchone()
    return row["text"] if row else None

def get_latest_rewrite_row_for_eval(conn: sqlite3.Connection, evaluation_id: str) -> Optional[sqlite3.Row]:
    """
    Liefert die jüngste Umschreibung als Row mit id und text.
    """
    return conn.execute(
        "SELECT id, text FROM rewritten_requirement WHERE evaluation_id = ? ORDER BY id DESC LIMIT 1",
        (evaluation_id,),
    ).fetchone()
def _apply_criteria_config(conn: sqlite3.Connection) -> None:
    """
    Optional: Kriterien aus JSON-Datei laden und in Tabelle criterion upserten.
    Format: [
      { "key": "clarity", "name": "Klarheit", "description": "...", "weight": 0.4, "active": true },
      ...
    ]
    """
    path = settings.CRITERIA_CONFIG_PATH
    try:
        if not path or not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return
        for item in data:
            key = str(item.get("key", "")).strip()
            if not key:
                continue
            name = str(item.get("name", "")).strip() or key
            desc = str(item.get("description", "")).strip()
            try:
                weight = float(item.get("weight", 1.0))
            except Exception:
                weight = 1.0
            active = 1 if bool(item.get("active", True)) else 0
            conn.execute(
                """
                INSERT INTO criterion(key, name, description, weight, active)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  name=excluded.name,
                  description=excluded.description,
                  weight=excluded.weight,
                  active=excluded.active
                """,
                (key, name, desc, weight, active),
            )
    except Exception:
        # Konfig ist optional; Fehler hier sollen den Start nicht verhindern
        pass