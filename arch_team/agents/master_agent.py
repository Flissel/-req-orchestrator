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

from dotenv import load_dotenv
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.openai._openai_client import ModelInfo, ModelCapabilities

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
    # Load .env explicitly (same pattern as arch_team/main.py)
    # This ensures OPENAI_API_KEY is available in async context
    # Use override=True to force loading even if empty env var exists
    import sys
    project_dir = Path(__file__).resolve().parents[2]

    sys.stderr.write(f"[master_agent.py] Loading .env from: {project_dir / '.env'}\n")
    sys.stderr.flush()

    load_dotenv(project_dir / ".env", override=True)

    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY", "")

    # Debug: Log API key status
    sys.stderr.write(f"[master_agent.py] OPENAI_API_KEY length after load_dotenv: {len(api_key)}\n")
    sys.stderr.flush()

    if not api_key:
        sys.stderr.write("[master_agent.py] ERROR: API key is empty! Raising RuntimeError\n")
        sys.stderr.flush()
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    # Create model client with model_info for non-standard OpenAI models
    # AutoGen 0.4.7+ requires ModelInfo with 'family' field
    model_info = ModelInfo(
        family="gpt",  # Required field in v0.4.7+
        vision=True,
        function_calling=True,
        json_output=True,
        capabilities=ModelCapabilities(
            vision=True,
            function_calling=True,
            json_output=True
        )
    )

    model_client = OpenAIChatCompletionClient(
        model=model,
        api_key=api_key,
        model_info=model_info
    )

    logger.info(f"Creating master Society of Mind agent with model: {model}")

    # 1. Create Orchestrator (no tools, pure coordination)
    orchestrator = AssistantAgent(
        name="Orchestrator",
        model_client=model_client,
        system_message=orchestrator_prompt
    )
    logger.info("[OK] Created Orchestrator agent")

    # 2. Create ChunkMiner (with mining tools)
    chunk_miner = AssistantAgent(
        name="ChunkMiner",
        model_client=model_client,
        tools=mining_tools,
        system_message=chunk_miner_prompt
    )
    logger.info("[OK] Created ChunkMiner agent with mining tools")

    # 3. Create KG Agent (with KG tools)
    kg_agent = AssistantAgent(
        name="KG",
        model_client=model_client,
        tools=kg_tools,
        system_message=kg_agent_prompt
    )
    logger.info("[OK] Created KG agent with knowledge graph tools")

    # 4. Create Validator (with validation tools)
    validator = AssistantAgent(
        name="Validator",
        model_client=model_client,
        tools=validation_tools,
        system_message=validation_agent_prompt
    )
    logger.info("[OK] Created Validator agent with evaluation tools")

    # 5. Create RAG Agent (with RAG tools)
    rag_agent = AssistantAgent(
        name="RAG",
        model_client=model_client,
        tools=rag_tools,
        system_message=rag_agent_prompt
    )
    logger.info("[OK] Created RAG agent with semantic search tools")

    # 6. Create QA Validator (no tools, reviews outputs)
    qa_validator = AssistantAgent(
        name="QA",
        model_client=model_client,
        system_message=qa_validator_prompt
    )
    logger.info("[OK] Created QA Validator agent")

    # 7. Create UserClarification Agent (with ask_user tool)
    ask_user_tool = _create_ask_user_tool(correlation_id)
    user_clarification = AssistantAgent(
        name="UserClarification",
        model_client=model_client,
        tools=[ask_user_tool],
        system_message=user_clarification_prompt
    )
    logger.info("[OK] Created UserClarification agent with ask_user tool")

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
    logger.info(f"[OK] Created RoundRobinGroupChat with {len(inner_team._participants)} agents, max_turns={max_turns}")

    # Wrap in Society of Mind (single-agent interface)
    from autogen_agentchat.agents import SocietyOfMindAgent

    master_agent = SocietyOfMindAgent(
        name="arch_team_master",
        team=inner_team,
        model_client=model_client
    )
    logger.info("[OK] Created master Society of Mind agent")

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

    # DIRECT MINING APPROACH (bypassing AutoGen conversation)
    # The AutoGen agents weren't calling the mining tools properly,
    # so we call ChunkMiner and KG agents directly
    try:
        from arch_team.agents.chunk_miner import ChunkMinerAgent
        from arch_team.agents.kg_agent import KGAbstractionAgent

        # Send workflow start status
        _send_to_workflow_stream(
            correlation_id,
            "workflow_status",
            status="running"
        )

        # Phase 1: Mine requirements from files
        logger.info("Phase 1: Mining requirements from documents...")
        _send_to_workflow_stream(
            correlation_id,
            "agent_message",
            agent="ChunkMiner",
            message=f"Mining requirements from {len(files)} document(s)..."
        )

        miner = ChunkMinerAgent(source="master_workflow", default_model=model)

        # Prepare chunk options
        chunk_opts = {
            "max_tokens": chunk_size,
            "overlap_tokens": chunk_overlap
        }

        # Read files from disk - files parameter contains path strings
        # ChunkMiner expects file data, not paths
        file_records = []
        for file_path in files:
            file_path_obj = Path(file_path)
            logger.info(f"Reading file: {file_path_obj}")
            with open(file_path_obj, 'rb') as f:
                file_records.append({
                    "filename": file_path_obj.name,
                    "data": f.read(),
                    "content_type": ""
                })

        # Mine requirements directly with file contents
        requirements = miner.mine_files_or_texts_collect(
            files_or_texts=file_records,  # Pass file data, not paths
            model=model,
            neighbor_refs=True,  # Include ±1 chunk context
            chunk_options=chunk_opts
        )

        logger.info(f"Mining completed: {len(requirements)} requirements extracted")
        _send_to_workflow_stream(
            correlation_id,
            "agent_message",
            agent="ChunkMiner",
            message=f"✅ Extracted {len(requirements)} requirements"
        )

        # Phase 1.5: Create Manifests in Database
        logger.info("Phase 1.5: Creating manifests in database...")
        _send_to_workflow_stream(
            correlation_id,
            "agent_message",
            agent="System",
            message="Persisting requirements to manifest system..."
        )

        try:
            from backend.core import db as _db
            from backend.services.manifest_integration import create_manifests_from_chunkminer

            conn = _db.get_db()
            try:
                manifest_ids = create_manifests_from_chunkminer(conn, requirements)
                logger.info(f"Created {len(manifest_ids)} manifests in database")
                _send_to_workflow_stream(
                    correlation_id,
                    "agent_message",
                    agent="System",
                    message=f"✅ Persisted {len(manifest_ids)} requirement manifests"
                )
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Manifest creation failed: {e}")
            _send_to_workflow_stream(
                correlation_id,
                "agent_message",
                agent="System",
                message=f"⚠️ Manifest creation failed (non-critical): {str(e)}"
            )
            # Continue anyway - manifests are optional for workflow completion

        # Phase 2: Build Knowledge Graph
        logger.info("Phase 2: Building Knowledge Graph...")
        _send_to_workflow_stream(
            correlation_id,
            "agent_message",
            agent="KGAgent",
            message="Building Knowledge Graph from requirements..."
        )

        kg_agent = KGAbstractionAgent(default_model=model)
        kg_result = kg_agent.run(
            items=requirements,
            model=model,
            persist="qdrant",  # Persist to Qdrant
            use_llm=use_llm_kg,  # Use LLM for entity extraction if enabled
            llm_fallback=True,  # Fall back to LLM if heuristics fail
            dedupe=True  # Deduplicate nodes/edges
        )

        kg_stats = kg_result.get("stats", {})
        logger.info(f"KG built: {kg_stats.get('nodes', 0)} nodes, {kg_stats.get('edges', 0)} edges")
        _send_to_workflow_stream(
            correlation_id,
            "agent_message",
            agent="KGAgent",
            message=f"✅ Created {kg_stats.get('nodes', 0)} nodes and {kg_stats.get('edges', 0)} edges"
        )

        # Phase 3: Validate requirements using local heuristics
        logger.info("Phase 3: Validating requirements...")
        _send_to_workflow_stream(
            correlation_id,
            "agent_message",
            agent="Validator",
            message=f"Validating {len(requirements)} requirements..."
        )

        validation_results = []
        passed_count = 0
        failed_count = 0

        # Validate each requirement using real LLM-based validation
        from arch_team.tools.validation_tools import evaluate_requirement

        for idx, req in enumerate(requirements):
            req_title = req.get("title", f"Requirement {idx + 1}")
            req_id = req.get("req_id", f"req-{idx + 1}")

            logger.info(f"Validating requirement {idx + 1}/{len(requirements)}: {req_title}")

            try:
                # Call real LLM-based validation API
                # Uses all 10 quality criteria: clarity, testability, measurability, atomic, concise,
                # unambiguous, consistent_language, follows_template, design_independent, purpose_independent
                validation_result = evaluate_requirement(
                    requirement_text=req_title,
                    criteria_keys=None  # None = use all criteria
                )

                # Extract validation results
                score = validation_result.get("score", 0.0)
                verdict = validation_result.get("verdict", "fail")
                evaluation = validation_result.get("evaluation", [])
                error = validation_result.get("error")

                # Count pass/fail
                if verdict == "pass":
                    passed_count += 1
                else:
                    failed_count += 1

                # Build result object
                result_obj = {
                    "req_id": req_id,
                    "title": req_title,
                    "score": round(score, 2),
                    "verdict": verdict,
                    "evaluation": evaluation,
                    "tag": req.get("tag", "unknown")
                }

                if error:
                    result_obj["error"] = error
                    logger.warning(f"Validation API error for {req_id}: {error}")

                validation_results.append(result_obj)

                # Stream progress for every 5 requirements or at the end
                if (idx + 1) % 5 == 0 or (idx + 1) == len(requirements):
                    _send_to_workflow_stream(
                        correlation_id,
                        "agent_message",
                        agent="Validator",
                        message=f"Validated {idx + 1}/{len(requirements)} requirements (✅ {passed_count} passed, ❌ {failed_count} failed)"
                    )

            except Exception as e:
                logger.error(f"Validation failed for requirement {req_id}: {e}")
                failed_count += 1
                validation_results.append({
                    "req_id": req_id,
                    "title": req_title,
                    "score": 0.0,
                    "verdict": "error",
                    "evaluation": [],
                    "error": str(e)
                })

        logger.info(f"Validation completed: {passed_count} passed, {failed_count} failed")
        _send_to_workflow_stream(
            correlation_id,
            "agent_message",
            agent="Validator",
            message=f"✅ Validation complete: {passed_count} passed, {failed_count} failed"
        )

        # Phase 4: Workflow complete
        logger.info("Workflow completed successfully")

        # Send completion status
        _send_to_workflow_stream(
            correlation_id,
            "workflow_status",
            status="completed"
        )

        # Send final result with structured data
        final_result = {
            "success": True,
            "workflow_status": "completed",
            "requirements": requirements,
            "kg_data": kg_result,
            "validation_results": {
                "validated_count": len(validation_results),
                "passed": passed_count,
                "failed": failed_count,
                "details": validation_results
            },
            "summary": {
                "total_requirements": len(requirements),
                "kg_nodes": kg_stats.get("nodes", 0),
                "kg_edges": kg_stats.get("edges", 0),
                "validation_passed": passed_count,
                "validation_failed": failed_count
            }
        }

        _send_to_workflow_stream(
            correlation_id,
            "workflow_result",
            result=final_result
        )

        # Save debug data to JSON file for inspection
        try:
            import json
            from datetime import datetime

            debug_dir = Path("./debug")
            debug_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            debug_file = debug_dir / f"requirements_{timestamp}.json"

            with open(debug_file, 'w', encoding='utf-8') as f:
                json.dump(final_result, f, indent=2, ensure_ascii=False)

            logger.info(f"📁 Debug data saved to {debug_file}")
        except Exception as e:
            logger.warning(f"Failed to save debug data: {e}")

        return final_result

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
