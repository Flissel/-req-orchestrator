"""
Workflow Prompts for MCP Server.

Pre-built prompts for common requirements engineering workflows.
"""

import logging

from mcp.server import Server
from mcp.types import Prompt, PromptMessage, TextContent, PromptArgument

logger = logging.getLogger("mcp_server.prompts")


def register_workflow_prompts(server: Server) -> None:
    """Register workflow prompts with the MCP server."""

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        """List available workflow prompts."""
        return [
            Prompt(
                name="quick-validation",
                description="Quickly validate requirements and get a summary",
                arguments=[
                    PromptArgument(
                        name="requirements",
                        description="Requirements to validate (newline-separated or file path)",
                        required=True
                    )
                ]
            ),
            Prompt(
                name="deep-analysis",
                description="Complete pipeline: Mining -> Validation -> KG -> Duplicates -> Report",
                arguments=[
                    PromptArgument(
                        name="files",
                        description="File paths to analyze (comma-separated)",
                        required=True
                    ),
                    PromptArgument(
                        name="mode",
                        description="Processing mode: 'quick' or 'guided'",
                        required=False
                    )
                ]
            ),
            Prompt(
                name="interactive-enhancement",
                description="Interactively improve failing requirements with clarification questions",
                arguments=[
                    PromptArgument(
                        name="requirement",
                        description="The requirement to improve",
                        required=True
                    ),
                    PromptArgument(
                        name="failing_criteria",
                        description="Criteria that failed (comma-separated)",
                        required=False
                    )
                ]
            ),
            Prompt(
                name="techstack-recommendation",
                description="Get project template recommendations based on requirements",
                arguments=[
                    PromptArgument(
                        name="requirements",
                        description="Requirements to analyze (newline-separated)",
                        required=True
                    )
                ]
            ),
            Prompt(
                name="duplicate-detection",
                description="Find semantic duplicates in a requirement set",
                arguments=[
                    PromptArgument(
                        name="requirements",
                        description="Requirements to check (newline-separated)",
                        required=True
                    ),
                    PromptArgument(
                        name="threshold",
                        description="Similarity threshold (0-1, default: 0.85)",
                        required=False
                    )
                ]
            ),
            Prompt(
                name="coverage-analysis",
                description="Analyze requirement coverage across categories",
                arguments=[
                    PromptArgument(
                        name="requirements",
                        description="Requirements to analyze (newline-separated)",
                        required=True
                    ),
                    PromptArgument(
                        name="categories",
                        description="Expected categories (comma-separated)",
                        required=False
                    )
                ]
            )
        ]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict[str, str] | None = None) -> list[PromptMessage]:
        """Get a specific prompt with arguments filled in."""

        arguments = arguments or {}

        if name == "quick-validation":
            return _get_quick_validation_prompt(arguments)

        elif name == "deep-analysis":
            return _get_deep_analysis_prompt(arguments)

        elif name == "interactive-enhancement":
            return _get_interactive_enhancement_prompt(arguments)

        elif name == "techstack-recommendation":
            return _get_techstack_prompt(arguments)

        elif name == "duplicate-detection":
            return _get_duplicate_detection_prompt(arguments)

        elif name == "coverage-analysis":
            return _get_coverage_analysis_prompt(arguments)

        return [PromptMessage(
            role="user",
            content=TextContent(type="text", text=f"Unknown prompt: {name}")
        )]


def _get_quick_validation_prompt(arguments: dict[str, str]) -> list[PromptMessage]:
    """Generate quick validation prompt."""
    requirements = arguments.get("requirements", "")

    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"""Validate the following requirements against IEEE 29148 quality criteria.

For each requirement, check these 9 criteria:
1. Atomic - One requirement per statement
2. Clarity - Clear, precise language
3. Testability - Can be verified
4. Measurability - Quantifiable metrics
5. Concise - No unnecessary words
6. Unambiguous - Single interpretation
7. Consistent Language - Consistent terminology
8. Design Independent - WHAT not HOW
9. Purpose Independent - No business justification mixed in

Requirements to validate:
{requirements}

Use the `validate_requirements` tool to evaluate these requirements.
Then provide a summary with:
- Total count and pass rate
- List of passing requirements (briefly)
- List of failing requirements with their failing criteria
- Top 3 improvement suggestions"""
            )
        )
    ]


