"""
Mining Tools for MCP Server.

These tools handle document mining and requirement extraction.
Uses direct Python imports for fast, in-process execution.
"""

import json
import logging
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

logger = logging.getLogger("mcp_server.mining")


def register_mining_tools(server: Server) -> None:
    """Register mining-related tools with the MCP server."""

    @server.list_tools()
    async def list_mining_tools() -> list[Tool]:
        """List available mining tools."""
        return [
            Tool(
                name="mine_documents",
                description="""Extract requirements from documents.

Analyzes documents (markdown, PDF, text) and extracts structured requirements.
Each requirement includes:
- req_id: Unique identifier
- title: The requirement text
- tag: Category (functional, security, performance, ux, ops)
- evidence_refs: Source references with chunk indexes

Parameters:
- files: List of file paths to process
- chunk_size: Token size per chunk (default: 1000)
- neighbor_refs: Include ±1 chunk context (default: true)

Returns: List of extracted requirement DTOs with evidence tracking.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of file paths to mine"
                        },
                        "chunk_size": {
                            "type": "integer",
                            "default": 1000,
                            "description": "Token chunk size"
                        },
                        "neighbor_refs": {
                            "type": "boolean",
                            "default": True,
                            "description": "Include neighbor chunk context"
                        }
                    },
                    "required": ["files"]
                }
            ),
            Tool(
                name="mine_text",
                description="""Extract requirements from raw text.

Similar to mine_documents but works with text content directly.
Useful for processing clipboard content or inline text.

Parameters:
- text: The text content to analyze
- source_name: Optional name for the source (for evidence tracking)
- chunk_size: Token size per chunk (default: 1000)

Returns: List of extracted requirement DTOs.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text content to mine"
                        },
                        "source_name": {
                            "type": "string",
                            "default": "inline_text",
                            "description": "Name for evidence tracking"
                        },
                        "chunk_size": {
                            "type": "integer",
                            "default": 1000,
                            "description": "Token chunk size"
                        }
                    },
                    "required": ["text"]
                }
            )
        ]

    @server.call_tool()
    async def call_mining_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle mining tool calls."""

        if name == "mine_documents":
            return await _mine_documents(
                files=arguments["files"],
                chunk_size=arguments.get("chunk_size", 1000),
                neighbor_refs=arguments.get("neighbor_refs", True)
            )

        elif name == "mine_text":
            return await _mine_text(
                text=arguments["text"],
                source_name=arguments.get("source_name", "inline_text"),
                chunk_size=arguments.get("chunk_size", 1000)
            )

        return [TextContent(type="text", text=f"Unknown mining tool: {name}")]


async def _mine_documents(
    files: list[str],
    chunk_size: int = 1000,
    neighbor_refs: bool = True
) -> list[TextContent]:
    """Mine requirements from document files."""
    try:
        # Import ChunkMinerAgent directly for fast execution
        from arch_team.agents.chunk_miner import ChunkMinerAgent

        logger.info(f"Mining {len(files)} files with chunk_size={chunk_size}")

        # Validate files exist
        valid_files = []
        for f in files:
            path = Path(f)
            if path.exists():
                valid_files.append(str(path))
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

        # Initialize miner and extract requirements
        agent = ChunkMinerAgent(
            source="mcp",
            default_model="gpt-4o-mini"
        )

        results = agent.mine_files_or_texts_collect(
            valid_files,
            neighbor_refs=neighbor_refs
        )

        # Format results
        requirements = []
        for item in results:
            requirements.append({
                "req_id": item.get("req_id", ""),
                "title": item.get("title", ""),
                "tag": item.get("tag", "functional"),
                "evidence_refs": item.get("evidence_refs", [])
            })

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "count": len(requirements),
                "files_processed": valid_files,
                "requirements": requirements
            }, indent=2)
        )]

    except ImportError as e:
        logger.error(f"Import error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": f"Module import failed: {str(e)}",
                "hint": "Ensure arch_team package is installed"
            }, indent=2)
        )]
    except Exception as e:
        logger.error(f"Mining error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _mine_text(
    text: str,
    source_name: str = "inline_text",
    chunk_size: int = 1000
) -> list[TextContent]:
    """Mine requirements from raw text."""
    try:
        from arch_team.agents.chunk_miner import ChunkMinerAgent

        logger.info(f"Mining text ({len(text)} chars) from source: {source_name}")

        agent = ChunkMinerAgent(
            source="mcp",
            default_model="gpt-4o-mini"
        )

        # Create a text record for processing
        text_records = [{"text": text, "source": source_name}]

        results = agent.mine_files_or_texts_collect(
            text_records,
            neighbor_refs=True
        )

        requirements = []
        for item in results:
            requirements.append({
                "req_id": item.get("req_id", ""),
                "title": item.get("title", ""),
                "tag": item.get("tag", "functional"),
                "evidence_refs": item.get("evidence_refs", [])
            })

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "count": len(requirements),
                "source": source_name,
                "requirements": requirements
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Text mining error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]
