# -*- coding: utf-8 -*-
"""
SocietyOfMindAgent-based Requirements Enhancement System

This module implements an iterative enhancement system that:
1. Evaluates requirements against IEEE 29148 criteria
2. Identifies specific issues that prevent the requirement from fulfilling its PURPOSE
3. Asks clarifying questions to the user when information is missing
4. Re-evaluates after each answer until quality threshold is met
5. Persists state between iterations for fresh restarts

The inner team includes:
- PurposeAnalyzer: Identifies what the requirement should achieve
- GapDetector: Finds missing information for the purpose
- QuestionGenerator: Creates specific questions to fill gaps
- RewriteAgent: Generates enhanced requirement after answers

Usage:
    enhancement_service = get_enhancement_service()
    result = await enhancement_service.enhance_with_iteration(
        requirement_text="...",
        websocket=ws
    )
    
    # Or for batch auto-enhancement:
    results = await enhancement_service.run_auto_batch([
        {"id": "REQ-001", "text": "..."},
        {"id": "REQ-002", "text": "..."}
    ])
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Callable, Dict, List, Optional, Awaitable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

# AutoGen imports
try:
    from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_agentchat.conditions import TextMentionTermination  
    from autogen_agentchat.messages import TextMessage
    from autogen_core import CancellationToken
    AUTOGEN_AGENTCHAT_AVAILABLE = True
except ImportError:
    AUTOGEN_AGENTCHAT_AVAILABLE = False
    AssistantAgent = None
    UserProxyAgent = None
    RoundRobinGroupChat = None
    TextMentionTermination = None
    TextMessage = None
    CancellationToken = None

# OpenAI model client
try:
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    OPENAI_CLIENT_AVAILABLE = True
except ImportError:
    OPENAI_CLIENT_AVAILABLE = False
    OpenAIChatCompletionClient = None

from backend.core import settings

logger = logging.getLogger(__name__)


class EnhancementStatus(Enum):
    """Status of an enhancement session"""
    PENDING = "pending"
    ANALYZING = "analyzing"
    AWAITING_ANSWER = "awaiting_answer"
    REWRITING = "rewriting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EnhancementState:
    """
    Persistent state for an enhancement session.
    Allows fresh restarts while maintaining context.
    """
    session_id: str
    original_text: str
    current_text: str
    status: EnhancementStatus = EnhancementStatus.PENDING
    iteration: int = 0
    max_iterations: int = 5
    quality_threshold: float = 0.7
    
    # Purpose and gap analysis
    identified_purpose: str = ""
    identified_gaps: List[str] = field(default_factory=list)
    
    # Questions and answers
    pending_question: Optional[Dict[str, Any]] = None
    answered_questions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Evaluation history
    evaluation_history: List[Dict[str, Any]] = field(default_factory=list)
    current_score: float = 0.0
    
    # Agent messages for debugging
    agent_messages: List[Dict[str, str]] = field(default_factory=list)
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for persistence"""
        return {
            **asdict(self),
            "status": self.status.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnhancementState":
        """Restore state from dictionary"""
        data = data.copy()
        data["status"] = EnhancementStatus(data.get("status", "pending"))
        return cls(**data)


@dataclass
class ClarificationRequest:
    """Request for user clarification"""
    request_id: str
    question: str
    context: str
    purpose: str = ""
    gap_being_addressed: str = ""
    options: List[str] = field(default_factory=list)
    requirement_text: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class EnhancementResult:
    """Result of requirement enhancement"""
    original_text: str
    enhanced_text: str
    final_score: float = 0.0
    iterations_used: int = 0
    questions_asked: int = 0
    splits: List[str] = field(default_factory=list)
    changes_made: List[str] = field(default_factory=list)
    purpose_identified: str = ""
    gaps_filled: List[str] = field(default_factory=list)
    gaps_remaining: List[str] = field(default_factory=list)
    agent_messages: List[Dict[str, str]] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


@dataclass
class BatchEnhancementResult:
    """Result of batch enhancement operation"""
    requirements: List[Dict[str, Any]]
    total_processed: int = 0
    passed_count: int = 0
    failed_count: int = 0
    improved_count: int = 0
    average_score: float = 0.0
    total_time_ms: int = 0
    success: bool = True
    error: Optional[str] = None


class EnhancementStateStore:
    """
    Simple in-memory store for enhancement states.
    Allows retrieving state to restart enhancement fresh.
    """
    
    def __init__(self):
        self._states: Dict[str, EnhancementState] = {}
    
    def save(self, state: EnhancementState):
        """Save state"""
        state.updated_at = datetime.now().isoformat()
        self._states[state.session_id] = state
    
    def get(self, session_id: str) -> Optional[EnhancementState]:
        """Get state by session ID"""
        return self._states.get(session_id)
    
    def delete(self, session_id: str):
        """Delete state"""
        if session_id in self._states:
            del self._states[session_id]
    
    def list_pending(self) -> List[EnhancementState]:
        """List states awaiting user answer"""
        return [
            s for s in self._states.values()
            if s.status == EnhancementStatus.AWAITING_ANSWER
        ]


# Global state store
_state_store = EnhancementStateStore()


class SocietyOfMindEnhancement:
    """
    Iterative Requirements Enhancement System.
    
    The system works in cycles:
    1. Analyze requirement PURPOSE (what it should achieve)
    2. Detect GAPS (missing information for the purpose)
    3. Generate targeted QUESTION to fill most critical gap
    4. Wait for user ANSWER (or auto-generate in auto_mode)
    5. REWRITE requirement with answer incorporated
    6. RE-EVALUATE - if still below threshold, go to step 2
    7. COMPLETE when quality threshold met or max iterations reached
    
    Modes:
    - Interactive: Asks user for clarification via WebSocket
    - Auto: Automatically generates best-guess answers or returns gaps as suggestions
    """
    
    # Coordinated prompts focused on PURPOSE
    
    PURPOSE_ANALYZER_PROMPT = """You are a Purpose Analyst for software requirements.

Your ONLY job is to identify the CORE PURPOSE of a requirement - what it should achieve for the user/system.

Given a requirement, analyze:
1. WHO is the actor (user, system, admin)?
2. WHAT action or capability is needed?
3. WHY - what value or goal does this serve?
4. WHEN/WHERE does this apply (if specified)?

Output format:
PURPOSE: [One clear sentence describing the requirement's purpose]
ACTOR: [Who performs/benefits]
ACTION: [What is being done]
VALUE: [Why this matters]

Be specific. If the purpose is unclear, say: PURPOSE_UNCLEAR: [what's missing]"""

    GAP_DETECTOR_PROMPT = """You are a Gap Detector for software requirements.

Given a requirement and its identified PURPOSE, find SPECIFIC GAPS - missing information that prevents the requirement from clearly expressing its purpose.

Check for these gap types:
- MEASURABILITY: Can success be measured? Are metrics defined?
- SPECIFICITY: Are vague terms like "fast", "user-friendly" used without definition?
- COMPLETENESS: Is all information needed for implementation present?
- TESTABILITY: Can this be verified through a test?
- ATOMICITY: Does it express a single concern?

Output format:
GAPS:
1. [GAP_TYPE]: [Specific description of what's missing]
2. [GAP_TYPE]: [Specific description of what's missing]

If no significant gaps: GAPS_NONE: The requirement adequately expresses its purpose.

CRITICAL_GAP: [The most important gap to address first]"""

    QUESTION_GENERATOR_PROMPT = """You are a Question Generator for requirements clarification.

Given a requirement, its PURPOSE, and identified GAPS, generate ONE specific question that:
1. Addresses the CRITICAL_GAP
2. Will provide concrete, measurable information
3. Is easy for a stakeholder to answer
4. Will significantly improve the requirement quality

Output format:
QUESTION: [Your specific question]
GAP_ADDRESSED: [Which gap this fills]
EXPECTED_ANSWER_TYPE: [number/text/choice/yes-no]
EXAMPLE_ANSWERS: [2-3 example valid answers]

Make the question conversational but precise."""

    REWRITE_PROMPT = """You are a Requirements Rewrite Expert.

Given:
- Original requirement
- Identified PURPOSE
- User's ANSWER to clarification question
- Previous evaluation feedback

Your job: Rewrite the requirement to:
1. Clearly express the PURPOSE
2. Incorporate the user's ANSWER naturally
3. Fix any identified quality issues
4. Follow IEEE 29148 best practices (atomic, testable, measurable)

Output format:
REWRITTEN: [The improved requirement text]
CHANGES: [List of changes made]
INCORPORATED: [How the answer was used]

If the requirement is now complete:
COMPLETE: [The final requirement text]
SCORE_ESTIMATE: [0.0-1.0 estimated quality]"""

    EVALUATOR_PROMPT = """You are a Requirement Quality Evaluator.

Evaluate the requirement against IEEE 29148 criteria:
- Atomic (single testable statement): 0.0-1.0
- Clear (unambiguous language): 0.0-1.0  
- Measurable (quantifiable success): 0.0-1.0
- Testable (verifiable through test): 0.0-1.0
- Complete (all info present): 0.0-1.0

Output format:
SCORES:
- atomic: [score]
- clear: [score]
- measurable: [score]
- testable: [score]
- complete: [score]
TOTAL: [weighted average]
VERDICT: [PASS if >= 0.7, FAIL otherwise]
WEAKEST: [criterion with lowest score]
SUGGESTION: [one specific improvement for weakest criterion]"""

    # New prompt for auto-generating answers
    AUTO_ANSWER_PROMPT = """You are an expert at inferring reasonable values for software requirements.

Given:
- A requirement with missing information
- The identified PURPOSE
- The QUESTION being asked
- Example possible answers

Your job: Provide the BEST reasonable answer that would make this requirement:
1. Specific and measurable
2. Industry-standard if applicable
3. Achievable for typical software systems

Output format:
ANSWER: [Your best-guess answer]
REASONING: [Why this is a reasonable default]
CONFIDENCE: [high/medium/low]

If you cannot reasonably infer an answer:
CANNOT_INFER: [reason]
NEED_STAKEHOLDER: [what specific information is needed]"""

    def __init__(self, max_concurrent: int = 5):
        """Initialize the enhancement system."""
        self.state_store = _state_store
        self.model_client = None
        self._initialized = False
        self.max_concurrent = max_concurrent
        
        if not AUTOGEN_AGENTCHAT_AVAILABLE:
            logger.warning("autogen_agentchat not available - SocietyOfMind disabled")
            return
            
        if not OPENAI_CLIENT_AVAILABLE:
            logger.warning("autogen_ext.models.openai not available - SocietyOfMind disabled")
            return
        
        self._initialize_model_client()
    
    def _initialize_model_client(self):
        """Initialize the OpenAI model client."""
        try:
            llm_config = settings.get_llm_config()
            api_key = llm_config.get("api_key", "")
            base_url = llm_config.get("base_url")
            model = settings.OPENAI_MODEL
            
            if not api_key:
                logger.warning("No API key configured for SocietyOfMind agents")
                return
            
            # Configure model client
            if base_url and "openrouter" in base_url.lower():
                self.model_client = OpenAIChatCompletionClient(
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                    model_info={
                        "vision": False,
                        "function_calling": True,
                        "json_output": True,
                        "family": "gpt-4"
                    }
                )
            else:
                self.model_client = OpenAIChatCompletionClient(
                    model=model,
                    api_key=api_key
                )
            
            self._initialized = True
            logger.info(f"SocietyOfMindEnhancement initialized with model: {model}")
            
        except Exception as e:
            logger.error(f"Failed to initialize model client: {e}")
            self._initialized = False
    
    async def _call_agent(self, system_prompt: str, user_message: str) -> str:
        """Call a single agent and get response."""
        if not self._initialized:
            raise RuntimeError("Enhancement system not initialized")
        
        agent = AssistantAgent(
            name="agent",
            model_client=self.model_client,
            system_message=system_prompt
        )
        
        # Simple single-turn call
        result = await agent.on_messages(
            [TextMessage(content=user_message, source="user")],
            CancellationToken()
        )
        
        return result.chat_message.content if result.chat_message else ""
    
    # =========================================================================
    # NEW: Auto Batch Enhancement Methods
    # =========================================================================
    
    async def run_auto_batch(
        self,
        requirements: List[Dict[str, Any]],
        quality_threshold: float = 0.7,
        max_iterations: int = 3,
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None
    ) -> BatchEnhancementResult:
        """
        Run automatic enhancement on a batch of requirements.
        
        This mode does NOT ask user questions - instead it:
        1. Analyzes and evaluates each requirement
        2. Auto-generates reasonable values for missing metrics
        3. Rewrites requirements to be measurable and testable
        4. Returns gaps that cannot be auto-filled as suggestions
        
        Args:
            requirements: List of {"id": str, "text": str} dicts
            quality_threshold: Target score (default 0.7)
            max_iterations: Max enhancement cycles per requirement
            progress_callback: Optional callback(stage, completed, total, message)
            
        Returns:
            BatchEnhancementResult with all processed requirements
        """
        if not self._initialized:
            return BatchEnhancementResult(
                requirements=[],
                success=False,
                error="Enhancement system not initialized"
            )
        
        import time
        start_time = time.time()
        
        total = len(requirements)
        results: List[Dict[str, Any]] = []
        passed = 0
        improved = 0
        
        # Process requirements with concurrency limit
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_one(req: Dict[str, Any], index: int) -> Dict[str, Any]:
            async with semaphore:
                req_id = req.get("id", f"REQ-{index}")
                req_text = req.get("text", req.get("title", ""))
                
                if progress_callback:
                    progress_callback("enhancing", index, total, f"Processing {req_id}")
                
                try:
                    result = await self._run_auto_enhancement(
                        req_id=req_id,
                        requirement_text=req_text,
                        quality_threshold=quality_threshold,
                        max_iterations=max_iterations
                    )
                    return result
                except Exception as e:
                    logger.error(f"Failed to enhance {req_id}: {e}")
                    return {
                        "id": req_id,
                        "original_text": req_text,
                        "enhanced_text": req_text,
                        "score": 0.0,
                        "verdict": "fail",
                        "error": str(e),
                        "success": False
                    }
        
        # Run all enhancements
        tasks = [process_one(req, i) for i, req in enumerate(requirements)]
        results = await asyncio.gather(*tasks)
        
        # Calculate statistics
        scores = []
        for r in results:
            if r.get("score", 0) >= quality_threshold:
                passed += 1
            if r.get("enhanced_text") != r.get("original_text"):
                improved += 1
            scores.append(r.get("score", 0))
        
        avg_score = sum(scores) / len(scores) if scores else 0.0
        total_time = int((time.time() - start_time) * 1000)
        
        if progress_callback:
            progress_callback("complete", total, total, f"Done: {passed}/{total} passed")
        
        return BatchEnhancementResult(
            requirements=results,
            total_processed=total,
            passed_count=passed,
            failed_count=total - passed,
            improved_count=improved,
            average_score=avg_score,
            total_time_ms=total_time,
            success=True
        )
    
    async def _run_auto_enhancement(
        self,
        req_id: str,
        requirement_text: str,
        quality_threshold: float = 0.7,
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Run automatic enhancement on a single requirement without user interaction.
        
        The flow:
        1. Analyze PURPOSE
        2. Detect GAPS
        3. Evaluate quality
        4. If below threshold: auto-generate answers for gaps and rewrite
        5. Repeat until threshold met or max iterations
        """
        current_text = requirement_text
        iteration = 0
        identified_purpose = ""
        all_gaps = []
        gaps_remaining = []
        changes = []
        
        while iteration < max_iterations:
            iteration += 1
            
            # Step 1: Analyze purpose
            purpose_response = await self._call_agent(
                self.PURPOSE_ANALYZER_PROMPT,
                f"Analyze this requirement:\n\n{current_text}"
            )
            
            if "PURPOSE:" in purpose_response:
                identified_purpose = purpose_response.split("PURPOSE:")[-1].split("\n")[0].strip()
            
            # Step 2: Detect gaps
            gap_input = f"""Requirement: {current_text}
Purpose: {identified_purpose}"""
            
            gap_response = await self._call_agent(self.GAP_DETECTOR_PROMPT, gap_input)
            
            # Parse gaps
            current_gaps = []
            if "GAPS:" in gap_response and "GAPS_NONE" not in gap_response:
                gaps_section = gap_response.split("GAPS:")[-1]
                for line in gaps_section.split("\n"):
                    line = line.strip()
                    if line and (line[0].isdigit() or line.startswith("-")):
                        gap = line.lstrip("0123456789.-) ").strip()
                        if gap and "CRITICAL_GAP" not in gap:
                            current_gaps.append(gap)
                            if gap not in all_gaps:
                                all_gaps.append(gap)
            
            critical_gap = ""
            if "CRITICAL_GAP:" in gap_response:
                critical_gap = gap_response.split("CRITICAL_GAP:")[-1].split("\n")[0].strip()
            
            # Step 3: Evaluate
            eval_response = await self._call_agent(
                self.EVALUATOR_PROMPT,
                f"Evaluate this requirement:\n\n{current_text}"
            )
            
            # Parse score
            current_score = 0.5
            if "TOTAL:" in eval_response:
                try:
                    total_str = eval_response.split("TOTAL:")[-1].split("\n")[0].strip()
                    current_score = float(total_str)
                except ValueError:
                    pass
            
            # Check if threshold met
            if current_score >= quality_threshold:
                logger.info(f"{req_id}: Enhancement complete at iteration {iteration}, score: {current_score:.2f}")
                break
            
            # Step 4: If gaps exist, auto-generate answer and rewrite
            if not critical_gap and current_gaps:
                critical_gap = current_gaps[0]
            
            if critical_gap and "GAPS_NONE" not in gap_response:
                # Generate question first
                question_input = f"""Requirement: {current_text}
Purpose: {identified_purpose}
Critical gap to address: {critical_gap}"""
                
                question_response = await self._call_agent(self.QUESTION_GENERATOR_PROMPT, question_input)
                
                question_text = ""
                if "QUESTION:" in question_response:
                    question_text = question_response.split("QUESTION:")[-1].split("\n")[0].strip()
                
                examples = ""
                if "EXAMPLE_ANSWERS:" in question_response:
                    examples = question_response.split("EXAMPLE_ANSWERS:")[-1].split("\n")[0]
                
                # Auto-generate answer
                auto_answer_input = f"""Requirement: {current_text}
Purpose: {identified_purpose}
Question: {question_text}
Gap being addressed: {critical_gap}
Example possible answers: {examples}"""
                
                auto_answer_response = await self._call_agent(self.AUTO_ANSWER_PROMPT, auto_answer_input)
                
                auto_answer = ""
                if "ANSWER:" in auto_answer_response:
                    auto_answer = auto_answer_response.split("ANSWER:")[-1].split("\n")[0].strip()
                
                # Check if we could generate an answer
                if "CANNOT_INFER" in auto_answer_response:
                    # Cannot auto-fill this gap - record it
                    gaps_remaining.append(critical_gap)
                    logger.info(f"{req_id}: Cannot auto-fill gap: {critical_gap}")
                    # Still try to improve other aspects
                    auto_answer = "[to be determined by stakeholder]"
                
                # Rewrite with auto-generated answer
                rewrite_input = f"""Original requirement: {requirement_text}
Current requirement: {current_text}
Purpose: {identified_purpose}

User answered: {auto_answer}
Question was about: {critical_gap}

Please rewrite the requirement incorporating this answer."""
                
                rewrite_response = await self._call_agent(self.REWRITE_PROMPT, rewrite_input)
                
                # Extract rewritten text
                if "REWRITTEN:" in rewrite_response:
                    new_text = rewrite_response.split("REWRITTEN:")[-1].split("\n")[0].strip()
                    if new_text and new_text != current_text:
                        changes.append(f"Gap '{critical_gap}' addressed with: {auto_answer[:50]}...")
                        current_text = new_text
                elif "COMPLETE:" in rewrite_response:
                    new_text = rewrite_response.split("COMPLETE:")[-1].split("\n")[0].strip()
                    if new_text:
                        current_text = new_text
        
        # Final evaluation
        final_eval = await self._call_agent(
            self.EVALUATOR_PROMPT,
            f"Evaluate this requirement:\n\n{current_text}"
        )
        
        final_score = 0.5
        if "TOTAL:" in final_eval:
            try:
                final_score = float(final_eval.split("TOTAL:")[-1].split("\n")[0].strip())
            except ValueError:
                pass
        
        verdict = "pass" if final_score >= quality_threshold else "fail"
        
        return {
            "id": req_id,
            "original_text": requirement_text,
            "enhanced_text": current_text,
            "score": final_score,
            "verdict": verdict,
            "iterations": iteration,
            "purpose": identified_purpose,
            "gaps_filled": [g for g in all_gaps if g not in gaps_remaining],
            "gaps_remaining": gaps_remaining,
            "changes": changes,
            "success": True
        }
    
    # =========================================================================
    # Original Interactive Methods (unchanged)
    # =========================================================================
    
    async def start_enhancement(
        self,
        requirement_text: str,
        session_id: Optional[str] = None,
        websocket = None
    ) -> EnhancementState:
        """
        Start a new enhancement session.
        
        Returns the initial state with first question.
        """
        if not self._initialized:
            raise RuntimeError("Enhancement system not initialized")
        
        # Create new state
        session_id = session_id or str(uuid.uuid4())
        state = EnhancementState(
            session_id=session_id,
            original_text=requirement_text,
            current_text=requirement_text
        )
        
        # Save initial state
        self.state_store.save(state)
        
        # Run first iteration
        return await self._run_iteration(state, websocket)
    
    async def continue_enhancement(
        self,
        session_id: str,
        answer: str,
        websocket = None
    ) -> EnhancementState:
        """
        Continue enhancement after user provides answer.
        
        Incorporates answer and runs fresh evaluation cycle.
        """
        state = self.state_store.get(session_id)
        if not state:
            raise ValueError(f"No session found: {session_id}")
        
        if state.status != EnhancementStatus.AWAITING_ANSWER:
            raise ValueError(f"Session not awaiting answer: {state.status}")
        
        # Store the answer
        if state.pending_question:
            answered = {
                **state.pending_question,
                "answer": answer,
                "answered_at": datetime.now().isoformat()
            }
            state.answered_questions.append(answered)
            state.pending_question = None
        
        # Increment iteration
        state.iteration += 1
        
        # Run next iteration (fresh evaluation with answer incorporated)
        return await self._run_iteration(state, websocket, answer)
    
    async def _run_iteration(
        self,
        state: EnhancementState,
        websocket = None,
        user_answer: Optional[str] = None
    ) -> EnhancementState:
        """
        Run one iteration of the enhancement cycle.
        
        1. If answer provided: Rewrite requirement with answer
        2. Analyze purpose
        3. Detect gaps
        4. Evaluate quality
        5. If quality OK: Complete
        6. If gaps: Generate question
        """
        try:
            state.status = EnhancementStatus.ANALYZING
            self.state_store.save(state)
            
            # Step 0: If answer provided, rewrite first
            if user_answer and state.answered_questions:
                await self._send_ws_message(websocket, "progress", 
                    f"📝 Incorporating your answer into requirement...")
                
                rewrite_input = f"""Original requirement: {state.original_text}
Current requirement: {state.current_text}
Purpose: {state.identified_purpose}

User answered: {user_answer}
Question was about: {state.answered_questions[-1].get('gap_being_addressed', 'quality improvement')}

Please rewrite the requirement incorporating this answer."""
                
                state.status = EnhancementStatus.REWRITING
                self.state_store.save(state)
                
                rewrite_response = await self._call_agent(self.REWRITE_PROMPT, rewrite_input)
                state.agent_messages.append({"source": "rewriter", "content": rewrite_response})
                
                # Extract rewritten text
                if "REWRITTEN:" in rewrite_response:
                    state.current_text = rewrite_response.split("REWRITTEN:")[-1].split("\n")[0].strip()
                elif "COMPLETE:" in rewrite_response:
                    state.current_text = rewrite_response.split("COMPLETE:")[-1].split("\n")[0].strip()
                
                await self._send_ws_message(websocket, "rewritten", 
                    f"✏️ Rewritten: {state.current_text}")
            
            # Step 1: Analyze purpose
            await self._send_ws_message(websocket, "progress", 
                f"🎯 Analyzing requirement purpose...")
            
            purpose_response = await self._call_agent(
                self.PURPOSE_ANALYZER_PROMPT,
                f"Analyze this requirement:\n\n{state.current_text}"
            )
            state.agent_messages.append({"source": "purpose_analyzer", "content": purpose_response})
            
            if "PURPOSE:" in purpose_response:
                state.identified_purpose = purpose_response.split("PURPOSE:")[-1].split("\n")[0].strip()
            
            await self._send_ws_message(websocket, "purpose", 
                f"🎯 Purpose: {state.identified_purpose}")
            
            # Step 2: Detect gaps
            await self._send_ws_message(websocket, "progress", 
                f"🔍 Detecting missing information...")
            
            gap_input = f"""Requirement: {state.current_text}
Purpose: {state.identified_purpose}
Previous answers: {json.dumps([q.get('answer') for q in state.answered_questions])}"""
            
            gap_response = await self._call_agent(self.GAP_DETECTOR_PROMPT, gap_input)
            state.agent_messages.append({"source": "gap_detector", "content": gap_response})
            
            # Parse gaps
            state.identified_gaps = []
            if "GAPS:" in gap_response and "GAPS_NONE" not in gap_response:
                gaps_section = gap_response.split("GAPS:")[-1]
                for line in gaps_section.split("\n"):
                    line = line.strip()
                    if line and (line[0].isdigit() or line.startswith("-")):
                        gap = line.lstrip("0123456789.-) ").strip()
                        if gap and "CRITICAL_GAP" not in gap:
                            state.identified_gaps.append(gap)
            
            # Extract critical gap
            critical_gap = ""
            if "CRITICAL_GAP:" in gap_response:
                critical_gap = gap_response.split("CRITICAL_GAP:")[-1].split("\n")[0].strip()
            
            # Step 3: Evaluate quality
            await self._send_ws_message(websocket, "progress", 
                f"📊 Evaluating quality...")
            
            eval_response = await self._call_agent(
                self.EVALUATOR_PROMPT,
                f"Evaluate this requirement:\n\n{state.current_text}"
            )
            state.agent_messages.append({"source": "evaluator", "content": eval_response})
            
            # Parse score
            if "TOTAL:" in eval_response:
                try:
                    total_str = eval_response.split("TOTAL:")[-1].split("\n")[0].strip()
                    state.current_score = float(total_str)
                except ValueError:
                    state.current_score = 0.5
            
            state.evaluation_history.append({
                "iteration": state.iteration,
                "score": state.current_score,
                "text": state.current_text,
                "response": eval_response
            })
            
            await self._send_ws_message(websocket, "evaluation", 
                f"📊 Score: {state.current_score:.2f}")
            
            # Step 4: Check if complete
            if state.current_score >= state.quality_threshold:
                state.status = EnhancementStatus.COMPLETED
                self.state_store.save(state)
                
                # Send complete with full result data
                await self._send_ws_message(websocket, "complete", 
                    f"✅ Enhancement complete! Score: {state.current_score:.2f}",
                    data={
                        "original_text": state.original_text,
                        "enhanced_text": state.current_text,
                        "final_score": state.current_score,
                        "iterations_used": state.iteration,
                        "questions_asked": len(state.answered_questions),
                        "purpose_identified": state.identified_purpose,
                        "success": True
                    })
                
                return state
            
            # Step 5: Check max iterations
            if state.iteration >= state.max_iterations:
                state.status = EnhancementStatus.COMPLETED
                self.state_store.save(state)
                
                # Send complete with full result data
                await self._send_ws_message(websocket, "complete", 
                    f"⚠️ Max iterations reached. Final score: {state.current_score:.2f}",
                    data={
                        "original_text": state.original_text,
                        "enhanced_text": state.current_text,
                        "final_score": state.current_score,
                        "iterations_used": state.iteration,
                        "questions_asked": len(state.answered_questions),
                        "purpose_identified": state.identified_purpose,
                        "success": True
                    })
                
                return state
            
            # Step 6: Generate question for most critical gap
            if not critical_gap and state.identified_gaps:
                critical_gap = state.identified_gaps[0]
            
            if critical_gap or "GAPS_NONE" not in gap_response:
                await self._send_ws_message(websocket, "progress", 
                    f"❓ Generating clarification question...")
                
                question_input = f"""Requirement: {state.current_text}
Purpose: {state.identified_purpose}
Critical gap to address: {critical_gap}
All identified gaps: {state.identified_gaps}
Questions already asked: {[q.get('question') for q in state.answered_questions]}"""
                
                question_response = await self._call_agent(self.QUESTION_GENERATOR_PROMPT, question_input)
                state.agent_messages.append({"source": "question_generator", "content": question_response})
                
                # Parse question
                question_text = ""
                if "QUESTION:" in question_response:
                    question_text = question_response.split("QUESTION:")[-1].split("\n")[0].strip()
                
                # Extract example answers
                examples = []
                if "EXAMPLE_ANSWERS:" in question_response:
                    examples_section = question_response.split("EXAMPLE_ANSWERS:")[-1].split("\n")[0]
                    examples = [e.strip() for e in examples_section.split(",") if e.strip()]
                
                if question_text:
                    state.pending_question = {
                        "request_id": str(uuid.uuid4()),
                        "question": question_text,
                        "gap_being_addressed": critical_gap,
                        "purpose": state.identified_purpose,
                        "example_answers": examples,
                        "iteration": state.iteration,
                        "timestamp": datetime.now().isoformat()
                    }
                    state.status = EnhancementStatus.AWAITING_ANSWER
                    self.state_store.save(state)
                    
                    # Send question to WebSocket
                    await self._send_ws_message(websocket, "clarification_request", 
                        question_text, data=state.pending_question)
                    
                    return state
            
            # No more gaps - complete
            state.status = EnhancementStatus.COMPLETED
            self.state_store.save(state)
            
            # Send complete with full result data
            await self._send_ws_message(websocket, "complete", 
                f"✅ No more gaps to address. Final score: {state.current_score:.2f}",
                data={
                    "original_text": state.original_text,
                    "enhanced_text": state.current_text,
                    "final_score": state.current_score,
                    "iterations_used": state.iteration,
                    "questions_asked": len(state.answered_questions),
                    "purpose_identified": state.identified_purpose,
                    "success": True
                })
            
            return state
            
        except Exception as e:
            logger.error(f"Enhancement iteration failed: {e}", exc_info=True)
            state.status = EnhancementStatus.FAILED
            self.state_store.save(state)
            
            await self._send_ws_message(websocket, "error", str(e))
            
            raise
    
    async def _send_ws_message(
        self,
        websocket,
        msg_type: str,
        message: str,
        data: Optional[Dict] = None
    ):
        """Send message to WebSocket if available."""
        if not websocket:
            return
        
        try:
            payload = {
                "type": msg_type,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            if data:
                payload["data"] = data
            
            await websocket.send_json(payload)
        except Exception as e:
            logger.warning(f"Failed to send WS message: {e}")
    
    def get_state(self, session_id: str) -> Optional[EnhancementState]:
        """Get enhancement state by session ID."""
        return self.state_store.get(session_id)
    
    def get_result(self, state: EnhancementState) -> EnhancementResult:
        """Convert state to final result."""
        return EnhancementResult(
            original_text=state.original_text,
            enhanced_text=state.current_text,
            final_score=state.current_score,
            iterations_used=state.iteration,
            questions_asked=len(state.answered_questions),
            purpose_identified=state.identified_purpose,
            gaps_filled=[q.get("gap_being_addressed", "") for q in state.answered_questions],
            gaps_remaining=state.identified_gaps,
            changes_made=[f"Q{i+1}: {q.get('question', '')[:50]}..." for i, q in enumerate(state.answered_questions)],
            agent_messages=state.agent_messages[-10:],
            success=state.status == EnhancementStatus.COMPLETED,
            error=None if state.status != EnhancementStatus.FAILED else "Enhancement failed"
        )
    
    # Legacy method for backward compatibility
    async def enhance_requirement(
        self,
        requirement_text: str,
        context: Optional[Dict[str, Any]] = None,
        websocket = None
    ) -> EnhancementResult:
        """Legacy method - starts enhancement and returns initial state as result."""
        state = await self.start_enhancement(requirement_text, websocket=websocket)
        return self.get_result(state)
    
    def handle_clarification_response(self, request_id: str, response: str):
        """Legacy method for handling clarification responses."""
        # Find session with this pending request
        for state in self.state_store._states.values():
            if (state.pending_question and 
                state.pending_question.get("request_id") == request_id):
                # Note: This synchronous method can't run the async continuation
                # The WebSocket handler should call continue_enhancement instead
                logger.info(f"Clarification response received for session {state.session_id}")
                return


# Singleton instance
_enhancement_instance: Optional[SocietyOfMindEnhancement] = None


def get_enhancement_service() -> SocietyOfMindEnhancement:
    """Get or create singleton SocietyOfMindEnhancement instance."""
    global _enhancement_instance
    if _enhancement_instance is None:
        _enhancement_instance = SocietyOfMindEnhancement()
    return _enhancement_instance