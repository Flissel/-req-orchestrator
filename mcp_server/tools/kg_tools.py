"""
Knowledge Graph Tools for MCP Server.

These tools handle knowledge graph construction and querying.
Uses direct Python imports for fast, in-process execution.
"""

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

logger = logging.getLogger("mcp_server.kg")


def register_kg_tools(server: Server) -> None:
    """Register knowledge graph tools with the MCP server."""

    @server.list_tools()
    async def list_kg_tools() -> list[Tool]:
        """List available KG tools."""
        return [
            Tool(
                name="build_knowledge_graph",
                description="""Build a semantic knowledge graph from requirements.

Creates nodes and edges representing relationships between:
- Requirements
- Tags (functional, security, performance, etc.)
- Actors (users, systems, components)
- Entities (data objects, resources)
- Actions (verbs/operations)

Relationships captured:
- HAS_TAG: Requirement -> Tag
- HAS_ACTOR: Requirement -> Actor
- HAS_ACTION: Requirement -> Action
- ON_ENTITY: Action -> Entity

Parameters:
- requirements: List of requirement DTOs (from mining)
- use_llm: Use LLM for enhanced extraction (default: false)
- persist: Save to Qdrant (default: true)

Returns: Graph statistics with node/edge counts.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "requirements": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "req_id": {"type": "string"},
                                    "title": {"type": "string"},
                                    "tag": {"type": "string"}
                                }
                            },
                            "description": "List of requirement DTOs"
                        },
                        "use_llm": {
                            "type": "boolean",
                            "default": False,
                            "description": "Use LLM for enhanced extraction"
                        },
                        "persist": {
                            "type": "boolean",
                            "default": True,
                            "description": "Save to Qdrant"
                        }
                    },
                    "required": ["requirements"]
                }
            ),
            Tool(
                name="search_kg_nodes",
                description="""Semantic search for nodes in the knowledge graph.

Find requirements, actors, entities, or actions by semantic similarity.

Parameters:
- query: Search query text
- node_type: Filter by type (Requirement, Actor, Entity, Action, Tag)
- top_k: Number of results (default: 10)

Returns: Matching nodes with similarity scores.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "node_type": {
                            "type": "string",
                            "enum": ["Requirement", "Actor", "Entity", "Action", "Tag", "all"],
                            "default": "all",
                            "description": "Node type filter"
                        },
                        "top_k": {
                            "type": "integer",
                            "default": 10,
                            "description": "Number of results"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="get_kg_neighbors",
                description="""Find neighbors of a node in the knowledge graph.

Get 1-hop connected nodes with their relationships.

Parameters:
- node_id: ID of the node to explore
- direction: "in", "out", or "both" (default: both)
- rel_types: Filter by relationship types

Returns: Connected nodes with relationship details.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {
                            "type": "string",
                            "description": "Node ID to explore"
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["in", "out", "both"],
                            "default": "both",
                            "description": "Edge direction"
                        },
                        "rel_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Relationship type filter"
                        }
                    },
                    "required": ["node_id"]
                }
            ),
            Tool(
                name="export_knowledge_graph",
                description="""Export the entire knowledge graph.

Returns all nodes and edges for visualization or analysis.

Parameters:
- format: Output format (json, cypher, graphml)

Returns: Complete graph data.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "enum": ["json", "cypher", "graphml"],
                            "default": "json",
                            "description": "Output format"
                        }
                    }
                }
            )
        ]

    @server.call_tool()
    async def call_kg_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle KG tool calls."""

        if name == "build_knowledge_graph":
            return await _build_knowledge_graph(
                requirements=arguments["requirements"],
                use_llm=arguments.get("use_llm", False),
                persist=arguments.get("persist", True)
            )

        elif name == "search_kg_nodes":
            return await _search_kg_nodes(
                query=arguments["query"],
                node_type=arguments.get("node_type", "all"),
                top_k=arguments.get("top_k", 10)
            )

        elif name == "get_kg_neighbors":
            return await _get_kg_neighbors(
                node_id=arguments["node_id"],
                direction=arguments.get("direction", "both"),
                rel_types=arguments.get("rel_types")
            )

        elif name == "export_knowledge_graph":
            return await _export_knowledge_graph(
                format=arguments.get("format", "json")
            )

        return [TextContent(type="text", text=f"Unknown KG tool: {name}")]


async def _build_knowledge_graph(
    requirements: list[dict],
    use_llm: bool = False,
    persist: bool = True
) -> list[TextContent]:
    """Build knowledge graph from requirements."""
    try:
        from arch_team.agents.kg_agent import KGAbstractionAgent

        logger.info(f"Building KG from {len(requirements)} requirements (use_llm={use_llm})")

        agent = KGAbstractionAgent()
        result = await agent.run(
            requirements,
            options={
                "use_llm": use_llm,
                "llm_fallback": True,
                "persist": "qdrant" if persist else "none"
            }
        )

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "stats": {
                    "nodes": result.get("node_count", 0),
                    "edges": result.get("edge_count", 0),
                    "requirements_processed": len(requirements)
                },
                "node_types": result.get("node_types", {}),
                "edge_types": result.get("edge_types", {}),
                "persisted": persist
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"KG build error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _search_kg_nodes(
    query: str,
    node_type: str = "all",
    top_k: int = 10
) -> list[TextContent]:
    """Search knowledge graph nodes."""
    try:
        import httpx
        from ..config import config

        logger.info(f"Searching KG nodes: '{query}' (type={node_type})")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.arch_team_url}/api/kg/search/nodes",
                params={
                    "query": query,
                    "top_k": top_k,
                    "node_type": node_type if node_type != "all" else None
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
                "count": len(results.get("nodes", [])),
                "nodes": results.get("nodes", [])
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"KG search error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _get_kg_neighbors(
    node_id: str,
    direction: str = "both",
    rel_types: list[str] | None = None
) -> list[TextContent]:
    """Get neighbors of a KG node."""
    try:
        import httpx
        from ..config import config

        logger.info(f"Getting neighbors of node: {node_id}")

        params = {
            "node_id": node_id,
            "dir": direction,
            "limit": 200
        }
        if rel_types:
            params["rel"] = ",".join(rel_types)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.arch_team_url}/api/kg/neighbors",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            results = response.json()

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "node_id": node_id,
                "neighbor_count": len(results.get("neighbors", [])),
                "neighbors": results.get("neighbors", [])
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"KG neighbors error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _export_knowledge_graph(format: str = "json") -> list[TextContent]:
    """Export the entire knowledge graph."""
    try:
        import httpx
        from ..config import config

        logger.info(f"Exporting KG in {format} format")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.arch_team_url}/api/kg/export",
                timeout=60
            )
            response.raise_for_status()
            data = response.json()

        if format == "json":
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "format": "json",
                    "node_count": len(data.get("nodes", [])),
                    "edge_count": len(data.get("edges", [])),
                    "nodes": data.get("nodes", []),
                    "edges": data.get("edges", [])
                }, indent=2)
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Format {format} not yet implemented"
                }, indent=2)
            )]

    except Exception as e:
        logger.error(f"KG export error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]
