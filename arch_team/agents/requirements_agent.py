# -*- coding: utf-8 -*-
"""
Requirements Validation Agent using Society of Mind Pattern.

This module provides a multi-agent system for requirements quality assurance:
- RequirementsOperator: Validates and improves requirements (with tools)
- UserClarificationAgent: Gets missing info from user (with ask_user tool)
- QAValidator: Verifies completeness and quality (no tools)

Architecture:
    SocietyOfMindAgent
      └─ RoundRobinGroupChat (inner team)
           ├─ RequirementsOperator (tools: evaluate, rewrite, suggest, detect_duplicates)
           ├─ UserClarificationAgent (tool: ask_user)
           └─ QAValidator (no tools, terminates with "APPROVE")

Reference Implementation: arch_team/dev_folder_/agent.py (GitHub MCP Agent)
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    # AutoGen imports
    from autogen_agentchat.agents import AssistantAgent, SocietyOfMindAgent
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_agentchat.conditions import TextMentionTermination
    from autogen_core.tools import FunctionTool
    from autogen_ext.models.openai import OpenAIChatCompletionClient
except ImportError:
    raise ImportError(
        "AutoGen is required. Install with: pip install 'pyautogen>=0.4.0'"
    )

from ..runtime.logging import get_logger
from ..model.openai_adapter import OpenAIAdapter
from ..tools.validation_tools import (
    evaluate_requirement,
    rewrite_requirement,
    suggest_improvements,
    detect_duplicates,
)

logger = get_logger("agents.requirements_agent")


def _init_model_client(model_name: Optional[str] = None) -> OpenAIChatCompletionClient:
    """
    Initialize OpenAI chat completion client via OpenAIAdapter.

    Args:
        model_name: Optional model override (e.g., "gpt-4o-mini")

    Returns:
        OpenAIChatCompletionClient configured for arch_team
    """
    adapter = OpenAIAdapter()
    model = model_name or adapter.default_model

    # Get API key from environment (same as OpenAIAdapter does)
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    return OpenAIChatCompletionClient(
        model=model,
        api_key=api_key,
        # Additional config from adapter if needed
    )


def _create_ask_user_tool(correlation_id: Optional[str] = None) -> FunctionTool:
    """
    Create the ask_user tool for UserClarificationAgent.

    This tool enables the agent to ask the user clarification questions via GUI.
    Uses file-based polling for user responses (similar to GitHub agent).

    Args:
        correlation_id: Optional correlation ID for multi-session tracking

    Returns:
        FunctionTool that can be used by UserClarificationAgent
    """

    async def ask_user_impl(question: str, suggested_answers: Optional[List[str]] = None) -> str:
        """
        Ask the user a clarification question via GUI/file polling.

        Args:
            question: The question to ask (in German)
            suggested_answers: Optional list of suggested answers

        Returns:
            User's answer as string
        """
        # Generate unique question ID
        question_id = str(uuid.uuid4())

        # Print to console for visibility
        print(f"\n{'='*60}")
        print(f"❓ USER QUESTION (ID: {question_id}):")
        print(f"   {question}")
        if suggested_answers:
            print(f"   Vorschläge: {suggested_answers}")
        print(f"{'='*60}\n")

        # TODO: Broadcast to GUI via EventBus (future enhancement)
        # For now, rely on file-based polling

        try:
            # Determine response file path
            project_root = Path(__file__).resolve().parents[2]  # Navigate to project root
            tmp_dir = project_root / "data" / "tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)

            # Use correlation_id for file name, fallback to question_id
            file_id = correlation_id if correlation_id else question_id
            response_file = tmp_dir / f"clarification_{file_id}.txt"

            # Poll for response file (timeout after 5 minutes)
            max_wait = 300  # 5 minutes
            poll_interval = 1  # 1 second
            elapsed = 0

            logger.info(f"Waiting for user response (polling {response_file})...")
            print(f"⏳ Warte auf Antwort (Datei: {response_file})...")

            while elapsed < max_wait:
                if response_file.exists():
                    # Read and delete the response file
                    try:
                        answer = response_file.read_text(encoding='utf-8').strip()
                        response_file.unlink()  # Delete file after reading

                        logger.info(f"User answered: {answer}")
                        print(f"✅ User antwortete: {answer}")
                        return f"User provided: {answer}"
                    except Exception as e:
                        logger.error(f"Error reading response file: {e}")
                        return "Error: Could not read user response"

                # Wait before next poll
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            # Timeout reached
            logger.warning("Timeout waiting for user response")
            print(f"⏰ Timeout: Keine Antwort vom User")
            return "Error: User did not respond within timeout (5 minutes)"

        except Exception as e:
            logger.error(f"Error in polling mechanism: {e}")
            return f"Error: Polling failed - {e}"

    return FunctionTool(
        ask_user_impl,
        description="Ask the user a clarification question when critical information is missing"
    )


class RequirementsValidationAgent:
    """
    Society of Mind agent for requirements validation and quality assurance.

    This agent orchestrates three specialized agents:
    1. RequirementsOperator: Validates and improves requirements using validation tools
    2. UserClarificationAgent: Gets missing information from the user
    3. QAValidator: Verifies completeness and approves the work

    Usage:
        agent = RequirementsValidationAgent()
        await agent.initialize()
        result = await agent.validate_requirements(
            requirements=["Die App muss schnell sein", ...],
            correlation_id="session-123"
        )
    """

    def __init__(self, model_client: Optional[OpenAIChatCompletionClient] = None):
        """
        Initialize the requirements validation agent.

        Args:
            model_client: Optional OpenAI client override
        """
        self.model_client = model_client or _init_model_client()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the validation agent."""
        if self._initialized:
            return

        logger.info("Initializing RequirementsValidationAgent with Society of Mind")
        self._initialized = True
        print("[RequirementsAgent] Initialized OK")

    async def validate_requirements(
        self,
        requirements: List[str],
        *,
        criteria_keys: Optional[List[str]] = None,
        threshold: float = 0.7,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate requirements and return quality report.

        Args:
            requirements: List of requirement texts to validate
            criteria_keys: Optional quality criteria (default: all)
            threshold: Quality score threshold (default: 0.7)
            correlation_id: Optional session identifier

        Returns:
            {
                "status": "completed",
                "requirements_count": 3,
                "validated": [...],
                "improved": [...],
                "duplicates": [...],
                "message_count": 15,
                "correlation_id": "..."
            }
        """
        if not self._initialized:
            await self.initialize()

        if not requirements:
            return {
                "status": "error",
                "error": "No requirements provided",
                "correlation_id": correlation_id
            }

        # Load prompts
        try:
            from .prompts import requirements_operator_prompt
            from .prompts import qa_validator_prompt
            from .prompts import user_clarification_prompt

            operator_prompt = requirements_operator_prompt.PROMPT
            qa_prompt = qa_validator_prompt.PROMPT
            clarification_prompt = user_clarification_prompt.PROMPT
        except Exception as e:
            logger.error(f"Failed to load prompts: {e}")
            return {"status": "error", "error": f"Prompt loading failed: {e}"}

        # Convert validation functions to FunctionTools for AutoGen
        validation_tools = [
            FunctionTool(evaluate_requirement, description="Evaluate requirement quality"),
            FunctionTool(rewrite_requirement, description="Rewrite requirement to improve it"),
            FunctionTool(suggest_improvements, description="Generate improvement suggestions"),
            FunctionTool(detect_duplicates, description="Find semantic duplicates"),
        ]

        # Create Operator agent WITH validation tools
        operator = AssistantAgent(
            "RequirementsOperator",
            model_client=self.model_client,
            tools=validation_tools,
            system_message=operator_prompt
        )

        # Create ask_user tool for UserClarificationAgent
        ask_user_tool = _create_ask_user_tool(correlation_id=correlation_id)

        # Create Clarification agent WITH ask_user tool
        clarification_agent = AssistantAgent(
            "UserClarificationAgent",
            model_client=self.model_client,
            tools=[ask_user_tool],
            system_message=clarification_prompt
        )

        # Create QA Validator (no tools, validation only)
        qa_validator = AssistantAgent(
            "QAValidator",
            model_client=self.model_client,
            system_message=qa_prompt
        )

        # Inner team termination: wait for "APPROVE" from QA Validator
        termination = TextMentionTermination("APPROVE")
        inner_team = RoundRobinGroupChat(
            [operator, clarification_agent, qa_validator],
            termination_condition=termination,
            max_turns=50  # Allow user interaction
        )

        # Society of Mind wrapper
        som_agent = SocietyOfMindAgent(
            "requirements_society_of_mind",
            team=inner_team,
            model_client=self.model_client
        )

        # Outer team (just the SoM agent)
        team = RoundRobinGroupChat([som_agent], max_turns=1)

        # Build task description
        task_parts = [
            f"Validate the following {len(requirements)} requirement(s):",
            ""
        ]
        for i, req in enumerate(requirements, 1):
            task_parts.append(f"{i}. {req}")

        if criteria_keys:
            task_parts.append(f"\nCriteria: {', '.join(criteria_keys)}")
        task_parts.append(f"\nThreshold: {threshold}")

        task = "\n".join(task_parts)

        # Run validation
        print(f"\n{'='*60}")
        print(f"Society of Mind: Requirements Validation")
        print(f"Requirements: {len(requirements)}")
        print(f"Threshold: {threshold}")
        print(f"{'='*60}\n")

        logger.info(f"Starting validation for {len(requirements)} requirements")

        messages = []
        try:
            async for message in team.run_stream(task=task):
                messages.append(message)

                # Print agent dialogue
                if hasattr(message, 'source') and hasattr(message, 'content'):
                    source = message.source
                    content = str(message.content)

                    if source == "RequirementsOperator":
                        print(f"\n[RequirementsOperator]:")
                        print(f"   {content[:300]}{'...' if len(content) > 300 else ''}")

                    elif source == "UserClarificationAgent":
                        print(f"\n[UserClarificationAgent]:")
                        print(f"   {content[:300]}{'...' if len(content) > 300 else ''}")

                    elif source == "QAValidator":
                        print(f"\n[QAValidator]:")
                        print(f"   {content[:300]}{'...' if len(content) > 300 else ''}")

                    # Check for tool calls
                    if hasattr(message, 'content') and isinstance(message.content, list):
                        for item in message.content:
                            if hasattr(item, 'name'):  # Tool call
                                print(f"   [Tool]: {item.name}")

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "correlation_id": correlation_id
            }

        print(f"\n{'='*60}")
        print(f"[COMPLETED] Validation completed")
        print(f"{'='*60}\n")

        # Extract results from conversation
        result_text = "\n".join([str(m) for m in messages[-5:]])  # Last few messages

        return {
            "status": "completed",
            "requirements_count": len(requirements),
            "message_count": len(messages),
            "correlation_id": correlation_id,
            "result": result_text
        }

    async def shutdown(self) -> None:
        """Shutdown the agent and cleanup."""
        self._initialized = False
        logger.info("RequirementsValidationAgent shutdown")


# Convenience function for quick testing
async def validate_requirements(
    requirements: List[str],
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to validate requirements without managing agent lifecycle.

    Args:
        requirements: List of requirement texts
        **kwargs: Additional arguments passed to validate_requirements()

    Returns:
        Validation result dictionary
    """
    agent = RequirementsValidationAgent()
    await agent.initialize()
    try:
        return await agent.validate_requirements(requirements, **kwargs)
    finally:
        await agent.shutdown()
