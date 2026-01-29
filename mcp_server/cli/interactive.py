"""
Interactive CLI for MCP Server.

Provides a command-line interface for testing and debugging MCP tools.
"""

import asyncio
import json
import sys
from pathlib import Path


def print_header():
    """Print the CLI header."""
    print("\n" + "=" * 60)
    print("  Requirements Orchestrator - MCP Server CLI")
    print("=" * 60)
    print("\nAvailable commands:")
    print("  tools          - List all available tools")
    print("  resources      - List all available resources")
    print("  prompts        - List all available prompts")
    print("  call <tool>    - Call a tool interactively")
    print("  read <uri>     - Read a resource")
    print("  prompt <name>  - Get a prompt")
    print("  status         - Show system status")
    print("  help           - Show this help")
    print("  quit           - Exit")
    print()


async def list_tools():
    """List all available tools."""
    from ..server import create_server

    server = create_server()

    print("\n Available Tools:")
    print("-" * 50)

    # Mining tools
    print("\n Mining:")
    print("  - mine_documents: Extract requirements from files")
    print("  - mine_text: Extract requirements from raw text")

    # Validation tools
    print("\n Validation:")
    print("  - validate_requirements: Batch validation against IEEE 29148")
    print("  - enhance_requirement: Improve a single requirement")
    print("  - evaluate_single: Detailed single requirement evaluation")

    # KG tools
    print("\n Knowledge Graph:")
    print("  - build_knowledge_graph: Build KG from requirements")
    print("  - search_kg_nodes: Semantic node search")
    print("  - get_kg_neighbors: 1-hop neighborhood query")
    print("  - export_knowledge_graph: Export all nodes/edges")

    # RAG tools
    print("\n RAG & Semantic Search:")
    print("  - find_duplicates: Detect semantic duplicates")
    print("  - search_requirements: Semantic search")
    print("  - find_related: Find related requirements")
    print("  - analyze_coverage: Gap analysis")

    # Workflow tools
    print("\n Workflow Orchestration:")
    print("  - run_full_workflow: Complete pipeline")
    print("  - get_clarification_questions: Generate questions")
    print("  - apply_answers: Apply answers and re-validate")
    print("  - get_project_status: Get workflow statistics")
    print("  - export_requirements: Export to various formats")

    # Template tools
    print("\n Templates:")
    print("  - recommend_techstack: Recommend project template")
    print("  - get_template_info: Get template details")
    print("  - list_templates: List all templates")
    print("  - get_template_questions: Get template questions")

    print()


async def list_resources():
    """List all available resources."""
    print("\n Available Resources:")
    print("-" * 50)
    print("  - requirements://current  - Current requirements with status")
    print("  - projects://list        - All projects")
    print("  - templates://all        - All 15 templates")
    print("  - criteria://ieee29148   - IEEE 29148 criteria definitions")
    print("  - config://runtime       - Runtime configuration")
    print()


async def list_prompts():
    """List all available prompts."""
    print("\n Available Prompts:")
    print("-" * 50)
    print("  - quick-validation        - Fast requirement validation")
    print("  - deep-analysis          - Complete analysis pipeline")
    print("  - interactive-enhancement - Guided requirement improvement")
    print("  - techstack-recommendation - Template recommendation")
    print("  - duplicate-detection     - Find semantic duplicates")
    print("  - coverage-analysis       - Coverage gap analysis")
    print()


