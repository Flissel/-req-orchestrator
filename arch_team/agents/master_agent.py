# -*- coding: utf-8 -*-
"""
Master Society of Mind Agent
Integrates all arch_team agents into a unified workflow.
"""
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from tempfile import mkdtemp

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_ext.models import OpenAIChatCompletionClient

# Import all tools
from arch_team.tools.mining_tools import mining_tools
from arch_team.tools.kg_tools import kg_tools
from arch_team.tools.validation_tools import validation_tools
from arch_team.tools.rag_tools import rag_tools

# Import all prompts
from arch_team.agents.prompts.orchestrator_prompt import PROMPT as orchestrator_prompt
from arch_team.agents.prompts.chunk_miner_prompt import PROMPT as chunk_miner_prompt
from arch_team.agents.prompts.kg_agent_prompt import PROMPT as kg_agent_prompt
from arch_team.agents.prompts.validation_agent_prompt import PROMPT as validation_agent_prompt
from arch_team.agents.prompts.rag_agent_prompt import PROMPT as rag_agent_prompt
from arch_team.agents.prompts.qa_validator_prompt import PROMPT as qa_validator_prompt
from arch_team.agents.prompts.user_clarification_prompt import PROMPT as user_clarification_prompt

logger = logging.getLogger("arch_team.master_agent")


def _send_to_workflow_stream(correlation_id: Optional[str], message_type: str, **kwargs):
    """Send message to workflow stream for frontend display."""
    if not correlation_id:
        return

    try:
        from arch_team.service import workflow_streams
        from datetime import datetime

        queue = workflow_streams.get(correlation_id)
        if queue:
            message = {
                "type": message_type,
                "timestamp": datetime.now().isoformat(),
                **kwargs
            }
            queue.put(message)
            logger.debug(f"[Stream] Sent {message_type}: {kwargs}")
    except Exception as e:
        logger.error(f"Error sending to workflow stream: {e}")


def _create_ask_user_tool(correlation_id: Optional[str] = None):
    """
    Create ask_user tool for UserClarificationAgent with SSE broadcasting.

    Args:
        correlation_id: Session ID for SSE streaming to frontend

    Returns:
        FunctionTool for ask_user
    """
    from autogen_core.tools import FunctionTool
    import time

    # Temporary directory for file-based polling
    tmp_dir = Path(mkdtemp(prefix="arch_team_clarification_"))

    def ask_user_impl(question: str, suggested_answers: Optional[List[str]] = None) -> str:
        """
        Ask user a clarification question and wait for response.

        This tool combines:
        1. SSE broadcasting to frontend (real-time GUI display)
        2. File-based polling for response (backend compatibility)

        Args:
            question: Question to ask user (in German)
            suggested_answers: Optional list of suggested responses

        Returns:
            User's answer as string
        """
        import uuid

        question_id = str(uuid.uuid4())[:8]

        logger.info(f"[ask_user] Question {question_id}: {question}")

        # Broadcast to GUI via SSE (if correlation_id exists, session is active)
        if correlation_id:
            try:
                import sys
                service_module = sys.modules.get('arch_team.service')
                if service_module and hasattr(service_module, 'clarification_streams'):
                    streams = service_module.clarification_streams
                    if correlation_id in streams:
                        streams[correlation_id].put({
                            "type": "question",
                            "question_id": question_id,
                            "question": question,
                            "suggested_answers": suggested_answers or []
                        })
                        logger.info(f"[ask_user] Broadcasted to SSE stream: {correlation_id}")
            except Exception as e:
                logger.warning(f"Failed to broadcast via SSE: {e}")

        # File-based polling for response
        response_file = tmp_dir / f"clarification_{correlation_id}.txt"

        # Wait for user to answer (file appears)
        logger.info(f"[ask_user] Waiting for response file: {response_file}")

        timeout = 300  # 5 minutes
        poll_interval = 1  # 1 second
        elapsed = 0

        while elapsed < timeout:
            if response_file.exists():
                try:
                    answer = response_file.read_text(encoding='utf-8').strip()
                    response_file.unlink()  # Delete file after reading
                    logger.info(f"[ask_user] Received answer: {answer}")
                    return answer
                except Exception as e:
                    logger.error(f"Failed to read response file: {e}")
                    time.sleep(poll_interval)
                    elapsed += poll_interval
            else:
                time.sleep(poll_interval)
                elapsed += poll_interval

        # Timeout - return default
        logger.warning(f"[ask_user] Timeout after {timeout}s, using default answer")
        return "Keine Antwort erhalten (Timeout)"

    return FunctionTool(
        ask_user_impl,
        description="Ask user for clarification when critical information is missing or decisions are needed"
    )


