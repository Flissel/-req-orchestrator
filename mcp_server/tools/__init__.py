"""
MCP Tools for Requirements Orchestrator.

This module contains all the tools exposed to Claude via MCP.
Tools are organized by category:

- mining_tools: Document mining and requirement extraction
- validation_tools: IEEE 29148 validation and enhancement
- kg_tools: Knowledge graph construction and querying
- rag_tools: Semantic search and duplicate detection
- workflow_tools: End-to-end orchestration
- template_tools: Tech stack recommendation
"""

from .mining_tools import register_mining_tools
from .validation_tools import register_validation_tools
from .kg_tools import register_kg_tools
from .rag_tools import register_rag_tools
from .workflow_tools import register_workflow_tools
from .template_tools import register_template_tools

__all__ = [
    "register_mining_tools",
    "register_validation_tools",
    "register_kg_tools",
    "register_rag_tools",
    "register_workflow_tools",
    "register_template_tools",
]
