# -*- coding: utf-8 -*-
"""
Async Database Operations für FastAPI + AutoGen Integration
"""

import asyncio
import sqlite3
import aiosqlite
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from .db import DDL
from . import settings

logger = logging.getLogger(__name__)

class AsyncDatabase:
    """Async Database Wrapper für Requirements System"""
    
    def __init__(self, db_path: str = None):
        # Bevorzugt Settings-Pfad; in Pytest auf isolierte Test-DB umleiten
        effective_path = db_path or getattr(settings, "SQLITE_PATH", "./data/app.db")
        if "PYTEST_CURRENT_TEST" in os.environ:
            effective_path = "./test_data/test_app.db"
        try:
            os.makedirs(os.path.dirname(effective_path) or ".", exist_ok=True)
        except Exception:
            pass
        self.db_path = effective_path
        self._connection_pool: Optional[aiosqlite.Connection] = None
    
    async def get_connection(self) -> aiosqlite.Connection:
        """Async Database Connection"""
        if not self._connection_pool:
            self._connection_pool = await aiosqlite.connect(self.db_path)
            await self._connection_pool.execute("PRAGMA journal_mode=WAL")
            await self._connection_pool.execute("PRAGMA synchronous=NORMAL")
            await self._connection_pool.execute("PRAGMA busy_timeout=5000")
            await self._connection_pool.execute("PRAGMA foreign_keys=ON")
            # Stelle sicher, dass das Schema existiert (idempotent)
            try:
                await self._connection_pool.executescript(DDL)
                await self._connection_pool.commit()
            except Exception:
                # Schema-Init ist best-effort; Fehler hier nicht kritisch für Verbindungsaufbau
                pass
            await self._connection_pool.commit()
        return self._connection_pool
    
    async def close(self):
        """Schließt Database Connection"""
        if self._connection_pool:
            await self._connection_pool.close()
            self._connection_pool = None

# Global Database Instance
db_instance = AsyncDatabase()

async def get_db_async() -> aiosqlite.Connection:
    """Async Database Dependency"""
    return await db_instance.get_connection()

async def load_criteria_async() -> List[Dict[str, Any]]:
    """Lädt Evaluation-Kriterien async"""
    try:
        db = await get_db_async()
        async with db.execute(
            "SELECT key, name, weight, active FROM criterion WHERE active = 1"
        ) as cursor:
            rows = await cursor.fetchall()
            
        criteria = []
        for row in rows:
            criteria.append({
                "key": row[0],
                "name": row[1], 
                "weight": row[2],
                "active": bool(row[3])
            })
            
        logger.info(f"Loaded {len(criteria)} active criteria")
        return criteria
        
    except Exception as e:
        logger.error(f"Fehler beim Laden der Kriterien: {str(e)}")
        return []

