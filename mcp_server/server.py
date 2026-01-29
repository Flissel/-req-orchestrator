"""
MCP Server for Requirements Orchestrator.

This is the main entry point for the MCP server that exposes
all requirement engineering tools to Claude.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
    Prompt,
    PromptMessage,
    GetPromptResult,
    PromptArgument,
)

from .config import config, MCPConfig

# Import tools
from .tools.mining_tools import register_mining_tools
from .tools.validation_tools import register_validation_tools
from .tools.kg_tools import register_kg_tools
from .tools.rag_tools import register_rag_tools
from .tools.workflow_tools import register_workflow_tools
from .tools.template_tools import register_template_tools

# Import resources
from .resources.requirements import register_requirement_resources

# Import prompts
from .prompts.workflow_prompts import register_workflow_prompts

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_server")


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server(config.server_name)

    # Register all tools
    logger.info("Registering MCP tools...")
    register_mining_tools(server)
    register_validation_tools(server)
    register_kg_tools(server)
    register_rag_tools(server)
    register_workflow_tools(server)
    register_template_tools(server)

    # Register resources
    logger.info("Registering MCP resources...")
    register_requirement_resources(server)

    # Register prompts
    logger.info("Registering MCP prompts...")
    register_workflow_prompts(server)

    logger.info(f"MCP Server '{config.server_name}' v{config.server_version} initialized")

    return server


async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting MCP Server for Requirements Orchestrator...")
    logger.info(f"Backend URL: {config.backend_url}")
    logger.info(f"Arch Team URL: {config.arch_team_url}")
    logger.info(f"Qdrant: {config.qdrant_url}:{config.qdrant_port}")

    server = create_server()

    # Run with stdio transport (for Claude Code integration)
    async with stdio_server() as (read_stream, write_stream):
        logger.info("MCP Server running on stdio...")
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
