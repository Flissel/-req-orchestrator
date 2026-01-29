"""
MCP Server for Requirements Orchestrator.

This MCP server exposes the high-end functions of the Requirements Engineering System
to Claude CLI for interactive workflow orchestration.

Features:
- Document mining and requirement extraction
- IEEE 29148 validation with 9 quality criteria
- Requirement enhancement and rewriting
- Knowledge graph construction
- Semantic duplicate detection via RAG
- End-to-end workflow orchestration

Usage:
    # Start the MCP server
    python -m mcp_server.server

    # Add to Claude Code
    claude mcp add req-orchestrator -- python -m mcp_server.server
"""

__version__ = "1.0.0"
__author__ = "Requirements Orchestrator Team"

from .config import MCPConfig, config
from .server import create_server, main

__all__ = [
    "MCPConfig",
    "config",
    "create_server",
    "main",
    "__version__"
]