async def save_evaluation_async(
    requirement_checksum: str,
    evaluation_data: Dict[str, Any]
) -> str:
    """Speichert Evaluation-Ergebnis async"""
    try:
        db = await get_db_async()
        
        evaluation_id = f"eval_{int(asyncio.get_event_loop().time() * 1000)}"
        
        # Verdict auf DB-Schema ('pass'|'fail') mappen
        raw_verdict = str(evaluation_data.get("verdict") or "").strip().lower()
        score_val = float(evaluation_data.get("score") or 0.0)
        if raw_verdict in ("pass", "fail"):
            verdict_db = raw_verdict
        elif raw_verdict in ("excellent", "good", "acceptable"):
            verdict_db = "pass"
        elif raw_verdict in ("needs_improvement", "poor"):
            verdict_db = "fail"
        else:
            verdict_db = "pass" if score_val >= 0.7 else "fail"
        model_val = str(evaluation_data.get("model") or "unknown")
        
        await db.execute(
            """INSERT INTO evaluation 
               (id, requirement_checksum, model, latency_ms, score, verdict, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                evaluation_id,
                requirement_checksum,
                model_val,
                int(evaluation_data.get("latency_ms") or 0),
                score_val,
                verdict_db,
                datetime.now()
            )
        )
        
        # Details speichern
        for criterion, c_score in (evaluation_data.get("details") or {}).items():
            # Stelle sicher, dass das Kriterium existiert (FK constraint)
            try:
                await db.execute(
                    """INSERT OR IGNORE INTO criterion(key, name, description, weight, active)
                       VALUES (?, ?, ?, ?, ?)""",
                    (str(criterion), str(criterion), "", 1.0, 1),
                )
            except Exception:
                pass
            try:
                c_val = float(c_score)
            except Exception:
                c_val = 0.0
            passed = 1 if c_val >= 0.7 else 0
            feedback = ""
            await db.execute(
                """INSERT INTO evaluation_detail 
                   (evaluation_id, criterion_key, score, passed, feedback)
                   VALUES (?, ?, ?, ?, ?)""",
                (evaluation_id, str(criterion), c_val, passed, feedback)
            )
        
        await db.commit()
        logger.info(f"Evaluation {evaluation_id} gespeichert")
        return evaluation_id
        
    except Exception as e:
        logger.error(f"Fehler beim Speichern der Evaluation: {str(e)}")
        raise

async def save_suggestions_async(
    requirement_checksum: str,
    suggestions: List[str],
    model: str = "unknown"
) -> List[str]:
    """Speichert Suggestions async"""
    try:
        db = await get_db_async()
        suggestion_ids = []
        
        for i, suggestion in enumerate(suggestions):
            suggestion_id = f"sugg_{int(asyncio.get_event_loop().time() * 1000)}_{i}"
            
            await db.execute(
                """INSERT INTO suggestion 
                   (id, requirement_checksum, suggestion_text, model, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (suggestion_id, requirement_checksum, suggestion, model, datetime.now())
            )
            suggestion_ids.append(suggestion_id)
        
        await db.commit()
        logger.info(f"{len(suggestions)} Suggestions gespeichert")
        return suggestion_ids
        
    except Exception as e:
        logger.error(f"Fehler beim Speichern der Suggestions: {str(e)}")
        raise

async def save_rewrite_async(
    requirement_checksum: str,
    rewritten_text: str,
    model: str = "unknown"
) -> str:
    """Speichert Rewrite async"""
    try:
        db = await get_db_async()
        
        rewrite_id = f"rewrite_{int(asyncio.get_event_loop().time() * 1000)}"
        
        await db.execute(
            """INSERT INTO rewritten_requirement 
               (id, requirement_checksum, redefined_requirement, model, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (rewrite_id, requirement_checksum, rewritten_text, model, datetime.now())
        )
        
        await db.commit()
        logger.info(f"Rewrite {rewrite_id} gespeichert")
        return rewrite_id
        
    except Exception as e:
        logger.error(f"Fehler beim Speichern des Rewrite: {str(e)}")
        raise

async def get_latest_evaluation_async(requirement_checksum: str) -> Optional[Dict[str, Any]]:
    """Holt neueste Evaluation für Requirement"""
    try:
        db = await get_db_async()
        
        async with db.execute(
            """SELECT id, verdict, score, latency_ms, model, created_at 
               FROM evaluation 
               WHERE requirement_checksum = ? 
               ORDER BY created_at DESC LIMIT 1""",
            (requirement_checksum,)
        ) as cursor:
            row = await cursor.fetchone()
            
        if not row:
            return None
            
        # Details laden
        async with db.execute(
            """SELECT criterion_key, score 
               FROM evaluation_detail 
               WHERE evaluation_id = ?""",
            (row[0],)
        ) as cursor:
            details_rows = await cursor.fetchall()
            
        details = {detail[0]: detail[1] for detail in details_rows}
        
        return {
            "evaluation_id": row[0],
            "verdict": row[1],
            "score": row[2],
            "latency_ms": row[3],
            "model": row[4],
            "created_at": row[5],
            "details": details
        }
        
    except Exception as e:
        logger.error(f"Fehler beim Laden der Evaluation: {str(e)}")
        return None

async def get_processing_stats_async() -> Dict[str, Any]:
    """Holt Processing-Statistiken"""
    try:
        db = await get_db_async()
        
        # Evaluations heute
        async with db.execute(
            """SELECT COUNT(*) FROM evaluation 
               WHERE DATE(created_at) = DATE('now')"""
        ) as cursor:
            evals_today = (await cursor.fetchone())[0]
        
        # Suggestions heute  
        async with db.execute(
            """SELECT COUNT(*) FROM suggestion 
               WHERE DATE(created_at) = DATE('now')"""
        ) as cursor:
            suggestions_today = (await cursor.fetchone())[0]
            
        # Rewrites heute
        async with db.execute(
            """SELECT COUNT(*) FROM rewritten_requirement 
               WHERE DATE(created_at) = DATE('now')"""
        ) as cursor:
            rewrites_today = (await cursor.fetchone())[0]
            
        # Durchschnittliche Latenz
        async with db.execute(
            """SELECT AVG(latency_ms) FROM evaluation 
               WHERE DATE(created_at) = DATE('now')"""
        ) as cursor:
            avg_latency = (await cursor.fetchone())[0] or 0
            
        return {
            "evaluations_today": evals_today,
            "suggestions_today": suggestions_today,
            "rewrites_today": rewrites_today,
            "average_latency_ms": round(avg_latency, 2),
            "total_processed_today": evals_today + suggestions_today + rewrites_today
        }
        
    except Exception as e:
        logger.error(f"Fehler beim Laden der Statistiken: {str(e)}")
        return {
            "evaluations_today": 0,
            "suggestions_today": 0,
            "rewrites_today": 0,
            "average_latency_ms": 0,
            "total_processed_today": 0
        }
