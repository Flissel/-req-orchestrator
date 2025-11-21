# -*- coding: utf-8 -*-
"""
Validation History Persistence Service

Persists validation workflow data to database for analytics and history tracking.
"""
from __future__ import annotations

import sqlite3
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.core import db as _db


class ValidationPersistenceService:
    """Service for persisting validation history to database"""

    def __init__(self):
        pass

    def create_validation_session(
        self,
        conn: sqlite3.Connection,
        requirement_id: str,
        initial_text: str,
        threshold: float,
        max_iterations: int,
        session_id: Optional[str] = None,
        model_used: Optional[str] = None
    ) -> str:
        """
        Create a new validation session record.

        Returns:
            validation_id: Unique ID for this validation session
        """
        validation_id = f"val-{uuid.uuid4().hex[:12]}"

        conn.execute("""
            INSERT INTO validation_history (
                id, requirement_id, session_id, initial_text, threshold,
                max_iterations, model_used, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            validation_id,
            requirement_id,
            session_id,
            initial_text,
            threshold,
            max_iterations,
            model_used,
            datetime.utcnow().isoformat()
        ))

        return validation_id

    def complete_validation_session(
        self,
        conn: sqlite3.Connection,
        validation_id: str,
        final_text: str,
        final_score: float,
        passed: bool,
        total_iterations: int,
        total_fixes: int,
        split_occurred: bool,
        total_latency_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Complete a validation session with final results"""
        conn.execute("""
            UPDATE validation_history
            SET completed_at = ?,
                final_text = ?,
                final_score = ?,
                passed = ?,
                total_iterations = ?,
                total_fixes = ?,
                split_occurred = ?,
                total_latency_ms = ?,
                error_message = ?,
                metadata = ?
            WHERE id = ?
        """, (
            datetime.utcnow().isoformat(),
            final_text,
            final_score,
            1 if passed else 0,
            total_iterations,
            total_fixes,
            1 if split_occurred else 0,
            total_latency_ms,
            error_message,
            json.dumps(metadata) if metadata else None,
            validation_id
        ))

    def create_iteration(
        self,
        conn: sqlite3.Connection,
        validation_id: str,
        iteration_number: int,
        requirement_text: str,
        overall_score: float,
        iteration_metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Create a new iteration record.

        Returns:
            iteration_id: Database ID for this iteration
        """
        cursor = conn.execute("""
            INSERT INTO validation_iteration (
                validation_id, iteration_number, started_at,
                requirement_text, overall_score, iteration_metadata
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            validation_id,
            iteration_number,
            datetime.utcnow().isoformat(),
            requirement_text,
            overall_score,
            json.dumps(iteration_metadata) if iteration_metadata else None
        ))

        return cursor.lastrowid

    def complete_iteration(
        self,
        conn: sqlite3.Connection,
        iteration_id: int,
        fixes_applied: int,
        split_occurred: bool,
        split_children_count: Optional[int] = None
    ):
        """Mark iteration as complete"""
        conn.execute("""
            UPDATE validation_iteration
            SET completed_at = ?,
                fixes_applied = ?,
                split_occurred = ?,
                split_children_count = ?
            WHERE id = ?
        """, (
            datetime.utcnow().isoformat(),
            fixes_applied,
            1 if split_occurred else 0,
            split_children_count,
            iteration_id
        ))

    def record_criterion_fix(
        self,
        conn: sqlite3.Connection,
        validation_id: str,
        iteration_id: int,
        criterion: str,
        old_text: str,
        new_text: str,
        score_before: float,
        score_after: float,
        suggestion: Optional[str] = None,
        model_used: Optional[str] = None,
        latency_ms: Optional[int] = None
    ):
        """Record a criterion-level fix"""
        improvement = score_after - score_before

        conn.execute("""
            INSERT INTO validation_criterion_fix (
                validation_id, iteration_id, criterion, applied_at,
                old_text, new_text, score_before, score_after,
                improvement, suggestion, model_used, latency_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            validation_id,
            iteration_id,
            criterion,
            datetime.utcnow().isoformat(),
            old_text,
            new_text,
            score_before,
            score_after,
            improvement,
            suggestion,
            model_used,
            latency_ms
        ))

    def record_criterion_scores(
        self,
        conn: sqlite3.Connection,
        validation_id: str,
        iteration_id: int,
        scores: Dict[str, float],
        threshold: float
    ):
        """Record all criterion scores for an iteration"""
        for criterion, score in scores.items():
            passed = 1 if score >= threshold else 0

            conn.execute("""
                INSERT OR REPLACE INTO validation_criterion_score (
                    validation_id, iteration_id, criterion, score, passed
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                validation_id,
                iteration_id,
                criterion,
                score,
                passed
            ))

    def get_validation_history(
        self,
        conn: sqlite3.Connection,
        requirement_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get validation history for a requirement"""
        cursor = conn.execute("""
            SELECT
                id, session_id, started_at, completed_at,
                initial_text, final_text, initial_score, final_score,
                passed, threshold, max_iterations, total_iterations,
                total_fixes, split_occurred, model_used, total_latency_ms,
                error_message, metadata
            FROM validation_history
            WHERE requirement_id = ?
            ORDER BY started_at DESC
            LIMIT ?
        """, (requirement_id, limit))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_validation_details(
        self,
        conn: sqlite3.Connection,
        validation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get complete validation details including iterations and fixes"""
        # Get validation record
        cursor = conn.execute("""
            SELECT *
            FROM validation_history
            WHERE id = ?
        """, (validation_id,))

        validation_row = cursor.fetchone()
        if not validation_row:
            return None

        validation = dict(validation_row)

        # Get iterations
        cursor = conn.execute("""
            SELECT *
            FROM validation_iteration
            WHERE validation_id = ?
            ORDER BY iteration_number
        """, (validation_id,))

        iterations = [dict(row) for row in cursor.fetchall()]

        # Get fixes for each iteration
        for iteration in iterations:
            cursor = conn.execute("""
                SELECT *
                FROM validation_criterion_fix
                WHERE iteration_id = ?
                ORDER BY applied_at
            """, (iteration['id'],))

            iteration['fixes'] = [dict(row) for row in cursor.fetchall()]

            # Get criterion scores
            cursor = conn.execute("""
                SELECT criterion, score, passed
                FROM validation_criterion_score
                WHERE iteration_id = ?
            """, (iteration['id'],))

            iteration['criterion_scores'] = [dict(row) for row in cursor.fetchall()]

        validation['iterations'] = iterations
        return validation

    def get_validation_analytics(
        self,
        conn: sqlite3.Connection,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get validation analytics for the last N days"""
        # Total validations
        cursor = conn.execute("""
            SELECT COUNT(*) as total
            FROM validation_history
            WHERE started_at >= datetime('now', '-' || ? || ' days')
        """, (days,))
        total_validations = cursor.fetchone()['total']

        # Pass/fail stats
        cursor = conn.execute("""
            SELECT
                SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed_count,
                SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) as failed_count
            FROM validation_history
            WHERE started_at >= datetime('now', '-' || ? || ' days')
        """, (days,))
        pass_fail_stats = dict(cursor.fetchone())

        # Average scores
        cursor = conn.execute("""
            SELECT
                AVG(initial_score) as avg_initial_score,
                AVG(final_score) as avg_final_score,
                AVG(final_score - initial_score) as avg_improvement
            FROM validation_history
            WHERE started_at >= datetime('now', '-' || ? || ' days')
              AND initial_score IS NOT NULL
              AND final_score IS NOT NULL
        """, (days,))
        score_stats = dict(cursor.fetchone())

        # Average fixes
        cursor = conn.execute("""
            SELECT
                AVG(total_fixes) as avg_fixes,
                AVG(total_iterations) as avg_iterations,
                AVG(total_latency_ms) as avg_latency_ms
            FROM validation_history
            WHERE started_at >= datetime('now', '-' || ? || ' days')
              AND total_fixes IS NOT NULL
        """, (days,))
        fix_stats = dict(cursor.fetchone())

        # Most common failing criteria
        cursor = conn.execute("""
            SELECT
                criterion,
                COUNT(*) as fix_count,
                AVG(improvement) as avg_improvement
            FROM validation_criterion_fix
            WHERE validation_id IN (
                SELECT id FROM validation_history
                WHERE started_at >= datetime('now', '-' || ? || ' days')
            )
            GROUP BY criterion
            ORDER BY fix_count DESC
            LIMIT 10
        """, (days,))
        failing_criteria = [dict(row) for row in cursor.fetchall()]

        return {
            'total_validations': total_validations,
            'passed_count': pass_fail_stats.get('passed_count', 0),
            'failed_count': pass_fail_stats.get('failed_count', 0),
            'avg_initial_score': score_stats.get('avg_initial_score'),
            'avg_final_score': score_stats.get('avg_final_score'),
            'avg_improvement': score_stats.get('avg_improvement'),
            'avg_fixes': fix_stats.get('avg_fixes'),
            'avg_iterations': fix_stats.get('avg_iterations'),
            'avg_latency_ms': fix_stats.get('avg_latency_ms'),
            'failing_criteria': failing_criteria
        }


# Global singleton instance
validation_persistence_service = ValidationPersistenceService()
