# -*- coding: utf-8 -*-
"""
Async Database Operations für FastAPI + AutoGen Integration
"""

import asyncio
import sqlite3
import aiosqlite
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class AsyncDatabase:
    """Async Database Wrapper für Requirements System"""
    
    def __init__(self, db_path: str = "./data/app.db"):
        self.db_path = db_path
        self._connection_pool: Optional[aiosqlite.Connection] = None
    
    async def get_connection(self) -> aiosqlite.Connection:
        """Async Database Connection"""
        if not self._connection_pool:
            self._connection_pool = await aiosqlite.connect(self.db_path)
            await self._connection_pool.execute("PRAGMA journal_mode=WAL")
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
        
        await db.execute(
            """INSERT INTO evaluation 
               (id, requirement_checksum, verdict, score, latency_ms, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                evaluation_id,
                requirement_checksum,
                evaluation_data.get("verdict", "unknown"),
                evaluation_data.get("score", 0.0),
                evaluation_data.get("latency_ms", 0),
                evaluation_data.get("model", "unknown"),
                datetime.now()
            )
        )
        
        # Details speichern
        for criterion, score in evaluation_data.get("details", {}).items():
            await db.execute(
                """INSERT INTO evaluation_detail 
                   (evaluation_id, criterion_key, score, created_at)
                   VALUES (?, ?, ?, ?)""",
                (evaluation_id, criterion, score, datetime.now())
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
