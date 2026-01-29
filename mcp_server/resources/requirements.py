"""
Requirements Resources for MCP Server.

Exposes requirement data and project context to Claude.
"""

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import Resource, TextContent

logger = logging.getLogger("mcp_server.resources")


def register_requirement_resources(server: Server) -> None:
    """Register requirement-related resources with the MCP server."""

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        """List available resources."""
        return [
            Resource(
                uri="requirements://current",
                name="Current Requirements",
                description="All requirements in the current session with validation status",
                mimeType="application/json"
            ),
            Resource(
                uri="projects://list",
                name="Project List",
                description="All available projects with metadata",
                mimeType="application/json"
            ),
            Resource(
                uri="templates://all",
                name="Project Templates",
                description="All 15 available project templates",
                mimeType="application/json"
            ),
            Resource(
                uri="criteria://ieee29148",
                name="IEEE 29148 Criteria",
                description="The 9 quality criteria for requirement validation",
                mimeType="application/json"
            ),
            Resource(
                uri="config://runtime",
                name="Runtime Configuration",
                description="Current system configuration and status",
                mimeType="application/json"
            )
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        """Read a specific resource."""

        if uri == "requirements://current":
            return await _get_current_requirements()

        elif uri == "projects://list":
            return await _get_projects_list()

        elif uri == "templates://all":
            return await _get_all_templates()

        elif uri == "criteria://ieee29148":
            return _get_ieee_criteria()

        elif uri == "config://runtime":
            return await _get_runtime_config()

        return json.dumps({"error": f"Unknown resource: {uri}"})


async def _get_current_requirements() -> str:
    """Get current requirements with validation status."""
    try:
        import httpx
        from ..config import config

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.backend_url}/api/v1/validation/analytics",
                timeout=30
            )
            response.raise_for_status()
            analytics = response.json()

        return json.dumps({
            "total": analytics.get("total", 0),
            "passed": analytics.get("passed", 0),
            "failed": analytics.get("failed", 0),
            "pass_rate": analytics.get("pass_rate", "0%"),
            "average_score": analytics.get("average_score", 0),
            "criteria_stats": analytics.get("criteria_stats", {})
        }, indent=2)

    except Exception as e:
        logger.error(f"Error getting requirements: {e}")
        return json.dumps({"error": str(e)})


async def _get_projects_list() -> str:
    """Get list of all projects."""
    try:
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        projects_dir = project_root / "projects"

        projects = []
        if projects_dir.exists():
            for project_dir in sorted(projects_dir.iterdir()):
                if project_dir.is_dir():
                    meta_path = project_dir / "meta.json"
                    meta = {}
                    if meta_path.exists():
                        try:
                            meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        except:
                            pass

                    projects.append({
                        "id": project_dir.name,
                        "name": meta.get("name", project_dir.name),
                        "description": meta.get("description", ""),
                        "created": meta.get("created", ""),
                        "template": meta.get("template", "")
                    })

        return json.dumps({
            "count": len(projects),
            "projects": projects
        }, indent=2)

    except Exception as e:
        logger.error(f"Error getting projects: {e}")
        return json.dumps({"error": str(e)})


async def _get_all_templates() -> str:
    """Get all project templates."""
    try:
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        templates_dir = project_root / "templates"

        templates = []
        if templates_dir.exists():
            for template_dir in sorted(templates_dir.iterdir()):
                if template_dir.is_dir() and template_dir.name[0].isdigit():
                    meta_path = template_dir / "meta.json"
                    meta = {}
                    if meta_path.exists():
                        try:
                            meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        except:
                            pass

                    templates.append({
                        "id": template_dir.name,
                        "name": meta.get("name", template_dir.name),
                        "description": meta.get("description", ""),
                        "stack": meta.get("stack", []),
                        "has_questions": (template_dir / "QUESTIONS.md").exists(),
                        "has_coding_rules": (template_dir / "CODING_RULES.md").exists()
                    })

        return json.dumps({
            "count": len(templates),
            "templates": templates
        }, indent=2)

    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        return json.dumps({"error": str(e)})