async def call_tool(tool_name: str):
    """Interactively call a tool."""
    print(f"\n Calling tool: {tool_name}")
    print("-" * 50)

    # Tool argument definitions
    tool_args = {
        "mine_documents": [
            ("files", "File paths (comma-separated)", "string[]"),
            ("chunk_size", "Chunk size in tokens (default: 1000)", "int"),
            ("neighbor_refs", "Include neighbor context (default: true)", "bool")
        ],
        "mine_text": [
            ("text", "Raw text to mine", "string"),
            ("source_name", "Source identifier", "string")
        ],
        "validate_requirements": [
            ("requirements", "Requirement texts (one per line)", "string[]"),
            ("mode", "quick or guided (default: quick)", "string")
        ],
        "enhance_requirement": [
            ("requirement", "Requirement text", "string"),
            ("failing_criteria", "Failing criteria (comma-separated)", "string[]")
        ],
        "evaluate_single": [
            ("requirement", "Requirement text", "string")
        ],
        "build_knowledge_graph": [
            ("requirements", "Requirement DTOs as JSON", "json"),
            ("use_llm", "Use LLM extraction (default: false)", "bool"),
            ("persist", "Persist to Qdrant (default: true)", "bool")
        ],
        "find_duplicates": [
            ("requirements", "Requirement texts (one per line)", "string[]"),
            ("threshold", "Similarity threshold 0-1 (default: 0.85)", "float")
        ],
        "search_requirements": [
            ("query", "Search query", "string"),
            ("top_k", "Number of results (default: 10)", "int")
        ],
        "run_full_workflow": [
            ("files", "File paths (comma-separated)", "string[]"),
            ("mode", "quick or guided (default: quick)", "string")
        ],
        "recommend_techstack": [
            ("requirements", "Requirement texts (one per line)", "string[]")
        ],
        "list_templates": [],
        "get_template_info": [
            ("template_id", "Template ID (e.g., 02-api-service)", "string")
        ],
        "get_template_questions": [
            ("template_id", "Template ID", "string")
        ],
        "get_project_status": [
            ("project_id", "Project ID (optional)", "string")
        ],
        "export_requirements": [
            ("format", "markdown, json, or csv (default: markdown)", "string"),
            ("include_scores", "Include validation scores (default: true)", "bool"),
            ("filter_passed", "Only passed requirements (default: false)", "bool")
        ]
    }

    if tool_name not in tool_args:
        print(f"  Unknown tool: {tool_name}")
        print(f"  Use 'tools' command to see available tools.")
        return

    args = tool_args[tool_name]
    arguments = {}

    if args:
        print("\n  Enter arguments (press Enter for defaults):\n")
        for arg_name, description, arg_type in args:
            value = input(f"  {arg_name} ({description}): ").strip()

            if value:
                if arg_type == "int":
                    arguments[arg_name] = int(value)
                elif arg_type == "float":
                    arguments[arg_name] = float(value)
                elif arg_type == "bool":
                    arguments[arg_name] = value.lower() in ("true", "1", "yes")
                elif arg_type == "string[]":
                    if "\n" in value:
                        arguments[arg_name] = value.split("\n")
                    else:
                        arguments[arg_name] = value.split(",")
                elif arg_type == "json":
                    arguments[arg_name] = json.loads(value)
                else:
                    arguments[arg_name] = value

    print(f"\n  Calling {tool_name} with: {json.dumps(arguments, indent=2)}")
    print("\n  (Tool execution requires running MCP server)")
    print("  Use: claude mcp add req-orchestrator -- python -m mcp_server.server")
    print()


async def read_resource(uri: str):
    """Read a resource."""
    from ..resources.requirements import (
        _get_current_requirements,
        _get_projects_list,
        _get_all_templates,
        _get_ieee_criteria,
        _get_runtime_config
    )

    print(f"\n Reading resource: {uri}")
    print("-" * 50)

    try:
        if uri == "requirements://current":
            result = await _get_current_requirements()
        elif uri == "projects://list":
            result = await _get_projects_list()
        elif uri == "templates://all":
            result = await _get_all_templates()
        elif uri == "criteria://ieee29148":
            result = _get_ieee_criteria()
        elif uri == "config://runtime":
            result = await _get_runtime_config()
        else:
            result = json.dumps({"error": f"Unknown resource: {uri}"})

        print(result)

    except Exception as e:
        print(f"  Error: {e}")

    print()


