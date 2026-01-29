"""
MCP Server Resources.

Resources expose data to Claude for context.
"""

from .requirements import register_requirement_resources

__all__ = ["register_requirement_resources"]