def _get_deep_analysis_prompt(arguments: dict[str, str]) -> list[PromptMessage]:
    """Generate deep analysis prompt."""
    files = arguments.get("files", "")
    mode = arguments.get("mode", "quick")

    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"""Perform a complete requirements engineering analysis on these files:
{files}

Mode: {mode}

Execute the following pipeline:

1. **Mining Phase**
   Use `mine_documents` to extract requirements from the files.
   Report: How many requirements found? What categories?

2. **Knowledge Graph Phase**
   Use `build_knowledge_graph` to create semantic relationships.
   Report: Node/edge counts, key actors and entities discovered.

3. **Validation Phase**
   Use `validate_requirements` to check IEEE 29148 compliance.
   Report: Pass rate, common failing criteria.

4. **Duplicate Detection**
   Use `find_duplicates` to identify semantic duplicates.
   Report: Any duplicate groups found?

5. **Coverage Analysis**
   Use `analyze_coverage` to check category coverage.
   Report: Gaps identified, suggested additions.

6. **Final Report**
   Provide a comprehensive summary with:
   - Executive summary (2-3 sentences)
   - Requirements statistics
   - Quality assessment
   - Top 5 action items for improvement"""
            )
        )
    ]


def _get_interactive_enhancement_prompt(arguments: dict[str, str]) -> list[PromptMessage]:
    """Generate interactive enhancement prompt."""
    requirement = arguments.get("requirement", "")
    failing_criteria = arguments.get("failing_criteria", "")

    criteria_text = ""
    if failing_criteria:
        criteria_text = f"\nKnown failing criteria: {failing_criteria}"

    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"""Help me improve this requirement interactively:

Requirement:
"{requirement}"
{criteria_text}

Steps:
1. First, use `evaluate_single` to get detailed scores for all criteria.
2. Identify the weakest criteria (score < 0.7).
3. For each failing criterion, ask me ONE clarifying question to gather missing information.
4. After I answer, use `enhance_requirement` to improve it.
5. Re-evaluate to confirm improvement.
6. Repeat until all criteria pass (score >= 0.7).

Start by evaluating the current requirement."""
            )
        )
    ]


def _get_techstack_prompt(arguments: dict[str, str]) -> list[PromptMessage]:
    """Generate techstack recommendation prompt."""
    requirements = arguments.get("requirements", "")

    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"""Analyze these requirements and recommend the best project template:

Requirements:
{requirements}

Steps:
1. Use `recommend_techstack` to get template recommendations.
2. For the top recommendation, use `get_template_info` to get details.
3. Use `get_template_questions` to show customization options.

Provide:
- Top 3 template recommendations with match scores
- Detailed breakdown of why the #1 choice fits
- Key questions to customize the template for this project"""
            )
        )
    ]


def _get_duplicate_detection_prompt(arguments: dict[str, str]) -> list[PromptMessage]:
    """Generate duplicate detection prompt."""
    requirements = arguments.get("requirements", "")
    threshold = arguments.get("threshold", "0.85")

    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"""Find semantic duplicates in these requirements:

Requirements:
{requirements}

Similarity threshold: {threshold}

Use `find_duplicates` with the specified threshold.

Report:
- Total requirements analyzed
- Number of duplicate groups found
- For each group:
  - The requirements that are similar
  - Similarity score
  - Suggested merged version (if duplicates should be combined)
- Recommendation on which duplicates to remove or merge"""
            )
        )
    ]


def _get_coverage_analysis_prompt(arguments: dict[str, str]) -> list[PromptMessage]:
    """Generate coverage analysis prompt."""
    requirements = arguments.get("requirements", "")
    categories = arguments.get("categories", "functional,security,performance,usability,reliability,maintainability")

    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"""Analyze the coverage of these requirements across categories:

Requirements:
{requirements}

Expected categories: {categories}

Use `analyze_coverage` to identify gaps.

Report:
- Coverage percentage per category
- Well-covered areas (with examples)
- Gap areas (missing or weak coverage)
- Suggested new requirements to fill gaps
- Priority order for addressing gaps"""
            )
        )
    ]