async def create_master_agent(
    *,
    model: str = "gpt-4o-mini",
    correlation_id: Optional[str] = None,
    max_turns: int = 100
) -> AssistantAgent:
    """
    Create master Society of Mind agent with all arch_team agents.

    This creates a coordinated team of 7 specialized agents:
    1. Orchestrator - Workflow coordination
    2. ChunkMiner - Document processing and requirements extraction
    3. KG - Knowledge Graph construction
    4. Validator - Requirements quality evaluation and improvement
    5. RAG - Semantic search, duplicate detection, clustering
    6. QA - Final quality assurance review
    7. UserClarification - Human-in-the-loop questions

    Args:
        model: LLM model to use (default: gpt-4o-mini)
        correlation_id: Session ID for user clarification SSE streaming
        max_turns: Maximum conversation turns (default: 100)

    Returns:
        Master Society of Mind agent ready for orchestration

    Example:
        master = await create_master_agent(correlation_id="session-123")
        result = await master.run(
            task="Extract and validate requirements from uploaded files"
        )
    """
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    # Create model client
    model_client = OpenAIChatCompletionClient(
        model=model,
        api_key=api_key
    )

    logger.info(f"Creating master Society of Mind agent with model: {model}")

    # 1. Create Orchestrator (no tools, pure coordination)
    orchestrator = AssistantAgent(
        name="Orchestrator",
        model_client=model_client,
        system_message=orchestrator_prompt
    )
    logger.info("✓ Created Orchestrator agent")

    # 2. Create ChunkMiner (with mining tools)
    chunk_miner = AssistantAgent(
        name="ChunkMiner",
        model_client=model_client,
        tools=mining_tools,
        system_message=chunk_miner_prompt
    )
    logger.info("✓ Created ChunkMiner agent with mining tools")

    # 3. Create KG Agent (with KG tools)
    kg_agent = AssistantAgent(
        name="KG",
        model_client=model_client,
        tools=kg_tools,
        system_message=kg_agent_prompt
    )
    logger.info("✓ Created KG agent with knowledge graph tools")

    # 4. Create Validator (with validation tools)
    validator = AssistantAgent(
        name="Validator",
        model_client=model_client,
        tools=validation_tools,
        system_message=validation_agent_prompt
    )
    logger.info("✓ Created Validator agent with evaluation tools")

    # 5. Create RAG Agent (with RAG tools)
    rag_agent = AssistantAgent(
        name="RAG",
        model_client=model_client,
        tools=rag_tools,
        system_message=rag_agent_prompt
    )
    logger.info("✓ Created RAG agent with semantic search tools")

    # 6. Create QA Validator (no tools, reviews outputs)
    qa_validator = AssistantAgent(
        name="QA",
        model_client=model_client,
        system_message=qa_validator_prompt
    )
    logger.info("✓ Created QA Validator agent")

    # 7. Create UserClarification Agent (with ask_user tool)
    ask_user_tool = _create_ask_user_tool(correlation_id)
    user_clarification = AssistantAgent(
        name="UserClarification",
        model_client=model_client,
        tools=[ask_user_tool],
        system_message=user_clarification_prompt
    )
    logger.info("✓ Created UserClarification agent with ask_user tool")

    # Create inner team with all agents
    termination = TextMentionTermination("WORKFLOW_COMPLETE")
    inner_team = RoundRobinGroupChat(
        participants=[
            orchestrator,
            chunk_miner,
            kg_agent,
            validator,
            rag_agent,
            qa_validator,
            user_clarification
        ],
        termination_condition=termination,
        max_turns=max_turns
    )
    logger.info(f"✓ Created RoundRobinGroupChat with {len(inner_team._participants)} agents, max_turns={max_turns}")

    # Wrap in Society of Mind (single-agent interface)
    from autogen_agentchat.agents import SocietyOfMindAgent

    master_agent = SocietyOfMindAgent(
        name="arch_team_master",
        team=inner_team,
        model_client=model_client
    )
    logger.info("✓ Created master Society of Mind agent")

    return master_agent


