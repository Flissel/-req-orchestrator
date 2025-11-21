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

-- =============================================================================
-- MANIFEST SYSTEM: Full requirement lifecycle tracking
-- =============================================================================

-- Main manifest table: tracks requirement from source to final state
CREATE TABLE IF NOT EXISTS requirement_manifest (
  requirement_id TEXT PRIMARY KEY,                -- Stable ID format: REQ-{sha1[:6]}-{chunk:03d}
  requirement_checksum TEXT NOT NULL,             -- SHA256 of current text
  source_type TEXT NOT NULL CHECK (source_type IN ('upload','manual','chunk_miner','api','atomic_split')),
  source_file TEXT,                               -- Original filename
  source_file_sha1 TEXT,                          -- Document hash (from ChunkMiner)
  chunk_index INTEGER,                            -- Position in chunked document
  original_text TEXT NOT NULL,                    -- Initial raw requirement text
  current_text TEXT NOT NULL,                     -- Latest version after processing
  current_stage TEXT,                             -- Latest processing stage name
  parent_id TEXT,                                 -- For split requirements (links to parent)
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  metadata TEXT,                                  -- JSON: additional context, tags, etc.
  FOREIGN KEY (parent_id) REFERENCES requirement_manifest(requirement_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_manifest_checksum ON requirement_manifest (requirement_checksum);
CREATE INDEX IF NOT EXISTS idx_manifest_source ON requirement_manifest (source_type, source_file);
CREATE INDEX IF NOT EXISTS idx_manifest_parent ON requirement_manifest (parent_id);
CREATE INDEX IF NOT EXISTS idx_manifest_created ON requirement_manifest (created_at);

-- Processing stage timeline: records each processing step
CREATE TABLE IF NOT EXISTS processing_stage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  requirement_id TEXT NOT NULL,
  stage_name TEXT NOT NULL CHECK (stage_name IN ('input','mining','evaluation','atomicity','suggestion','rewrite','validation','completed','failed','fix_clarity','fix_testability','fix_measurability','fix_atomic','fix_concise','fix_unambiguous','fix_consistent_language','fix_design_independent','fix_purpose_independent')),
  status TEXT NOT NULL CHECK (status IN ('pending','in_progress','completed','failed')),
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME,
  evaluation_id TEXT,                             -- Link to evaluation table
  score REAL,                                     -- Overall score for this stage
  verdict TEXT,                                   -- pass/fail verdict
  atomic_score REAL,                              -- Specific to atomicity stage
  was_split INTEGER DEFAULT 0,                    -- Boolean: was requirement split in this stage
  model_used TEXT,                                -- LLM model (e.g., gpt-4o-mini)
  latency_ms INTEGER,                             -- Processing time in milliseconds
  token_usage TEXT,                               -- JSON: {prompt_tokens, completion_tokens, total_tokens}
  error_message TEXT,                             -- Error details if status=failed
  stage_metadata TEXT,                            -- JSON: stage-specific additional data
  FOREIGN KEY (requirement_id) REFERENCES requirement_manifest(requirement_id) ON DELETE CASCADE,
  FOREIGN KEY (evaluation_id) REFERENCES evaluation(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_stage_requirement ON processing_stage (requirement_id, stage_name);
CREATE INDEX IF NOT EXISTS idx_stage_status ON processing_stage (status);
CREATE INDEX IF NOT EXISTS idx_stage_started ON processing_stage (started_at);

-- Evidence references: tracks source documents and chunk positions
CREATE TABLE IF NOT EXISTS evidence_reference (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  requirement_id TEXT NOT NULL,
  source_file TEXT,                               -- Filename of source document
  sha1 TEXT,                                      -- SHA1 hash of source document
  chunk_index INTEGER,                            -- Position in chunked document (0-based)
  is_neighbor INTEGER DEFAULT 0,                  -- Boolean: is this ±1 neighbor context chunk
  evidence_metadata TEXT,                         -- JSON: additional evidence data
  FOREIGN KEY (requirement_id) REFERENCES requirement_manifest(requirement_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_evidence_requirement ON evidence_reference (requirement_id);
CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence_reference (source_file, sha1, chunk_index);

-- Split relationships: tracks parent-child relationships when AtomicityAgent splits requirements
CREATE TABLE IF NOT EXISTS requirement_split (
  parent_id TEXT NOT NULL,
  child_id TEXT NOT NULL,
  split_rationale TEXT,                           -- Explanation for why requirement was split
  split_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  split_model TEXT,                               -- Model used for splitting (e.g., gpt-4o-mini)
  PRIMARY KEY (parent_id, child_id),
  FOREIGN KEY (parent_id) REFERENCES requirement_manifest(requirement_id) ON DELETE CASCADE,
  FOREIGN KEY (child_id) REFERENCES requirement_manifest(requirement_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_split_parent ON requirement_split (parent_id);
CREATE INDEX IF NOT EXISTS idx_split_child ON requirement_split (child_id);

-- =============================================================================
-- VALIDATION HISTORY: Tracks automatic validation workflow (RequirementOrchestrator)
-- =============================================================================

-- Main validation session table
CREATE TABLE IF NOT EXISTS validation_history (
  id TEXT PRIMARY KEY,                            -- Unique session ID
  requirement_id TEXT NOT NULL,
  session_id TEXT,                                -- SSE session ID for tracking
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME,
  initial_text TEXT NOT NULL,                     -- Requirement text before validation
  final_text TEXT,                                -- Requirement text after validation
  initial_score REAL,                             -- Overall score before validation
  final_score REAL,                               -- Overall score after validation
  passed INTEGER DEFAULT 0,                       -- Boolean: did validation pass threshold
  threshold REAL NOT NULL DEFAULT 0.7,            -- Quality threshold used
  max_iterations INTEGER NOT NULL DEFAULT 3,      -- Maximum iterations allowed
  total_iterations INTEGER DEFAULT 0,             -- Actual iterations performed
  total_fixes INTEGER DEFAULT 0,                  -- Total criterion fixes applied
  split_occurred INTEGER DEFAULT 0,               -- Boolean: was requirement split
  model_used TEXT,                                -- LLM model (e.g., gpt-4o-mini)
  total_latency_ms INTEGER,                       -- Total processing time
  error_message TEXT,                             -- Error details if failed
  metadata TEXT,                                  -- JSON: additional session data
  FOREIGN KEY (requirement_id) REFERENCES requirement_manifest(requirement_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_validation_history_req ON validation_history (requirement_id);
CREATE INDEX IF NOT EXISTS idx_validation_history_session ON validation_history (session_id);
CREATE INDEX IF NOT EXISTS idx_validation_history_started ON validation_history (started_at);

-- Validation iteration details
CREATE TABLE IF NOT EXISTS validation_iteration (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  validation_id TEXT NOT NULL,
  iteration_number INTEGER NOT NULL,
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME,
  requirement_text TEXT NOT NULL,                 -- Text at start of this iteration
  overall_score REAL,                             -- Overall score for this iteration
  fixes_applied INTEGER DEFAULT 0,                -- Number of criterion fixes in this iteration
  split_occurred INTEGER DEFAULT 0,               -- Boolean: did split occur in this iteration
  split_children_count INTEGER,                   -- Number of children created if split
  iteration_metadata TEXT,                        -- JSON: {failing_criteria, scores_before, scores_after}
  FOREIGN KEY (validation_id) REFERENCES validation_history(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_validation_iter_val ON validation_iteration (validation_id);
CREATE INDEX IF NOT EXISTS idx_validation_iter_num ON validation_iteration (validation_id, iteration_number);

-- Criterion-level fix details
CREATE TABLE IF NOT EXISTS validation_criterion_fix (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  validation_id TEXT NOT NULL,
  iteration_id INTEGER NOT NULL,
  criterion TEXT NOT NULL,                        -- Criterion name (e.g., clarity, testability)
  applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  old_text TEXT NOT NULL,                         -- Requirement text before fix
  new_text TEXT NOT NULL,                         -- Requirement text after fix
  score_before REAL NOT NULL,                     -- Criterion score before fix
  score_after REAL NOT NULL,                      -- Criterion score after fix
  improvement REAL NOT NULL,                      -- score_after - score_before
  suggestion TEXT,                                -- Fix suggestion text
  model_used TEXT,                                -- LLM model used for this fix
  latency_ms INTEGER,                             -- Time taken for this fix
  FOREIGN KEY (validation_id) REFERENCES validation_history(id) ON DELETE CASCADE,
  FOREIGN KEY (iteration_id) REFERENCES validation_iteration(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_validation_fix_val ON validation_criterion_fix (validation_id);
CREATE INDEX IF NOT EXISTS idx_validation_fix_iter ON validation_criterion_fix (iteration_id);
CREATE INDEX IF NOT EXISTS idx_validation_fix_criterion ON validation_criterion_fix (criterion);

-- Criterion scores at each iteration
CREATE TABLE IF NOT EXISTS validation_criterion_score (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  validation_id TEXT NOT NULL,
  iteration_id INTEGER NOT NULL,
  criterion TEXT NOT NULL,                        -- Criterion name
  score REAL NOT NULL,                            -- Score for this criterion
  passed INTEGER NOT NULL,                        -- Boolean: did criterion pass threshold
  FOREIGN KEY (validation_id) REFERENCES validation_history(id) ON DELETE CASCADE,
  FOREIGN KEY (iteration_id) REFERENCES validation_iteration(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_validation_score ON validation_criterion_score (iteration_id, criterion);
CREATE INDEX IF NOT EXISTS idx_validation_score_val ON validation_criterion_score (validation_id);
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
    - Fügt 'atomic_split' zu source_type CHECK constraint hinzu
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

    # Migration: Add 'atomic_split' to source_type CHECK constraint
    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table if needed
    try:
        # Check if atomic_split is already allowed by trying to insert one
        cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='requirement_manifest'")
        table_sql = cursor.fetchone()
        if table_sql and "'atomic_split'" not in table_sql[0]:
            # Need to recreate table with new constraint
            conn.executescript("""
                -- Create temporary table with new schema
                CREATE TABLE requirement_manifest_new (
                  requirement_id TEXT PRIMARY KEY,
                  requirement_checksum TEXT NOT NULL,
                  source_type TEXT NOT NULL CHECK (source_type IN ('upload','manual','chunk_miner','api','atomic_split')),
                  source_file TEXT,
                  source_file_sha1 TEXT,
                  chunk_index INTEGER,
                  original_text TEXT NOT NULL,
                  current_text TEXT NOT NULL,
                  current_stage TEXT NOT NULL DEFAULT 'input',
                  parent_id TEXT,
                  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  metadata TEXT DEFAULT '{}'
                );

                -- Copy data
                INSERT INTO requirement_manifest_new SELECT * FROM requirement_manifest;

                -- Drop old table
                DROP TABLE requirement_manifest;

                -- Rename new table
                ALTER TABLE requirement_manifest_new RENAME TO requirement_manifest;

                -- Recreate indexes
                CREATE INDEX IF NOT EXISTS idx_manifest_source ON requirement_manifest (source_type, source_file);
                CREATE INDEX IF NOT EXISTS idx_manifest_stage ON requirement_manifest (current_stage);
                CREATE INDEX IF NOT EXISTS idx_manifest_parent ON requirement_manifest (parent_id);
            """)
    except Exception as e:
        # Migration may fail if table doesn't exist yet or if already migrated
        # This is okay - table will be created with correct schema via DDL
        import logging
        logging.getLogger(__name__).debug(f"source_type migration skipped: {e}")


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


# =============================================================================
# MANIFEST SYSTEM: Helper functions
# =============================================================================

def get_manifest_by_id(conn: sqlite3.Connection, requirement_id: str) -> Optional[sqlite3.Row]:
    """Retrieve manifest by requirement_id"""
    return conn.execute(
        """
        SELECT requirement_id, requirement_checksum, source_type, source_file,
               source_file_sha1, chunk_index, original_text, current_text,
               current_stage, parent_id, created_at, updated_at, metadata
        FROM requirement_manifest
        WHERE requirement_id = ?
        """,
        (requirement_id,),
    ).fetchone()


def get_manifest_by_checksum(conn: sqlite3.Connection, checksum: str) -> Optional[sqlite3.Row]:
    """Retrieve manifest by current text checksum"""
    return conn.execute(
        """
        SELECT requirement_id, requirement_checksum, source_type, source_file,
               source_file_sha1, chunk_index, original_text, current_text,
               current_stage, parent_id, created_at, updated_at, metadata
        FROM requirement_manifest
        WHERE requirement_checksum = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (checksum,),
    ).fetchone()


def get_processing_stages(conn: sqlite3.Connection, requirement_id: str) -> List[sqlite3.Row]:
    """Get all processing stages for a requirement, ordered chronologically"""
    return conn.execute(
        """
        SELECT id, requirement_id, stage_name, status, started_at, completed_at,
               evaluation_id, score, verdict, atomic_score, was_split,
               model_used, latency_ms, token_usage, error_message, stage_metadata
        FROM processing_stage
        WHERE requirement_id = ?
        ORDER BY started_at ASC
        """,
        (requirement_id,),
    ).fetchall()


def get_evidence_refs(conn: sqlite3.Connection, requirement_id: str) -> List[sqlite3.Row]:
    """Get all evidence references for a requirement"""
    return conn.execute(
        """
        SELECT id, requirement_id, source_file, sha1, chunk_index,
               is_neighbor, evidence_metadata
        FROM evidence_reference
        WHERE requirement_id = ?
        ORDER BY chunk_index ASC, is_neighbor ASC
        """,
        (requirement_id,),
    ).fetchall()


def get_split_children(conn: sqlite3.Connection, parent_id: str) -> List[sqlite3.Row]:
    """Get all child requirements created from splitting a parent"""
    return conn.execute(
        """
        SELECT rs.child_id, rs.split_rationale, rs.split_timestamp, rs.split_model,
               rm.current_text, rm.current_stage
        FROM requirement_split rs
        JOIN requirement_manifest rm ON rs.child_id = rm.requirement_id
        WHERE rs.parent_id = ?
        ORDER BY rs.split_timestamp ASC
        """,
        (parent_id,),
    ).fetchall()


def get_split_parent(conn: sqlite3.Connection, child_id: str) -> Optional[sqlite3.Row]:
    """Get the parent requirement that was split to create this child"""
    return conn.execute(
        """
        SELECT rs.parent_id, rs.split_rationale, rs.split_timestamp, rs.split_model,
               rm.original_text, rm.current_stage
        FROM requirement_split rs
        JOIN requirement_manifest rm ON rs.parent_id = rm.requirement_id
        WHERE rs.child_id = ?
        """,
        (child_id,),
    ).fetchone()


def create_manifest(
    conn: sqlite3.Connection,
    requirement_id: str,
    requirement_text: str,
    checksum: str,
    source_type: str,
    source_file: Optional[str] = None,
    source_file_sha1: Optional[str] = None,
    chunk_index: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a new requirement manifest.
    Returns the requirement_id.
    """
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

    conn.execute(
        """
        INSERT INTO requirement_manifest
        (requirement_id, requirement_checksum, source_type, source_file,
         source_file_sha1, chunk_index, original_text, current_text, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            requirement_id,
            checksum,
            source_type,
            source_file,
            source_file_sha1,
            chunk_index,
            requirement_text,
            requirement_text,  # Initially, original = current
            metadata_json,
        ),
    )
    return requirement_id


def update_manifest_stage(
    conn: sqlite3.Connection,
    requirement_id: str,
    current_stage: str
) -> None:
    """Update the current processing stage of a manifest"""
    conn.execute(
        """
        UPDATE requirement_manifest
        SET current_stage = ?, updated_at = CURRENT_TIMESTAMP
        WHERE requirement_id = ?
        """,
        (current_stage, requirement_id),
    )


def update_manifest_text(
    conn: sqlite3.Connection,
    requirement_id: str,
    new_text: str,
    new_checksum: str,
) -> None:
    """Update the current text and checksum after processing (e.g., rewrite)"""
    conn.execute(
        """
        UPDATE requirement_manifest
        SET current_text = ?, requirement_checksum = ?, updated_at = CURRENT_TIMESTAMP
        WHERE requirement_id = ?
        """,
        (new_text, new_checksum, requirement_id),
    )


def add_processing_stage(
    conn: sqlite3.Connection,
    requirement_id: str,
    stage_name: str,
    status: str = "in_progress",
    evaluation_id: Optional[str] = None,
    score: Optional[float] = None,
    verdict: Optional[str] = None,
    atomic_score: Optional[float] = None,
    was_split: bool = False,
    model_used: Optional[str] = None,
    latency_ms: Optional[int] = None,
    token_usage: Optional[Dict[str, int]] = None,
    error_message: Optional[str] = None,
    stage_metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Add a new processing stage entry.
    Returns the stage id.
    """
    token_usage_json = json.dumps(token_usage or {}, ensure_ascii=False)
    stage_metadata_json = json.dumps(stage_metadata or {}, ensure_ascii=False)

    cursor = conn.execute(
        """
        INSERT INTO processing_stage
        (requirement_id, stage_name, status, evaluation_id, score, verdict,
         atomic_score, was_split, model_used, latency_ms, token_usage,
         error_message, stage_metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            requirement_id,
            stage_name,
            status,
            evaluation_id,
            score,
            verdict,
            atomic_score,
            1 if was_split else 0,
            model_used,
            latency_ms,
            token_usage_json,
            error_message,
            stage_metadata_json,
        ),
    )
    return cursor.lastrowid


def complete_processing_stage(
    conn: sqlite3.Connection,
    stage_id: int,
    status: str = "completed",
    error_message: Optional[str] = None,
    score: Optional[float] = None,
    verdict: Optional[str] = None,
    atomic_score: Optional[float] = None,
    was_split: int = 0,
    latency_ms: Optional[int] = None,
    token_usage: Optional[Dict[str, int]] = None,
    stage_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Mark a processing stage as completed or failed with all metadata"""
    import json

    token_usage_json = json.dumps(token_usage or {}, ensure_ascii=False)
    stage_metadata_json = json.dumps(stage_metadata or {}, ensure_ascii=False)

    conn.execute(
        """
        UPDATE processing_stage
        SET status = ?, completed_at = CURRENT_TIMESTAMP, error_message = ?,
            score = ?, verdict = ?, atomic_score = ?, was_split = ?,
            latency_ms = ?, token_usage = ?, stage_metadata = ?
        WHERE id = ?
        """,
        (status, error_message, score, verdict, atomic_score, was_split,
         latency_ms, token_usage_json, stage_metadata_json, stage_id),
    )


def add_evidence_reference(
    conn: sqlite3.Connection,
    requirement_id: str,
    source_file: str,
    sha1: str,
    chunk_index: int,
    is_neighbor: bool = False,
    evidence_metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Add an evidence reference for a requirement.
    Returns the evidence id.
    """
    evidence_metadata_json = json.dumps(evidence_metadata or {}, ensure_ascii=False)

    cursor = conn.execute(
        """
        INSERT INTO evidence_reference
        (requirement_id, source_file, sha1, chunk_index, is_neighbor, evidence_metadata)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (requirement_id, source_file, sha1, chunk_index, 1 if is_neighbor else 0, evidence_metadata_json),
    )
    return cursor.lastrowid


def record_requirement_split(
    conn: sqlite3.Connection,
    parent_id: str,
    child_id: str,
    split_rationale: str,
    split_model: Optional[str] = None,
) -> None:
    """Record a parent-child relationship when a requirement is split"""
    conn.execute(
        """
        INSERT INTO requirement_split (parent_id, child_id, split_rationale, split_model)
        VALUES (?, ?, ?, ?)
        """,
        (parent_id, child_id, split_rationale, split_model),
    )