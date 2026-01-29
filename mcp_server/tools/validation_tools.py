"""
Validation Tools for MCP Server.

These tools handle requirement validation against IEEE 29148 criteria.
Uses direct Python imports for fast, in-process execution.
"""

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

logger = logging.getLogger("mcp_server.validation")

# IEEE 29148 Quality Criteria
IEEE_CRITERIA = [
    "atomic",           # One requirement per statement
    "clarity",          # Clear, unambiguous language
    "testability",      # Can be verified/tested
    "measurability",    # Quantifiable metrics
    "concise",          # No unnecessary words
    "unambiguous",      # Single interpretation
    "consistent_language",  # Consistent terminology
    "design_independent",   # WHAT not HOW
    "purpose_independent"   # Business logic separation
]


def register_validation_tools(server: Server) -> None:
    """Register validation-related tools with the MCP server."""

    @server.list_tools()
    async def list_validation_tools() -> list[Tool]:
        """List available validation tools."""
        return [
            Tool(
                name="validate_requirements",
                description=f"""Validate requirements against IEEE 29148 quality criteria.

Evaluates each requirement against 9 criteria:
{', '.join(IEEE_CRITERIA)}

Each criterion is scored 0-1. Requirements with score >= 0.7 pass.

Parameters:
- requirements: List of requirement texts to validate
- mode: "quick" (auto-fix) or "guided" (collect questions)
- criteria: Optional subset of criteria to evaluate

Returns: Validation results with scores, verdicts, and improvement hints.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "requirements": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of requirement texts"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["quick", "guided"],
                            "default": "quick",
                            "description": "Validation mode"
                        },
                        "criteria": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific criteria to evaluate"
                        }
                    },
                    "required": ["requirements"]
                }
            ),
            Tool(
                name="enhance_requirement",
                description="""Improve a single requirement based on failing criteria.

Takes a requirement and its failing criteria, then rewrites it
to improve quality while preserving intent.

Parameters:
- requirement: The requirement text to improve
- failing_criteria: List of criteria that failed (e.g., ["testability", "clarity"])
- context: Optional additional context for enhancement

Returns: Enhanced requirement text with explanation of changes.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "requirement": {
                            "type": "string",
                            "description": "Requirement text to improve"
                        },
                        "failing_criteria": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of failing criteria"
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context"
                        }
                    },
                    "required": ["requirement", "failing_criteria"]
                }
            ),
            Tool(
                name="evaluate_single",
                description="""Evaluate a single requirement against all criteria.

Provides detailed feedback on each of the 9 IEEE 29148 criteria.

Parameters:
- requirement: The requirement text to evaluate

Returns: Detailed evaluation with per-criterion scores and reasoning.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "requirement": {
                            "type": "string",
                            "description": "Requirement text to evaluate"
                        }
                    },
                    "required": ["requirement"]
                }
            )
        ]

    @server.call_tool()
    async def call_validation_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle validation tool calls."""

        if name == "validate_requirements":
            return await _validate_requirements(
                requirements=arguments["requirements"],
                mode=arguments.get("mode", "quick"),
                criteria=arguments.get("criteria")
            )

        elif name == "enhance_requirement":
            return await _enhance_requirement(
                requirement=arguments["requirement"],
                failing_criteria=arguments["failing_criteria"],
                context=arguments.get("context")
            )

        elif name == "evaluate_single":
            return await _evaluate_single(
                requirement=arguments["requirement"]
            )

        return [TextContent(type="text", text=f"Unknown validation tool: {name}")]


async def _validate_requirements(
    requirements: list[str],
    mode: str = "quick",
    criteria: list[str] | None = None
) -> list[TextContent]:
    """Validate multiple requirements."""
    try:
        from arch_team.agents.batch_criteria_evaluator import BatchCriteriaEvaluator

        logger.info(f"Validating {len(requirements)} requirements in {mode} mode")

        evaluator = BatchCriteriaEvaluator()
        results = []

        for i, req_text in enumerate(requirements):
            try:
                # Evaluate all criteria
                scores = await evaluator.evaluate(req_text)

                # Filter to requested criteria if specified
                if criteria:
                    scores = {k: v for k, v in scores.items() if k in criteria}

                # Calculate overall score
                overall_score = sum(scores.values()) / len(scores) if scores else 0

                # Determine verdict
                failing = [k for k, v in scores.items() if v < 0.7]
                verdict = "pass" if overall_score >= 0.7 and not failing else "fail"

                results.append({
                    "index": i,
                    "requirement": req_text[:100] + "..." if len(req_text) > 100 else req_text,
                    "score": round(overall_score, 2),
                    "verdict": verdict,
                    "criteria_scores": {k: round(v, 2) for k, v in scores.items()},
                    "failing_criteria": failing
                })

            except Exception as e:
                results.append({
                    "index": i,
                    "requirement": req_text[:50] + "...",
                    "score": 0,
                    "verdict": "error",
                    "error": str(e)
                })

        # Summary statistics
        passed = sum(1 for r in results if r["verdict"] == "pass")
        failed = sum(1 for r in results if r["verdict"] == "fail")
        errors = sum(1 for r in results if r["verdict"] == "error")

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "mode": mode,
                "summary": {
                    "total": len(requirements),
                    "passed": passed,
                    "failed": failed,
                    "errors": errors,
                    "pass_rate": f"{passed/len(requirements)*100:.1f}%" if requirements else "0%"
                },
                "results": results
            }, indent=2)
        )]

    except ImportError as e:
        logger.error(f"Import error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": f"Module import failed: {str(e)}"
            }, indent=2)
        )]
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _enhance_requirement(
    requirement: str,
    failing_criteria: list[str],
    context: str | None = None
) -> list[TextContent]:
    """Enhance a single requirement."""
    try:
        from arch_team.tools.validation_tools import rewrite_with_feedback

        logger.info(f"Enhancing requirement with {len(failing_criteria)} failing criteria")

        # Build feedback from failing criteria
        feedback = f"Improve the following criteria: {', '.join(failing_criteria)}"
        if context:
            feedback += f"\nContext: {context}"

        # Call rewrite function
        result = await rewrite_with_feedback(requirement, feedback)

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "original": requirement,
                "enhanced": result.get("rewritten", requirement),
                "changes": result.get("changes", []),
                "criteria_addressed": failing_criteria
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Enhancement error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e),
                "original": requirement
            }, indent=2)
        )]


async def _evaluate_single(requirement: str) -> list[TextContent]:
    """Evaluate a single requirement in detail."""
    try:
        from arch_team.agents.batch_criteria_evaluator import BatchCriteriaEvaluator

        logger.info("Evaluating single requirement")

        evaluator = BatchCriteriaEvaluator()
        scores = await evaluator.evaluate(requirement)

        # Build detailed feedback
        feedback = []
        for criterion, score in scores.items():
            status = "PASS" if score >= 0.7 else "FAIL"
            feedback.append({
                "criterion": criterion,
                "score": round(score, 2),
                "status": status,
                "threshold": 0.7
            })

        overall = sum(scores.values()) / len(scores) if scores else 0
        passing = all(s >= 0.7 for s in scores.values())

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "requirement": requirement,
                "overall_score": round(overall, 2),
                "verdict": "pass" if passing else "fail",
                "criteria": feedback,
                "needs_improvement": [f["criterion"] for f in feedback if f["status"] == "FAIL"]
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Evaluation error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]
