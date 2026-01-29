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
  verdict TEXT CHECK (verdict IN ('pass','fail','on_hold')),
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
  stage_name TEXT NOT NULL CHECK (stage_name IN ('input','mining','evaluation','atomicity','suggestion','rewrite','validation','completed','failed','needs_user_input','fix_clarity','fix_testability','fix_measurability','fix_atomic','fix_concise','fix_unambiguous','fix_consistent_language','fix_design_independent','fix_purpose_independent')),
  status TEXT NOT NULL CHECK (status IN ('pending','in_progress','completed','failed','awaiting_input')),
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

-- =============================================================================
-- CLARIFICATION QUESTIONS: Tracks user input requests for unfixable requirements
-- =============================================================================

CREATE TABLE IF NOT EXISTS clarification_question (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  validation_id TEXT,                             -- Links to validation_history.id (optional)
  requirement_id TEXT NOT NULL,                   -- Links to requirement_manifest.requirement_id
  criterion TEXT NOT NULL,                        -- Which criterion triggered the question
  question_text TEXT NOT NULL,                    -- The question in user's language
  suggested_answers TEXT,                         -- JSON array of suggested answers
  context_hint TEXT,                              -- Why this question was generated
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','answered','skipped','expired')),
  answer_text TEXT,                               -- User's answer
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  answered_at DATETIME,
  applied_text TEXT,                              -- Requirement text after applying answer
  FOREIGN KEY (validation_id) REFERENCES validation_history(id) ON DELETE CASCADE,
  FOREIGN KEY (requirement_id) REFERENCES requirement_manifest(requirement_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_clarification_requirement ON clarification_question (requirement_id);
CREATE INDEX IF NOT EXISTS idx_clarification_validation ON clarification_question (validation_id);
CREATE INDEX IF NOT EXISTS idx_clarification_status ON clarification_question (status);
CREATE INDEX IF NOT EXISTS idx_clarification_criterion ON clarification_question (criterion);

-- =============================================================================
-- PROJECT METADATA: Tracks TechStack-generated projects
-- =============================================================================

CREATE TABLE IF NOT EXISTS project_metadata (
  project_id TEXT PRIMARY KEY,                -- UUID or slugified name
  project_name TEXT NOT NULL,                 -- Human-readable project name
  project_path TEXT NOT NULL,                 -- Filesystem path to project
  template_id TEXT NOT NULL,                  -- Template used (e.g., "02-api-service")
  template_name TEXT,                         -- Template display name
  template_category TEXT,                     -- web, backend, mobile, etc.
  tech_stack TEXT,                            -- JSON array of technologies
  requirements_count INTEGER DEFAULT 0,       -- Number of requirements imported
  source_file TEXT,                           -- Original requirements source file
  validation_summary TEXT,                    -- JSON: {total, passed, failed, avg_score}
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  metadata TEXT                               -- Additional JSON metadata
);

CREATE INDEX IF NOT EXISTS idx_project_template ON project_metadata (template_id);
CREATE INDEX IF NOT EXISTS idx_project_category ON project_metadata (template_category);
CREATE INDEX IF NOT EXISTS idx_project_created ON project_metadata (created_at);

-- Link table: associates projects with requirements
CREATE TABLE IF NOT EXISTS project_requirements (
  project_id TEXT NOT NULL,
  requirement_id TEXT NOT NULL,
  imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (project_id, requirement_id),
  FOREIGN KEY (project_id) REFERENCES project_metadata(project_id) ON DELETE CASCADE,
  FOREIGN KEY (requirement_id) REFERENCES requirement_manifest(requirement_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_project_req_project ON project_requirements (project_id);
CREATE INDEX IF NOT EXISTS idx_project_req_requirement ON project_requirements (requirement_id);
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

    # Migration: Add validation columns to requirement_manifest
    try:
        conn.execute("ALTER TABLE requirement_manifest ADD COLUMN validation_score REAL")
    except sqlite3.OperationalError:
        pass  # Column already exists
    try:
        conn.execute("ALTER TABLE requirement_manifest ADD COLUMN validation_verdict TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists


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


def persist_evaluation_with_details(
    conn: sqlite3.Connection,
    requirement_text: str,
    score: float,
    verdict: str,
    details: List[Dict[str, Any]],
    model: str = "unknown",
    latency_ms: int = 0,
) -> str:
    """
    Persist evaluation and its criteria details to the database.

    This is used by the mining pipeline to save validation results.

    Args:
        conn: Database connection
        requirement_text: The requirement text (used for checksum)
        score: Overall evaluation score (0.0-1.0)
        verdict: Verdict string (pass/fail)
        details: List of criterion evaluation dicts with:
            - criterion: criterion key (e.g., "clarity", "testability")
            - score: criterion score (0.0-1.0)
            - passed: boolean
            - feedback: optional feedback string
        model: Model used for evaluation
        latency_ms: Processing time in milliseconds

    Returns:
        The evaluation_id of the created record
    """
    import hashlib
    import time

    # Generate checksum from requirement text
    checksum = hashlib.sha256(requirement_text.encode("utf-8")).hexdigest()

    # Generate evaluation ID
    eval_id = f"ev_{int(time.time())}_{checksum[:8]}"

    with conn:
        # Insert main evaluation record
        conn.execute(
            "INSERT INTO evaluation(id, requirement_checksum, model, latency_ms, score, verdict) VALUES (?, ?, ?, ?, ?, ?)",
            (eval_id, checksum, model, latency_ms, score, verdict),
        )

        # Insert criterion details
        for d in details:
            criterion_key = d.get("criterion", "")
            if not criterion_key:
                continue

            criterion_score = float(d.get("score", 0.0))
            passed = 1 if d.get("passed", False) else 0
            feedback = d.get("feedback", "") or d.get("reason", "")

            conn.execute(
                "INSERT INTO evaluation_detail(evaluation_id, criterion_key, score, passed, feedback) VALUES (?, ?, ?, ?, ?)",
                (eval_id, criterion_key, criterion_score, passed, feedback),
            )

    return eval_id


def get_evaluation_details(conn: sqlite3.Connection, evaluation_id: str) -> List[Dict[str, Any]]:
    """
    Get all criterion details for an evaluation.

    Args:
        conn: Database connection
        evaluation_id: The evaluation ID

    Returns:
        List of criterion detail dicts
    """
    rows = conn.execute(
        "SELECT criterion_key, score, passed, feedback FROM evaluation_detail WHERE evaluation_id = ?",
        (evaluation_id,),
    ).fetchall()

    return [
        {
            "criterion": row["criterion_key"],
            "score": row["score"],
            "passed": bool(row["passed"]),
            "feedback": row["feedback"],
        }
        for row in rows
    ]


def get_evaluation_for_requirement(
    conn: sqlite3.Connection,
    requirement_text: str,
) -> Optional[Dict[str, Any]]:
    """
    Get the latest evaluation and its criteria details for a requirement text.

    Args:
        conn: Database connection
        requirement_text: The requirement text

    Returns:
        Dict with evaluation info and details, or None if not found:
        {
            "evaluation_id": "ev_...",
            "score": 0.75,
            "verdict": "pass",
            "details": [
                {"criterion": "clarity", "score": 0.8, "passed": True, "feedback": "..."},
                ...
            ]
        }
    """
    import hashlib

    # Generate checksum from requirement text
    checksum = hashlib.sha256(requirement_text.encode("utf-8")).hexdigest()

    # Find latest evaluation for this checksum
    eval_row = conn.execute(
        """
        SELECT id, score, verdict, created_at
        FROM evaluation
        WHERE requirement_checksum = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (checksum,),
    ).fetchone()

    if not eval_row:
        return None

    # Get criterion details
    details = get_evaluation_details(conn, eval_row["id"])

    return {
        "evaluation_id": eval_row["id"],
        "score": eval_row["score"],
        "verdict": eval_row["verdict"],
        "details": details,
    }


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
               current_stage, parent_id, validation_score, validation_verdict,
               created_at, updated_at, metadata
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
               current_stage, parent_id, validation_score, validation_verdict,
               created_at, updated_at, metadata
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


# =============================================================================
# PROJECT METADATA: Helper functions
# =============================================================================

def create_project(
    conn: sqlite3.Connection,
    project_id: str,
    project_name: str,
    project_path: str,
    template_id: str,
    template_name: Optional[str] = None,
    template_category: Optional[str] = None,
    tech_stack: Optional[List[str]] = None,
    requirements_count: int = 0,
    source_file: Optional[str] = None,
    validation_summary: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a new project metadata record.
    Returns the project_id.
    """
    tech_stack_json = json.dumps(tech_stack or [], ensure_ascii=False)
    validation_summary_json = json.dumps(validation_summary or {}, ensure_ascii=False)
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

    conn.execute(
        """
        INSERT INTO project_metadata
        (project_id, project_name, project_path, template_id, template_name,
         template_category, tech_stack, requirements_count, source_file,
         validation_summary, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            project_name,
            project_path,
            template_id,
            template_name,
            template_category,
            tech_stack_json,
            requirements_count,
            source_file,
            validation_summary_json,
            metadata_json,
        ),
    )
    return project_id


def get_project_by_id(conn: sqlite3.Connection, project_id: str) -> Optional[sqlite3.Row]:
    """Retrieve project metadata by project_id"""
    return conn.execute(
        """
        SELECT project_id, project_name, project_path, template_id, template_name,
               template_category, tech_stack, requirements_count, source_file,
               validation_summary, created_at, updated_at, metadata
        FROM project_metadata
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()


def list_projects(
    conn: sqlite3.Connection,
    limit: int = 100,
    offset: int = 0,
    template_id: Optional[str] = None,
    category: Optional[str] = None,
) -> List[sqlite3.Row]:
    """List projects with optional filters"""
    where_clauses = []
    params: List[Any] = []

    if template_id:
        where_clauses.append("template_id = ?")
        params.append(template_id)
    if category:
        where_clauses.append("template_category = ?")
        params.append(category)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    params.extend([limit, offset])
    return conn.execute(
        f"""
        SELECT project_id, project_name, project_path, template_id, template_name,
               template_category, tech_stack, requirements_count, source_file,
               validation_summary, created_at, updated_at, metadata
        FROM project_metadata
        WHERE {where_sql}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()


def count_projects(conn: sqlite3.Connection) -> int:
    """Get total number of projects"""
    row = conn.execute("SELECT COUNT(*) as c FROM project_metadata").fetchone()
    return row["c"] if row else 0


def link_project_requirement(
    conn: sqlite3.Connection,
    project_id: str,
    requirement_id: str,
) -> None:
    """Link a requirement to a project"""
    conn.execute(
        """
        INSERT OR IGNORE INTO project_requirements (project_id, requirement_id)
        VALUES (?, ?)
        """,
        (project_id, requirement_id),
    )


def link_project_requirements_batch(
    conn: sqlite3.Connection,
    project_id: str,
    requirement_ids: List[str],
) -> int:
    """Link multiple requirements to a project. Returns count of linked."""
    if not requirement_ids:
        return 0
    conn.executemany(
        """
        INSERT OR IGNORE INTO project_requirements (project_id, requirement_id)
        VALUES (?, ?)
        """,
        [(project_id, req_id) for req_id in requirement_ids],
    )
    return len(requirement_ids)


def get_project_requirements(conn: sqlite3.Connection, project_id: str) -> List[sqlite3.Row]:
    """Get all requirements linked to a project (with full manifest data)"""
    return conn.execute(
        """
        SELECT rm.requirement_id, rm.requirement_checksum, rm.source_type, rm.source_file,
               rm.original_text, rm.current_text, rm.current_stage,
               rm.validation_score, rm.validation_verdict, rm.created_at, rm.updated_at,
               pr.imported_at
        FROM project_requirements pr
        JOIN requirement_manifest rm ON pr.requirement_id = rm.requirement_id
        WHERE pr.project_id = ?
        ORDER BY pr.imported_at ASC
        """,
        (project_id,),
    ).fetchall()


def get_project_requirement_ids(conn: sqlite3.Connection, project_id: str) -> List[str]:
    """Get just the requirement IDs linked to a project (no JOIN)"""
    rows = conn.execute(
        """
        SELECT requirement_id FROM project_requirements
        WHERE project_id = ?
        ORDER BY imported_at ASC
        """,
        (project_id,),
    ).fetchall()
    return [r["requirement_id"] for r in rows]


def delete_project(conn: sqlite3.Connection, project_id: str) -> bool:
    """Delete a project (CASCADE deletes project_requirements links)"""
    cursor = conn.execute(
        "DELETE FROM project_metadata WHERE project_id = ?",
        (project_id,),
    )
    return cursor.rowcount > 0