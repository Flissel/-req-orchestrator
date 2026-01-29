# -*- coding: utf-8 -*-
"""
Clarification Service for Database Operations.

Handles all CRUD operations for clarification_question table:
- Create questions from validation feedback
- Retrieve pending/answered questions
- Record user answers
- Apply answers to requirement text
- Track question lifecycle

Part of the Requirements-Management-System.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.core import db as _db

logger = logging.getLogger("backend.services.clarification_service")


class ClarificationService:
    """
    Service for managing clarification questions.
    
    Provides methods for:
    - Creating questions from validation feedback
    - Retrieving questions by status/requirement
    - Recording user answers
    - Applying answers to requirement text
    - Cleaning up expired questions
    """
    
    def __init__(self):
        """Initialize clarification service."""
        pass
    
    def create_question(
        self,
        conn: sqlite3.Connection,
        requirement_id: str,
        criterion: str,
        question_text: str,
        *,
        validation_id: Optional[str] = None,
        suggested_answers: Optional[List[str]] = None,
        context_hint: Optional[str] = None
    ) -> int:
        """
        Create a new clarification question.
        
        Args:
            conn: SQLite connection
            requirement_id: Links to requirement_manifest
            criterion: Which criterion triggered the question
            question_text: The question in user's language
            validation_id: Optional link to validation_history
            suggested_answers: Optional list of suggested answers
            context_hint: Optional context/hint for the user
        
        Returns:
            question_id (int)
        """
        suggested_json = json.dumps(suggested_answers or [], ensure_ascii=False)
        
        cursor = conn.execute(
            """
            INSERT INTO clarification_question
            (validation_id, requirement_id, criterion, question_text,
             suggested_answers, context_hint, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
            """,
            (validation_id, requirement_id, criterion, question_text,
             suggested_json, context_hint)
        )
        
        question_id = cursor.lastrowid
        logger.info(f"Created clarification question {question_id} for {requirement_id}/{criterion}")
        
        return question_id
    
    def create_questions_batch(
        self,
        conn: sqlite3.Connection,
        questions: List[Dict[str, Any]],
        *,
        validation_id: Optional[str] = None
    ) -> List[int]:
        """
        Create multiple clarification questions in batch.
        
        Args:
            conn: SQLite connection
            questions: List of question dicts with keys:
                - requirement_id (required)
                - criterion (required)
                - question_text (required)
                - suggested_answers (optional)
                - context_hint (optional)
            validation_id: Optional link to validation_history for all
        
        Returns:
            List of question_ids
        """
        question_ids = []
        
        for q in questions:
            qid = self.create_question(
                conn,
                requirement_id=q["requirement_id"],
                criterion=q["criterion"],
                question_text=q["question_text"],
                validation_id=validation_id,
                suggested_answers=q.get("suggested_answers"),
                context_hint=q.get("context_hint")
            )
            question_ids.append(qid)
        
        logger.info(f"Created {len(question_ids)} clarification questions in batch")
        return question_ids
    
    def get_question_by_id(
        self,
        conn: sqlite3.Connection,
        question_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single clarification question by ID.
        
        Args:
            conn: SQLite connection
            question_id: Question ID
        
        Returns:
            Question dict or None
        """
        row = conn.execute(
            """
            SELECT id, validation_id, requirement_id, criterion,
                   question_text, suggested_answers, context_hint,
                   status, answer_text, created_at, answered_at, applied_text
            FROM clarification_question
            WHERE id = ?
            """,
            (question_id,)
        ).fetchone()
        
        if not row:
            return None
        
        return self._row_to_dict(row)
    
    def get_pending_questions(
        self,
        conn: sqlite3.Connection,
        *,
        requirement_id: Optional[str] = None,
        validation_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all pending (unanswered) questions.
        
        Args:
            conn: SQLite connection
            requirement_id: Optional filter by requirement
            validation_id: Optional filter by validation session
            limit: Maximum number of results
        
        Returns:
            List of question dicts
        """
        query = """
            SELECT id, validation_id, requirement_id, criterion,
                   question_text, suggested_answers, context_hint,
                   status, answer_text, created_at, answered_at, applied_text
            FROM clarification_question
            WHERE status = 'pending'
        """
        params = []
        
        if requirement_id:
            query += " AND requirement_id = ?"
            params.append(requirement_id)
        
        if validation_id:
            query += " AND validation_id = ?"
            params.append(validation_id)
        
        query += " ORDER BY created_at ASC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]
    
    def get_questions_for_requirement(
        self,
        conn: sqlite3.Connection,
        requirement_id: str,
        *,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all questions for a specific requirement.
        
        Args:
            conn: SQLite connection
            requirement_id: Requirement ID
            status: Optional filter by status (pending/answered/skipped/expired)
        
        Returns:
            List of question dicts
        """
        query = """
            SELECT id, validation_id, requirement_id, criterion,
                   question_text, suggested_answers, context_hint,
                   status, answer_text, created_at, answered_at, applied_text
            FROM clarification_question
            WHERE requirement_id = ?
        """
        params = [requirement_id]
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY created_at ASC"
        
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]
    
    def answer_question(
        self,
        conn: sqlite3.Connection,
        question_id: int,
        answer_text: str,
        *,
        apply_to_requirement: bool = True
    ) -> Dict[str, Any]:
        """
        Record user's answer to a clarification question.
        
        Args:
            conn: SQLite connection
            question_id: Question ID
            answer_text: User's answer
            apply_to_requirement: Whether to update requirement text
        
        Returns:
            Updated question dict
        """
        # Get the question first
        question = self.get_question_by_id(conn, question_id)
        if not question:
            raise ValueError(f"Question {question_id} not found")
        
        if question["status"] != "pending":
            raise ValueError(f"Question {question_id} is not pending (status: {question['status']})")
        
        # Update question with answer
        conn.execute(
            """
            UPDATE clarification_question
            SET answer_text = ?, status = 'answered', answered_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (answer_text, question_id)
        )
        
        logger.info(f"Recorded answer for question {question_id}: {answer_text[:50]}...")
        
        # Optionally apply to requirement
        applied_text = None
        if apply_to_requirement:
            applied_text = self._apply_answer_to_requirement(
                conn,
                question["requirement_id"],
                question["criterion"],
                answer_text
            )
            
            if applied_text:
                conn.execute(
                    "UPDATE clarification_question SET applied_text = ? WHERE id = ?",
                    (applied_text, question_id)
                )
        
        # Return updated question
        return self.get_question_by_id(conn, question_id)
    
    def skip_question(
        self,
        conn: sqlite3.Connection,
        question_id: int,
        *,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mark a question as skipped (user chose not to answer).
        
        Args:
            conn: SQLite connection
            question_id: Question ID
            reason: Optional reason for skipping
        
        Returns:
            Updated question dict
        """
        conn.execute(
            """
            UPDATE clarification_question
            SET status = 'skipped', answer_text = ?, answered_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (reason or "Skipped by user", question_id)
        )
        
        logger.info(f"Question {question_id} skipped")
        return self.get_question_by_id(conn, question_id)
    
    def expire_old_questions(
        self,
        conn: sqlite3.Connection,
        max_age_hours: int = 24
    ) -> int:
        """
        Expire old pending questions that were never answered.
        
        Args:
            conn: SQLite connection
            max_age_hours: Questions older than this are expired
        
        Returns:
            Number of expired questions
        """
        cursor = conn.execute(
            """
            UPDATE clarification_question
            SET status = 'expired'
            WHERE status = 'pending'
              AND datetime(created_at) < datetime('now', ? || ' hours')
            """,
            (f"-{max_age_hours}",)
        )
        
        count = cursor.rowcount
        if count > 0:
            logger.info(f"Expired {count} old clarification questions")
        
        return count
    
    def get_questions_summary(
        self,
        conn: sqlite3.Connection,
        *,
        validation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get summary statistics of clarification questions.
        
        Args:
            conn: SQLite connection
            validation_id: Optional filter by validation session
        
        Returns:
            Summary dict with counts by status and criterion
        """
        base_query = "FROM clarification_question"
        params = []
        
        if validation_id:
            base_query += " WHERE validation_id = ?"
            params.append(validation_id)
        
        # Count by status
        status_query = f"""
            SELECT status, COUNT(*) as count
            {base_query}
            GROUP BY status
        """
        status_rows = conn.execute(status_query, params).fetchall()
        by_status = {row["status"]: row["count"] for row in status_rows}
        
        # Count by criterion
        criterion_query = f"""
            SELECT criterion, COUNT(*) as count
            {base_query}
            GROUP BY criterion
        """
        criterion_rows = conn.execute(criterion_query, params).fetchall()
        by_criterion = {row["criterion"]: row["count"] for row in criterion_rows}
        
        # Total
        total = sum(by_status.values())
        
        return {
            "total": total,
            "by_status": by_status,
            "by_criterion": by_criterion,
            "pending": by_status.get("pending", 0),
            "answered": by_status.get("answered", 0),
            "skipped": by_status.get("skipped", 0),
            "expired": by_status.get("expired", 0)
        }
    
    def _apply_answer_to_requirement(
        self,
        conn: sqlite3.Connection,
        requirement_id: str,
        criterion: str,
        answer_text: str
    ) -> Optional[str]:
        """
        Apply user's answer to update the requirement text.
        
        Args:
            conn: SQLite connection
            requirement_id: Requirement ID
            criterion: Which criterion the answer addresses
            answer_text: User's answer
        
        Returns:
            Updated requirement text or None if failed
        """
        try:
            # Get current requirement text
            manifest = _db.get_manifest_by_id(conn, requirement_id)
            if not manifest:
                logger.warning(f"Manifest {requirement_id} not found")
                return None
            
            current_text = manifest["current_text"]
            
            # Apply answer based on criterion type
            # This is a simple approach - a more sophisticated implementation
            # would use LLM to intelligently incorporate the answer
            applied_text = self._merge_answer_into_requirement(
                current_text,
                criterion,
                answer_text
            )
            
            # Update manifest with new text
            if applied_text and applied_text != current_text:
                import hashlib
                new_checksum = hashlib.sha256(applied_text.encode('utf-8')).hexdigest()
                
                _db.update_manifest_text(conn, requirement_id, applied_text, new_checksum)
                
                # Add processing stage
                _db.add_processing_stage(
                    conn,
                    requirement_id=requirement_id,
                    stage_name="needs_user_input",
                    status="completed",
                    stage_metadata={
                        "criterion": criterion,
                        "answer": answer_text,
                        "applied": True
                    }
                )
                
                logger.info(f"Applied answer to requirement {requirement_id}")
                return applied_text
            
            return current_text
            
        except Exception as e:
            logger.error(f"Failed to apply answer to {requirement_id}: {e}")
            return None
    
    def _merge_answer_into_requirement(
        self,
        current_text: str,
        criterion: str,
        answer_text: str
    ) -> str:
        """
        Merge user's answer into requirement text.
        
        Simple implementation - appends relevant information based on criterion.
        A more advanced version would use LLM to intelligently rewrite.
        
        Args:
            current_text: Current requirement text
            criterion: Which criterion the answer addresses
            answer_text: User's answer
        
        Returns:
            Merged text
        """
        # Simple merge strategies per criterion
        if criterion == "measurability":
            # Append measurement as acceptance criterion
            if "Acceptance Criteria:" in current_text:
                return current_text.replace(
                    "Acceptance Criteria:",
                    f"Acceptance Criteria:\n- Measurement: {answer_text}"
                )
            else:
                return f"{current_text}\n\nAcceptance Criteria:\n- Measurement: {answer_text}"
        
        elif criterion == "testability":
            # Append test criteria
            if "Acceptance Criteria:" in current_text:
                return current_text.replace(
                    "Acceptance Criteria:",
                    f"Acceptance Criteria:\n- Test: {answer_text}"
                )
            else:
                return f"{current_text}\n\nAcceptance Criteria:\n- Test: {answer_text}"
        
        elif criterion in ["clarity", "unambiguous"]:
            # Add clarification note
            return f"{current_text}\n\n[Clarification: {answer_text}]"
        
        elif criterion == "atomic":
            # User decided on priority - just note it
            return f"{current_text}\n\n[Priority Decision: {answer_text}]"
        
        else:
            # Generic append
            return f"{current_text}\n\n[{criterion}: {answer_text}]"
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert SQLite Row to dictionary with parsed JSON fields."""
        d = dict(row)
        
        # Parse JSON fields
        if d.get("suggested_answers"):
            try:
                d["suggested_answers"] = json.loads(d["suggested_answers"])
            except json.JSONDecodeError:
                d["suggested_answers"] = []
        else:
            d["suggested_answers"] = []
        
        return d


__all__ = ["ClarificationService"]