async def run_master_workflow(
    files: List[str],
    *,
    correlation_id: Optional[str] = None,
    model: str = "gpt-4o-mini",
    chunk_size: int = 800,
    chunk_overlap: int = 200,
    use_llm_kg: bool = True,
    validation_threshold: float = 0.7
) -> Dict[str, Any]:
    """
    Run complete arch_team workflow using master Society of Mind agent.

    This is a high-level convenience function that:
    1. Creates master agent
    2. Constructs task description
    3. Runs workflow
    4. Returns structured results

    Args:
        files: List of file paths to process
        correlation_id: Session ID for user clarification
        model: LLM model (default: gpt-4o-mini)
        chunk_size: Document chunk size in tokens (default: 800)
        chunk_overlap: Chunk overlap in tokens (default: 200)
        use_llm_kg: Use LLM for KG entity extraction (default: True)
        validation_threshold: Quality threshold for validation (default: 0.7)

    Returns:
        {
            "success": bool,
            "workflow_status": "completed|failed",
            "requirements": [...],
            "knowledge_graph": {...},
            "validation_results": {...},
            "rag_analysis": {...},
            "qa_report": {...},
            "user_clarifications": [...]
        }

    Example:
        result = await run_master_workflow(
            files=["requirements.md"],
            correlation_id="session-123",
            chunk_size=800
        )
        print(f"Extracted {len(result['requirements'])} requirements")
    """
    logger.info(f"Starting master workflow for {len(files)} file(s)")

    # Create master agent
    master = await create_master_agent(
        model=model,
        correlation_id=correlation_id
    )

    # Construct task description
    task = f"""Process {len(files)} document(s) through the complete arch_team workflow:

Files to process: {', '.join(files)}

Parameters:
- Chunk size: {chunk_size} tokens
- Chunk overlap: {chunk_overlap} tokens
- Use LLM for KG: {use_llm_kg}
- Validation threshold: {validation_threshold}

Workflow Phases:
1. Extract requirements from documents (ChunkMiner)
2. Build Knowledge Graph (KG Agent)
3. Validate and improve requirements (Validator)
4. Analyze duplicates and semantics (RAG Agent)
5. Final quality review (QA Validator)
6. User clarification if needed (UserClarification)

Execute all phases and signal WORKFLOW_COMPLETE when done.
"""

    logger.info(f"Task description:\n{task}")

    # Run workflow with streaming
    try:
        from autogen_agentchat.messages import TextMessage

        # Send workflow start status
        _send_to_workflow_stream(
            correlation_id,
            "workflow_status",
            status="running"
        )

        # Use run_stream to get messages in real-time
        result = None
        async for message in master.run_stream(task=task):
            # Stream each agent message to frontend
            if hasattr(message, 'source') and hasattr(message, 'content'):
                _send_to_workflow_stream(
                    correlation_id,
                    "agent_message",
                    agent=message.source,
                    message=str(message.content)
                )

            # Keep last message as result
            result = message

        logger.info("Workflow completed successfully")

        # Send completion status
        _send_to_workflow_stream(
            correlation_id,
            "workflow_status",
            status="completed"
        )

        # Send final result
        _send_to_workflow_stream(
            correlation_id,
            "workflow_result",
            result={
                "success": True,
                "workflow_status": "completed",
                "final_message": str(result) if result else "Workflow completed"
            }
        )

        return {
            "success": True,
            "workflow_status": "completed",
            "result": result
        }

    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)

        # Send failure status
        _send_to_workflow_stream(
            correlation_id,
            "workflow_status",
            status="failed",
            error=str(e)
        )

        return {
            "success": False,
            "workflow_status": "failed",
            "error": str(e)
        }


__all__ = ["create_master_agent", "run_master_workflow"]
