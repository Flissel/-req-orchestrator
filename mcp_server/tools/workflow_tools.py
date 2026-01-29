"""
Workflow Tools for MCP Server.

These tools handle end-to-end orchestration workflows.
Uses REST + SSE for long-running operations with progress streaming.
"""

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

logger = logging.getLogger("mcp_server.workflow")


def register_workflow_tools(server: Server) -> None:
    """Register workflow orchestration tools with the MCP server."""

    @server.list_tools()
    async def list_workflow_tools() -> list[Tool]:
        """List available workflow tools."""
        return [
            Tool(
                name="run_full_workflow",
                description="""Execute the complete requirements engineering pipeline.

This is the master orchestration tool that runs:
1. Mining: Extract requirements from documents
2. Knowledge Graph: Build semantic relationships
3. Validation: Evaluate against IEEE 29148 criteria
4. Enhancement: Improve failing requirements
5. RAG: Detect duplicates and analyze coverage
6. QA: Final quality review

Parameters:
- files: List of file paths to process
- mode: "quick" (auto-enhance) or "guided" (collect questions)
- options: Additional workflow options

Returns: Complete analysis results with progress updates.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "File paths to process"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["quick", "guided"],
                            "default": "quick",
                            "description": "Processing mode"
                        },
                        "options": {
                            "type": "object",
                            "properties": {
                                "use_llm_kg": {
                                    "type": "boolean",
                                    "default": False,
                                    "description": "Use LLM for KG extraction"
                                },
                                "persist": {
                                    "type": "boolean",
                                    "default": True,
                                    "description": "Save results"
                                },
                                "max_iterations": {
                                    "type": "integer",
                                    "default": 3,
                                    "description": "Max enhancement iterations"
                                }
                            }
                        }
                    },
                    "required": ["files"]
                }
            ),
            Tool(
                name="get_clarification_questions",
                description="""Get clarification questions for failing requirements.

After validation, this tool generates targeted questions
to gather missing information for failing requirements.

Parameters:
- validation_results: Results from validate_requirements tool
- priority: Filter by priority (CRITICAL, HIGH, MEDIUM, LOW)

Returns: Prioritized list of clarification questions.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "validation_results": {
                            "type": "array",
                            "items": {
                                "type": "object"
                            },
                            "description": "Validation results"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW", "all"],
                            "default": "all",
                            "description": "Priority filter"
                        }
                    },
                    "required": ["validation_results"]
                }
            ),
            Tool(
                name="apply_answers",
                description="""Apply user answers to clarification questions and re-validate.

Takes answers to clarification questions and uses them
to improve requirements, then re-validates.

Parameters:
- answers: List of {question_id, answer} pairs

Returns: Re-validation results showing improvements.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "answers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question_id": {"type": "string"},
                                    "answer": {"type": "string"}
                                },
                                "required": ["question_id", "answer"]
                            },
                            "description": "Answers to questions"
                        }
                    },
                    "required": ["answers"]
                }
            ),
            Tool(
                name="get_project_status",
                description="""Get current workflow status and statistics.

Returns overall project status including:
- Requirements counts (mined, validated, passed, failed)
- Current workflow state
- Recent activity

Parameters:
- project_id: Optional project ID (uses current if not specified)

Returns: Project status summary.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "Project ID"
                        }
                    }
                }
            ),
            Tool(
                name="export_requirements",
                description="""Export validated requirements to various formats.

Parameters:
- format: Output format (markdown, json, csv)
- include_scores: Include validation scores (default: true)
- filter_passed: Only export passed requirements (default: false)

Returns: Formatted requirements export.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "enum": ["markdown", "json", "csv"],
                            "default": "markdown",
                            "description": "Output format"
                        },
                        "include_scores": {
                            "type": "boolean",
                            "default": True,
                            "description": "Include scores"
                        },
                        "filter_passed": {
                            "type": "boolean",
                            "default": False,
                            "description": "Only passed requirements"
                        }
                    }
                }
            )
        ]

    @server.call_tool()
    async def call_workflow_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle workflow tool calls."""

        if name == "run_full_workflow":
            return await _run_full_workflow(
                files=arguments["files"],
                mode=arguments.get("mode", "quick"),
                options=arguments.get("options", {})
            )

        elif name == "get_clarification_questions":
            return await _get_clarification_questions(
                validation_results=arguments["validation_results"],
                priority=arguments.get("priority", "all")
            )

        elif name == "apply_answers":
            return await _apply_answers(
                answers=arguments["answers"]
            )

        elif name == "get_project_status":
            return await _get_project_status(
                project_id=arguments.get("project_id")
            )

        elif name == "export_requirements":
            return await _export_requirements(
                format=arguments.get("format", "markdown"),
                include_scores=arguments.get("include_scores", True),
                filter_passed=arguments.get("filter_passed", False)
            )

        return [TextContent(type="text", text=f"Unknown workflow tool: {name}")]


async def _run_full_workflow(
    files: list[str],
    mode: str = "quick",
    options: dict = None
) -> list[TextContent]:
    """Run the complete workflow pipeline."""
    try:
        import httpx
        from pathlib import Path
        from ..config import config

        options = options or {}
        logger.info(f"Running full workflow on {len(files)} files (mode={mode})")

        # Validate files exist
        valid_files = []
        for f in files:
            path = Path(f)
            if path.exists():
                valid_files.append(path)
            else:
                logger.warning(f"File not found: {f}")

        if not valid_files:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "No valid files found",
                    "files_requested": files
                }, indent=2)
            )]

        # Use REST API with multipart upload for full workflow
        # This is a long-running operation, so we use the REST endpoint
        async with httpx.AsyncClient(timeout=config.stream_timeout) as client:
            # Prepare multipart files
            files_data = []
            for path in valid_files:
                files_data.append(
                    ("files", (path.name, open(path, "rb"), "application/octet-stream"))
                )

            response = await client.post(
                f"{config.arch_team_url}/api/arch_team/process",
                files=files_data,
                data={
                    "mode": mode,
                    "use_llm_kg": str(options.get("use_llm_kg", False)).lower(),
                    "persist": str(options.get("persist", True)).lower()
                }
            )
            response.raise_for_status()
            result = response.json()

        # Close file handles
        for _, (_, handle, _) in files_data:
            handle.close()

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "mode": mode,
                "files_processed": [str(p) for p in valid_files],
                "phases": {
                    "mining": {
                        "count": result.get("mining_count", 0),
                        "status": "completed"
                    },
                    "knowledge_graph": {
                        "nodes": result.get("kg_nodes", 0),
                        "edges": result.get("kg_edges", 0),
                        "status": "completed"
                    },
                    "validation": {
                        "total": result.get("validation_total", 0),
                        "passed": result.get("validation_passed", 0),
                        "failed": result.get("validation_failed", 0),
                        "status": "completed"
                    },
                    "duplicates": {
                        "groups": result.get("duplicate_groups", 0),
                        "status": "completed"
                    }
                },
                "requirements": result.get("requirements", []),
                "clarification_questions": result.get("questions", []) if mode == "guided" else []
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Full workflow error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _get_clarification_questions(
    validation_results: list[dict],
    priority: str = "all"
) -> list[TextContent]:
    """Get clarification questions for failing requirements."""
    try:
        import httpx
        from ..config import config

        # Filter to failing requirements
        failing = [r for r in validation_results if r.get("verdict") == "fail"]

        if not failing:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "message": "No failing requirements to clarify",
                    "questions": []
                }, indent=2)
            )]

        logger.info(f"Generating questions for {len(failing)} failing requirements")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.backend_url}/api/v1/clarifications/pending",
                params={"priority": priority if priority != "all" else None},
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

        questions = result.get("questions", [])

        # Group by priority
        by_priority = {}
        for q in questions:
            p = q.get("priority", "MEDIUM")
            if p not in by_priority:
                by_priority[p] = []
            by_priority[p].append(q)

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "total_questions": len(questions),
                "by_priority": {k: len(v) for k, v in by_priority.items()},
                "questions": questions
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Clarification questions error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _apply_answers(answers: list[dict]) -> list[TextContent]:
    """Apply answers and re-validate."""
    try:
        import httpx
        from ..config import config

        logger.info(f"Applying {len(answers)} answers")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.backend_url}/api/v1/validate/all-in-one/apply-answers",
                json={"answers": answers},
                timeout=120
            )
            response.raise_for_status()
            result = response.json()

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "answers_applied": len(answers),
                "improvements": result.get("improvements", []),
                "revalidation": result.get("revalidation", {})
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Apply answers error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _get_project_status(project_id: str | None = None) -> list[TextContent]:
    """Get project status."""
    try:
        import httpx
        from ..config import config

        logger.info(f"Getting project status (id={project_id})")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.backend_url}/api/v1/validation/analytics",
                timeout=30
            )
            response.raise_for_status()
            analytics = response.json()

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "project_id": project_id or "current",
                "status": {
                    "requirements": {
                        "total": analytics.get("total", 0),
                        "passed": analytics.get("passed", 0),
                        "failed": analytics.get("failed", 0),
                        "pass_rate": analytics.get("pass_rate", "0%")
                    },
                    "average_score": analytics.get("average_score", 0),
                    "criteria_stats": analytics.get("criteria_stats", {})
                }
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Project status error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _export_requirements(
    format: str = "markdown",
    include_scores: bool = True,
    filter_passed: bool = False
) -> list[TextContent]:
    """Export requirements."""
    try:
        import httpx
        from ..config import config

        logger.info(f"Exporting requirements as {format}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.arch_team_url}/api/mining/report",
                json={
                    "format": format,
                    "include_scores": include_scores,
                    "filter_passed": filter_passed
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()

        if format == "markdown":
            return [TextContent(
                type="text",
                text=result.get("markdown", "No requirements to export")
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "format": format,
                    "count": result.get("count", 0),
                    "data": result.get("data", [])
                }, indent=2)
            )]

    except Exception as e:
        logger.error(f"Export error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]
