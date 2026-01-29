"""
RAG Tools for MCP Server.

These tools handle semantic search and duplicate detection.
Uses direct Python imports for fast, in-process execution.
"""

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

logger = logging.getLogger("mcp_server.rag")


def register_rag_tools(server: Server) -> None:
    """Register RAG-related tools with the MCP server."""

    @server.list_tools()
    async def list_rag_tools() -> list[Tool]:
        """List available RAG tools."""
        return [
            Tool(
                name="find_duplicates",
                description="""Find semantic duplicate requirements.

Groups requirements by semantic similarity using vector embeddings.
Uses union-find clustering to group related requirements.

Parameters:
- requirements: List of requirement texts to analyze
- threshold: Similarity threshold (0-1, default: 0.85)

Returns: Groups of duplicate/similar requirements with similarity scores.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "requirements": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of requirement texts"
                        },
                        "threshold": {
                            "type": "number",
                            "default": 0.85,
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Similarity threshold"
                        }
                    },
                    "required": ["requirements"]
                }
            ),
            Tool(
                name="search_requirements",
                description="""Semantic search in the requirement knowledge base.

Find requirements similar to a query using vector embeddings.

Parameters:
- query: Search query text
- top_k: Number of results (default: 10)
- version: Requirement version/collection to search

Returns: Matching requirements with similarity scores.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "top_k": {
                            "type": "integer",
                            "default": 10,
                            "description": "Number of results"
                        },
                        "version": {
                            "type": "string",
                            "description": "Version/collection to search"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="find_related",
                description="""Find related requirements with relationship types.

Identifies relationships like:
- Similar: Semantically similar requirements
- Dependent: Requirements with dependencies
- Conflicting: Potentially conflicting requirements

Parameters:
- requirement: The requirement to find relations for
- relation_types: Filter by types (similar, dependent, conflicting)

Returns: Related requirements grouped by relationship type.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "requirement": {
                            "type": "string",
                            "description": "Requirement to analyze"
                        },
                        "relation_types": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["similar", "dependent", "conflicting"]
                            },
                            "description": "Relationship types to find"
                        }
                    },
                    "required": ["requirement"]
                }
            ),
            Tool(
                name="analyze_coverage",
                description="""Analyze requirement coverage across categories.

Identifies gaps and overlaps in requirement coverage.

Parameters:
- requirements: List of requirements to analyze
- categories: Expected categories to check coverage

Returns: Coverage report with gaps and suggestions.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "requirements": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Requirements to analyze"
                        },
                        "categories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Expected categories"
                        }
                    },
                    "required": ["requirements"]
                }
            )
        ]

    @server.call_tool()
    async def call_rag_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle RAG tool calls."""

        if name == "find_duplicates":
            return await _find_duplicates(
                requirements=arguments["requirements"],
                threshold=arguments.get("threshold", 0.85)
            )

        elif name == "search_requirements":
            return await _search_requirements(
                query=arguments["query"],
                top_k=arguments.get("top_k", 10),
                version=arguments.get("version")
            )

        elif name == "find_related":
            return await _find_related(
                requirement=arguments["requirement"],
                relation_types=arguments.get("relation_types")
            )

        elif name == "analyze_coverage":
            return await _analyze_coverage(
                requirements=arguments["requirements"],
                categories=arguments.get("categories")
            )

        return [TextContent(type="text", text=f"Unknown RAG tool: {name}")]


async def _find_duplicates(
    requirements: list[str],
    threshold: float = 0.85
) -> list[TextContent]:
    """Find duplicate requirements."""
    try:
        from arch_team.tools.rag_tools import find_duplicates

        logger.info(f"Finding duplicates in {len(requirements)} requirements (threshold={threshold})")

        result = await find_duplicates(requirements, threshold=threshold)

        # Format duplicate groups
        groups = result.get("groups", [])
        formatted_groups = []

        for i, group in enumerate(groups):
            if len(group) > 1:
                formatted_groups.append({
                    "group_id": i + 1,
                    "count": len(group),
                    "requirements": group,
                    "similarity": result.get("similarities", {}).get(str(i), threshold)
                })

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "total_requirements": len(requirements),
                "duplicate_groups": len(formatted_groups),
                "unique_requirements": len(requirements) - sum(g["count"] - 1 for g in formatted_groups),
                "groups": formatted_groups
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Duplicate detection error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _search_requirements(
    query: str,
    top_k: int = 10,
    version: str | None = None
) -> list[TextContent]:
    """Semantic search for requirements."""
    try:
        import httpx
        from ..config import config

        logger.info(f"Searching requirements: '{query}'")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.arch_team_url}/api/rag/search",
                json={
                    "query": query,
                    "top_k": top_k,
                    "version": version
                },
                timeout=30
            )
            response.raise_for_status()
            results = response.json()

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "query": query,
                "count": len(results.get("results", [])),
                "results": results.get("results", [])
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Search error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _find_related(
    requirement: str,
    relation_types: list[str] | None = None
) -> list[TextContent]:
    """Find related requirements."""
    try:
        import httpx
        from ..config import config

        logger.info(f"Finding related requirements")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.arch_team_url}/api/rag/related",
                json={
                    "requirement": requirement,
                    "relation_types": relation_types or ["similar", "dependent", "conflicting"]
                },
                timeout=30
            )
            response.raise_for_status()
            results = response.json()

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "requirement": requirement[:100] + "..." if len(requirement) > 100 else requirement,
                "related": results.get("related", {})
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Find related error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _analyze_coverage(
    requirements: list[str],
    categories: list[str] | None = None
) -> list[TextContent]:
    """Analyze requirement coverage."""
    try:
        import httpx
        from ..config import config

        # Default categories
        default_categories = [
            "functional",
            "security",
            "performance",
            "usability",
            "reliability",
            "maintainability"
        ]

        categories = categories or default_categories
        logger.info(f"Analyzing coverage for {len(requirements)} requirements")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.arch_team_url}/api/rag/coverage",
                json={
                    "requirements": requirements,
                    "categories": categories
                },
                timeout=60
            )
            response.raise_for_status()
            results = response.json()

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "total_requirements": len(requirements),
                "categories_analyzed": categories,
                "coverage": results.get("coverage", {}),
                "gaps": results.get("gaps", []),
                "suggestions": results.get("suggestions", [])
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Coverage analysis error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]
