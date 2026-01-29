"""
Template Tools for MCP Server.

These tools handle tech stack recommendation and template management.
"""

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

logger = logging.getLogger("mcp_server.template")


def register_template_tools(server: Server) -> None:
    """Register template-related tools with the MCP server."""

    @server.list_tools()
    async def list_template_tools() -> list[Tool]:
        """List available template tools."""
        return [
            Tool(
                name="recommend_techstack",
                description="""Recommend project template based on requirements analysis.

Analyzes requirements to identify the best-fit project template from:
- 01-web-app: Next.js web applications
- 02-api-service: FastAPI backend services
- 03-desktop-electron: Electron desktop apps
- 04-mobile-expo: React Native mobile apps
- 05-static-site: Static site generators
- 06-web3-dapp: Blockchain DApps
- 07-data-ml: Data science / ML projects
- 08-simulation-cpp: C++ simulations
- 09-cli-tool: Command-line tools
- 10-browser-extension: Browser extensions
- 11-chatbot: AI chatbots
- 12-realtime-socketio: WebSocket apps
- 13-operating-system: OS development
- 14-vr-webxr: VR/AR applications
- 15-iot-wokwi: IoT projects

Parameters:
- requirements: List of requirement texts to analyze

Returns: Ranked template recommendations with match scores.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "requirements": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Requirements to analyze"
                        }
                    },
                    "required": ["requirements"]
                }
            ),
            Tool(
                name="get_template_info",
                description="""Get detailed information about a project template.

Returns:
- Template metadata (name, description, stack)
- Required dependencies
- Default project structure
- Available questions for customization

Parameters:
- template_id: Template ID (e.g., "02-api-service")

Returns: Complete template information.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "template_id": {
                            "type": "string",
                            "description": "Template ID"
                        }
                    },
                    "required": ["template_id"]
                }
            ),
            Tool(
                name="list_templates",
                description="""List all available project templates.

Returns: Summary of all 15 templates with descriptions.""",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="get_template_questions",
                description="""Get customization questions for a template.

Returns the questionnaire used to gather project-specific details
for code generation.

Parameters:
- template_id: Template ID

Returns: List of questions organized by category.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "template_id": {
                            "type": "string",
                            "description": "Template ID"
                        }
                    },
                    "required": ["template_id"]
                }
            )
        ]

    @server.call_tool()
    async def call_template_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle template tool calls."""

        if name == "recommend_techstack":
            return await _recommend_techstack(
                requirements=arguments["requirements"]
            )

        elif name == "get_template_info":
            return await _get_template_info(
                template_id=arguments["template_id"]
            )

        elif name == "list_templates":
            return await _list_templates()

        elif name == "get_template_questions":
            return await _get_template_questions(
                template_id=arguments["template_id"]
            )

        return [TextContent(type="text", text=f"Unknown template tool: {name}")]


async def _recommend_techstack(requirements: list[str]) -> list[TextContent]:
    """Recommend tech stack based on requirements."""
    try:
        from arch_team.agents.techstack_agent import TechStackAgent

        logger.info(f"Recommending techstack for {len(requirements)} requirements")

        agent = TechStackAgent()
        recommendations = agent.recommend(requirements)

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "requirements_analyzed": len(requirements),
                "recommendations": recommendations
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Techstack recommendation error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _get_template_info(template_id: str) -> list[TextContent]:
    """Get template information."""
    try:
        from pathlib import Path
        import json as json_module

        logger.info(f"Getting template info: {template_id}")

        # Find template directory
        project_root = Path(__file__).parent.parent.parent
        template_dir = project_root / "templates" / template_id

        if not template_dir.exists():
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Template not found: {template_id}"
                }, indent=2)
            )]

        # Read meta.json
        meta_path = template_dir / "meta.json"
        meta = {}
        if meta_path.exists():
            meta = json_module.loads(meta_path.read_text(encoding="utf-8"))

        # Check for QUESTIONS.md
        questions_path = template_dir / "QUESTIONS.md"
        has_questions = questions_path.exists()

        # Check for CODING_RULES.md
        rules_path = template_dir / "CODING_RULES.md"
        has_rules = rules_path.exists()

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "template_id": template_id,
                "meta": meta,
                "has_questions": has_questions,
                "has_coding_rules": has_rules,
                "path": str(template_dir)
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Get template info error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _list_templates() -> list[TextContent]:
    """List all templates."""
    try:
        from pathlib import Path
        import json as json_module

        logger.info("Listing all templates")

        project_root = Path(__file__).parent.parent.parent
        templates_dir = project_root / "templates"

        templates = []
        for template_dir in sorted(templates_dir.iterdir()):
            if template_dir.is_dir() and template_dir.name[0].isdigit():
                # Read meta.json
                meta_path = template_dir / "meta.json"
                meta = {}
                if meta_path.exists():
                    try:
                        meta = json_module.loads(meta_path.read_text(encoding="utf-8"))
                    except:
                        pass

                templates.append({
                    "id": template_dir.name,
                    "name": meta.get("name", template_dir.name),
                    "description": meta.get("description", ""),
                    "stack": meta.get("stack", [])
                })

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "count": len(templates),
                "templates": templates
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"List templates error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def _get_template_questions(template_id: str) -> list[TextContent]:
    """Get template questions."""
    try:
        from pathlib import Path

        logger.info(f"Getting questions for template: {template_id}")

        project_root = Path(__file__).parent.parent.parent
        questions_path = project_root / "templates" / template_id / "QUESTIONS.md"

        if not questions_path.exists():
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Questions not found for template: {template_id}"
                }, indent=2)
            )]

        content = questions_path.read_text(encoding="utf-8")

        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "template_id": template_id,
                "questions_markdown": content
            }, indent=2)
        )]

    except Exception as e:
        logger.error(f"Get template questions error: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]