def _get_ieee_criteria() -> str:
    """Get IEEE 29148 quality criteria definitions."""
    criteria = {
        "criteria": [
            {
                "id": "atomic",
                "name": "Atomic",
                "description": "Requirement contains one and only one requirement statement",
                "threshold": 0.7,
                "examples": {
                    "good": "The system shall display an error message when login fails.",
                    "bad": "The system shall display an error message when login fails and log the attempt and notify the admin."
                }
            },
            {
                "id": "clarity",
                "name": "Clarity",
                "description": "Requirement is clear and uses precise language without jargon",
                "threshold": 0.7,
                "examples": {
                    "good": "The system shall respond to user requests within 2 seconds.",
                    "bad": "The system shall be fast."
                }
            },
            {
                "id": "testability",
                "name": "Testability",
                "description": "Requirement can be verified through testing or inspection",
                "threshold": 0.7,
                "examples": {
                    "good": "The system shall support at least 1000 concurrent users.",
                    "bad": "The system shall handle many users efficiently."
                }
            },
            {
                "id": "measurability",
                "name": "Measurability",
                "description": "Requirement contains quantifiable metrics or acceptance criteria",
                "threshold": 0.7,
                "examples": {
                    "good": "The system shall process transactions in under 500ms.",
                    "bad": "The system shall process transactions quickly."
                }
            },
            {
                "id": "concise",
                "name": "Concise",
                "description": "Requirement is brief and free of unnecessary words",
                "threshold": 0.7,
                "examples": {
                    "good": "Users shall authenticate using email and password.",
                    "bad": "It is required that users of the system shall be able to authenticate themselves using their email address and their password credentials."
                }
            },
            {
                "id": "unambiguous",
                "name": "Unambiguous",
                "description": "Requirement has only one possible interpretation",
                "threshold": 0.7,
                "examples": {
                    "good": "The system shall encrypt passwords using SHA-256.",
                    "bad": "The system shall properly secure passwords."
                }
            },
            {
                "id": "consistent_language",
                "name": "Consistent Language",
                "description": "Requirement uses consistent terminology throughout",
                "threshold": 0.7,
                "examples": {
                    "good": "The user shall log in to access the dashboard.",
                    "bad": "The user shall sign in to access the home screen (also called dashboard)."
                }
            },
            {
                "id": "design_independent",
                "name": "Design Independent",
                "description": "Requirement specifies WHAT not HOW (no implementation details)",
                "threshold": 0.7,
                "examples": {
                    "good": "The system shall store user preferences persistently.",
                    "bad": "The system shall store user preferences in a MySQL database table named 'user_prefs'."
                }
            },
            {
                "id": "purpose_independent",
                "name": "Purpose Independent",
                "description": "Requirement focuses on functionality, not business justification",
                "threshold": 0.7,
                "examples": {
                    "good": "The system shall generate monthly sales reports.",
                    "bad": "To improve business insights, the system shall generate monthly sales reports."
                }
            }
        ],
        "scoring": {
            "per_criterion_threshold": 0.7,
            "overall_pass_threshold": 0.7,
            "verdict_rules": [
                "PASS: Overall score >= 0.7 AND no criterion below 0.7",
                "FAIL: Overall score < 0.7 OR any criterion below 0.7"
            ]
        }
    }
    return json.dumps(criteria, indent=2)


async def _get_runtime_config() -> str:
    """Get current runtime configuration."""
    try:
        import httpx
        from ..config import config

        # Get backend status
        backend_status = "unknown"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{config.backend_url}/health",
                    timeout=5
                )
                backend_status = "healthy" if response.status_code == 200 else "unhealthy"
        except:
            backend_status = "unreachable"

        # Get arch_team status
        arch_team_status = "unknown"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{config.arch_team_url}/health",
                    timeout=5
                )
                arch_team_status = "healthy" if response.status_code == 200 else "unhealthy"
        except:
            arch_team_status = "unreachable"

        return json.dumps({
            "mcp_server": {
                "name": config.server_name,
                "version": config.server_version
            },
            "services": {
                "backend": {
                    "url": config.backend_url,
                    "status": backend_status
                },
                "arch_team": {
                    "url": config.arch_team_url,
                    "status": arch_team_status
                }
            },
            "timeouts": {
                "default": f"{config.default_timeout}ms",
                "stream": f"{config.stream_timeout}ms"
            }
        }, indent=2)

    except Exception as e:
        logger.error(f"Error getting runtime config: {e}")
        return json.dumps({"error": str(e)})