async def get_prompt(name: str):
    """Get a prompt."""
    from ..prompts.workflow_prompts import (
        _get_quick_validation_prompt,
        _get_deep_analysis_prompt,
        _get_interactive_enhancement_prompt,
        _get_techstack_prompt,
        _get_duplicate_detection_prompt,
        _get_coverage_analysis_prompt
    )

    print(f"\n Prompt: {name}")
    print("-" * 50)

    prompt_funcs = {
        "quick-validation": _get_quick_validation_prompt,
        "deep-analysis": _get_deep_analysis_prompt,
        "interactive-enhancement": _get_interactive_enhancement_prompt,
        "techstack-recommendation": _get_techstack_prompt,
        "duplicate-detection": _get_duplicate_detection_prompt,
        "coverage-analysis": _get_coverage_analysis_prompt
    }

    if name not in prompt_funcs:
        print(f"  Unknown prompt: {name}")
        return

    # Get sample arguments
    arguments = {}
    if name == "quick-validation":
        arguments["requirements"] = "The system shall...\nThe user shall..."
    elif name == "deep-analysis":
        arguments["files"] = "docs/requirements.md"
        arguments["mode"] = "quick"
    elif name == "interactive-enhancement":
        arguments["requirement"] = "The system shall be fast"
        arguments["failing_criteria"] = "measurability,testability"
    elif name == "techstack-recommendation":
        arguments["requirements"] = "Web application with user auth..."
    elif name == "duplicate-detection":
        arguments["requirements"] = "Req 1\nReq 2\nReq 3"
        arguments["threshold"] = "0.85"
    elif name == "coverage-analysis":
        arguments["requirements"] = "Req 1\nReq 2"
        arguments["categories"] = "functional,security,performance"

    messages = prompt_funcs[name](arguments)
    for msg in messages:
        print(f"\n  [{msg.role}]:")
        print(f"  {msg.content.text[:500]}...")

    print()


async def show_status():
    """Show system status."""
    import httpx
    from ..config import config

    print("\n System Status:")
    print("-" * 50)

    print(f"\n  MCP Server: {config.server_name} v{config.server_version}")

    # Check backend
    print(f"\n  Backend ({config.backend_url}):")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{config.backend_url}/health", timeout=5)
            if response.status_code == 200:
                print("    Status: HEALTHY")
            else:
                print(f"    Status: UNHEALTHY ({response.status_code})")
    except Exception as e:
        print(f"    Status: UNREACHABLE ({e})")

    # Check arch_team
    print(f"\n  Arch Team ({config.arch_team_url}):")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{config.arch_team_url}/health", timeout=5)
            if response.status_code == 200:
                print("    Status: HEALTHY")
            else:
                print(f"    Status: UNHEALTHY ({response.status_code})")
    except Exception as e:
        print(f"    Status: UNREACHABLE ({e})")

    print()


def run_interactive():
    """Run the interactive CLI."""
    print_header()

    while True:
        try:
            cmd = input("mcp> ").strip().lower()

            if not cmd:
                continue

            parts = cmd.split(maxsplit=1)
            command = parts[0]
            arg = parts[1] if len(parts) > 1 else ""

            if command in ("quit", "exit", "q"):
                print("\nGoodbye!")
                break

            elif command == "help":
                print_header()

            elif command == "tools":
                asyncio.run(list_tools())

            elif command == "resources":
                asyncio.run(list_resources())

            elif command == "prompts":
                asyncio.run(list_prompts())

            elif command == "call":
                if arg:
                    asyncio.run(call_tool(arg))
                else:
                    print("Usage: call <tool_name>")

            elif command == "read":
                if arg:
                    asyncio.run(read_resource(arg))
                else:
                    print("Usage: read <resource_uri>")

            elif command == "prompt":
                if arg:
                    asyncio.run(get_prompt(arg))
                else:
                    print("Usage: prompt <prompt_name>")

            elif command == "status":
                asyncio.run(show_status())

            else:
                print(f"Unknown command: {command}")
                print("Type 'help' for available commands.")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except EOFError:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    run_interactive()
