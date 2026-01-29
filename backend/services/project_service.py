# -*- coding: utf-8 -*-
"""
ProjectService - Manages TechStack-generated project metadata

Handles CRUD operations for project metadata and requirement linkage.
Projects are created by TechStack and persisted with metadata in SQLite.
"""

from __future__ import annotations

import json
import uuid
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from .ports import RequestContext, ServiceError
from backend.core import db as _db
from backend.schemas import (
    ProjectMetadata,
    ValidationSummary,
    ProjectListResponse,
    CreateProjectResponse,
)


def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def _generate_project_id(project_name: str) -> str:
    """Generate unique project ID from name + short UUID"""
    slug = _slugify(project_name)[:30]
    short_uuid = str(uuid.uuid4())[:8]
    return f"proj-{slug}-{short_uuid}"


class ProjectService:
    """
    Service for managing TechStack-generated project metadata.

    Operations:
    - create_project_record: Store project metadata after generation
    - get_project: Retrieve project by ID
    - list_projects: List projects with filters
    - get_project_requirements: Get linked requirements
    - delete_project: Remove project record
    - compute_validation_summary: Calculate validation stats from requirements
    """

    def create_project_record(
        self,
        conn,
        project_name: str,
        project_path: str,
        template_id: str,
        template_name: Optional[str] = None,
        template_category: Optional[str] = None,
        tech_stack: Optional[List[str]] = None,
        requirements: Optional[List[Dict[str, Any]]] = None,
        requirement_ids: Optional[List[str]] = None,
        source_file: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ctx: Optional[RequestContext] = None,
    ) -> CreateProjectResponse:
        """
        Create a project metadata record and link requirements.

        Args:
            conn: Database connection
            project_name: Human-readable project name
            project_path: Filesystem path to project
            template_id: Template used
            template_name: Template display name
            template_category: Template category
            tech_stack: List of technologies
            requirements: Raw requirement objects (for counting/summary)
            requirement_ids: Requirement IDs to link from database
            source_file: Original source file
            metadata: Additional metadata
            ctx: Request context

        Returns:
            CreateProjectResponse with project details
        """
        try:
            project_id = _generate_project_id(project_name)

            # Compute validation summary from requirements
            validation_summary = None
            requirements_count = 0

            if requirements:
                requirements_count = len(requirements)
                validation_summary = self._compute_validation_summary(requirements)
            elif requirement_ids:
                requirements_count = len(requirement_ids)
                # Optionally compute from linked requirements later

            # Create the project record
            _db.create_project(
                conn=conn,
                project_id=project_id,
                project_name=project_name,
                project_path=project_path,
                template_id=template_id,
                template_name=template_name,
                template_category=template_category,
                tech_stack=tech_stack,
                requirements_count=requirements_count,
                source_file=source_file,
                validation_summary=validation_summary,
                metadata=metadata,
            )

            # Link requirements if IDs provided
            linked_count = 0
            if requirement_ids:
                linked_count = _db.link_project_requirements_batch(
                    conn, project_id, requirement_ids
                )

            return CreateProjectResponse(
                success=True,
                project_id=project_id,
                project_name=project_name,
                project_path=project_path,
                files_created=0,  # Set by caller
                requirements_linked=linked_count,
                template_id=template_id,
                message=f"Project '{project_name}' created successfully"
            )

        except Exception as e:
            raise ServiceError(
                "project_create_failed",
                f"Failed to create project record: {str(e)}",
                details={
                    "project_name": project_name,
                    "template_id": template_id,
                    "request_id": getattr(ctx, "request_id", None)
                }
            ) from e

    def get_project(
        self,
        conn,
        project_id: str,
        include_requirements: bool = False,
        ctx: Optional[RequestContext] = None,
    ) -> Optional[ProjectMetadata]:
        """
        Get project metadata by ID.

        Args:
            conn: Database connection
            project_id: Project ID
            include_requirements: If True, include linked requirement IDs
            ctx: Request context

        Returns:
            ProjectMetadata or None if not found
        """
        try:
            row = _db.get_project_by_id(conn, project_id)
            if not row:
                return None

            # Parse JSON fields
            tech_stack = json.loads(row["tech_stack"]) if row["tech_stack"] else []
            validation_summary_data = json.loads(row["validation_summary"]) if row["validation_summary"] else None
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}

            validation_summary = None
            if validation_summary_data:
                validation_summary = ValidationSummary(**validation_summary_data)

            linked_requirements = []
            if include_requirements:
                linked_requirements = _db.get_project_requirement_ids(conn, project_id)

            return ProjectMetadata(
                project_id=row["project_id"],
                project_name=row["project_name"],
                project_path=row["project_path"],
                template_id=row["template_id"],
                template_name=row["template_name"],
                template_category=row["template_category"],
                tech_stack=tech_stack,
                requirements_count=row["requirements_count"] or 0,
                source_file=row["source_file"],
                validation_summary=validation_summary,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                metadata=metadata,
                linked_requirements=linked_requirements,
            )

        except Exception as e:
            raise ServiceError(
                "project_get_failed",
                f"Failed to get project: {str(e)}",
                details={
                    "project_id": project_id,
                    "request_id": getattr(ctx, "request_id", None)
                }
            ) from e

    def list_projects(
        self,
        conn,
        limit: int = 100,
        offset: int = 0,
        template_id: Optional[str] = None,
        category: Optional[str] = None,
        ctx: Optional[RequestContext] = None,
    ) -> ProjectListResponse:
        """
        List projects with optional filters.

        Args:
            conn: Database connection
            limit: Maximum results
            offset: Skip N results
            template_id: Filter by template
            category: Filter by category
            ctx: Request context

        Returns:
            ProjectListResponse with projects and total count
        """
        try:
            rows = _db.list_projects(
                conn,
                limit=limit,
                offset=offset,
                template_id=template_id,
                category=category,
            )
            total = _db.count_projects(conn)

            projects = []
            for row in rows:
                tech_stack = json.loads(row["tech_stack"]) if row["tech_stack"] else []
                validation_summary_data = json.loads(row["validation_summary"]) if row["validation_summary"] else None
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}

                validation_summary = None
                if validation_summary_data:
                    validation_summary = ValidationSummary(**validation_summary_data)

                projects.append(ProjectMetadata(
                    project_id=row["project_id"],
                    project_name=row["project_name"],
                    project_path=row["project_path"],
                    template_id=row["template_id"],
                    template_name=row["template_name"],
                    template_category=row["template_category"],
                    tech_stack=tech_stack,
                    requirements_count=row["requirements_count"] or 0,
                    source_file=row["source_file"],
                    validation_summary=validation_summary,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    metadata=metadata,
                ))

            return ProjectListResponse(projects=projects, total=total)

        except Exception as e:
            raise ServiceError(
                "project_list_failed",
                f"Failed to list projects: {str(e)}",
                details={"request_id": getattr(ctx, "request_id", None)}
            ) from e

    def get_project_requirements(
        self,
        conn,
        project_id: str,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all requirements linked to a project.

        Args:
            conn: Database connection
            project_id: Project ID
            ctx: Request context

        Returns:
            List of requirement dictionaries
        """
        try:
            rows = _db.get_project_requirements(conn, project_id)
            return [dict(row) for row in rows]
        except Exception as e:
            raise ServiceError(
                "project_requirements_failed",
                f"Failed to get project requirements: {str(e)}",
                details={
                    "project_id": project_id,
                    "request_id": getattr(ctx, "request_id", None)
                }
            ) from e

    def delete_project(
        self,
        conn,
        project_id: str,
        ctx: Optional[RequestContext] = None,
    ) -> bool:
        """
        Delete a project record.

        Note: This does NOT delete the project files from filesystem,
        only the metadata record and requirement links.

        Args:
            conn: Database connection
            project_id: Project ID
            ctx: Request context

        Returns:
            True if deleted, False if not found
        """
        try:
            return _db.delete_project(conn, project_id)
        except Exception as e:
            raise ServiceError(
                "project_delete_failed",
                f"Failed to delete project: {str(e)}",
                details={
                    "project_id": project_id,
                    "request_id": getattr(ctx, "request_id", None)
                }
            ) from e

    def _compute_validation_summary(
        self,
        requirements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute validation summary from requirements list.

        Args:
            requirements: List of requirement objects with validation data

        Returns:
            Dictionary with total, passed, failed, avg_score
        """
        total = len(requirements)
        if total == 0:
            return {"total": 0, "passed": 0, "failed": 0, "avg_score": 0.0}

        passed = 0
        failed = 0
        scores = []

        for req in requirements:
            # Try different field names for score
            score = req.get("validation_score") or req.get("score") or req.get("overall_score")
            verdict = req.get("validation_verdict") or req.get("verdict")

            if score is not None:
                try:
                    score = float(score)
                    scores.append(score)
                except (ValueError, TypeError):
                    pass

            if verdict == "pass" or (score is not None and score >= 0.7):
                passed += 1
            elif verdict == "fail" or (score is not None and score < 0.7):
                failed += 1

        avg_score = sum(scores) / len(scores) if scores else 0.0

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "avg_score": round(avg_score, 3),
        }


# Singleton instance for convenience
_project_service: Optional[ProjectService] = None


def get_project_service() -> ProjectService:
    """Get or create the ProjectService singleton"""
    global _project_service
    if _project_service is None:
        _project_service = ProjectService()
    return _project_service
