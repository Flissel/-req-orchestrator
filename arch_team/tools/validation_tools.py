# -*- coding: utf-8 -*-
"""
Validation Tools for Requirements Quality Assurance.

Provides FunctionTool wrappers for AutoGen agents to interact with:
- Evaluation API (quality assessment)
- Rewrite API (requirement improvement)
- Suggestion API (atomic improvements)
- Qdrant KG (duplicate detection via semantic search)
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import requests

from ..runtime.logging import get_logger

logger = get_logger("tools.validation")

# API Base URL - Use ARCH_TEAM_PORT (8000) or BACKEND_PORT (8087) based on configuration
# VALIDATION_API_BASE overrides everything if set
_arch_port = os.environ.get("ARCH_TEAM_PORT", "8000")
_backend_port = os.environ.get("BACKEND_PORT", "8087")
# Default to backend port for API v2 endpoints
API_BASE = os.environ.get("VALIDATION_API_BASE", f"http://localhost:{_backend_port}")
# Timeout for API calls (default 120s - allows for batch processing with sequential LLM calls)
API_TIMEOUT = int(os.environ.get("VALIDATION_TIMEOUT", "120"))


def evaluate_requirement(
    requirement_text: str,
    criteria_keys: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Evaluates a requirement against quality criteria using the Evaluation API.

    Args:
        requirement_text: The requirement to evaluate against quality criteria
        criteria_keys: Quality criteria (clarity, testability, measurability). Defaults to all.

    Returns:
        {
            "score": 0.85,
            "verdict": "pass|fail",
            "evaluation": [
                {"criterion": "clarity", "score": 0.9, "passed": true, "feedback": "..."}
            ]
        }

    Raises:
        requests.RequestException: If API call fails
    """
    try:
        url = f"{API_BASE}/api/v2/evaluate/single"
        payload = {
            "text": requirement_text,
            "criteria_keys": criteria_keys  # Let backend use its DEFAULT_CRITERIA_KEYS (all 10)
        }

        logger.info(f"Evaluating requirement via {url}")
        response = requests.post(url, json=payload, timeout=API_TIMEOUT)
        response.raise_for_status()

        result = response.json()
        logger.info(f"Evaluation result: score={result.get('score')}, verdict={result.get('verdict')}")
        return result

    except requests.RequestException as e:
        logger.error(f"Evaluation API call failed: {e}")
        # Return fallback result
        return {
            "score": 0.0,
            "verdict": "fail",
            "evaluation": [],
            "error": str(e)
        }


def rewrite_requirement(
    requirement_text: str
) -> Dict[str, Any]:
    """
    Rewrites a requirement to improve clarity, add User Story format, and follow best practices.

    Args:
        requirement_text: The requirement to improve and rewrite

    Returns:
        {
            "originalText": "...",
            "correctedText": "Als [Rolle] möchte ich [Funktion], damit [Nutzen]",
            "status": "accepted|rejected",
            "score": 0.88,
            "verdict": "pass",
            "evaluation": [...]
        }

    Raises:
        requests.RequestException: If API call fails
    """
    try:
        url = f"{API_BASE}/api/v1/validate/batch"
        payload = {
            "items": [requirement_text]
        }

        logger.info(f"Rewriting requirement via {url}")
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        result_list = response.json()
        if not result_list:
            raise ValueError("Empty response from rewrite API")

        result = result_list[0]
        logger.info(f"Rewrite result: status={result.get('status')}, score={result.get('score')}")
        return result

    except (requests.RequestException, ValueError, IndexError) as e:
        logger.error(f"Rewrite API call failed: {e}")
        # Return fallback result
        return {
            "originalText": requirement_text,
            "correctedText": requirement_text,
            "status": "rejected",
            "score": 0.0,
            "verdict": "fail",
            "evaluation": [],
            "error": str(e)
        }


def suggest_improvements(
    requirement_text: str
) -> List[Dict[str, Any]]:
    """
    Generates atomic improvement suggestions (User Story format, acceptance criteria, etc.).

    Args:
        requirement_text: The requirement to analyze for improvement suggestions

    Returns:
        [
            {"type": "add_actor", "suggestion": "Füge 'Als Dozent' hinzu", "priority": "high"},
            {"type": "add_criteria", "suggestion": "Given-When-Then Kriterien fehlen"}
        ]

    Raises:
        requests.RequestException: If API call fails
    """
    try:
        url = f"{API_BASE}/api/v1/validate/suggest"
        payload = {
            "items": [requirement_text]
        }

        logger.info(f"Suggesting improvements via {url}")
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()
        # Extract suggestions from response format: { "items": { "REQ_1": { "suggestions": [...] } } }
        items = result.get("items", {})
        if not items:
            return []

        # Get first (and only) item's suggestions
        first_key = list(items.keys())[0]
        suggestions = items[first_key].get("suggestions", [])

        logger.info(f"Generated {len(suggestions)} improvement suggestions")
        return suggestions

    except (requests.RequestException, KeyError, IndexError) as e:
        logger.error(f"Suggestion API call failed: {e}")
        return []


def detect_duplicates(
    requirements: List[str],
    similarity_threshold: float = 0.90
) -> List[Dict[str, Any]]:
    """
    Finds semantically similar requirements using embeddings (Qdrant).

    Args:
        requirements: List of requirements to check for semantic duplicates
        similarity_threshold: Cosine similarity threshold (0.0-1.0). Default 0.90.

    Returns:
        [
            {
                "req1_idx": 0,
                "req2_idx": 5,
                "similarity": 0.95,
                "req1_text": "...",
                "req2_text": "...",
                "reason": "Beide beschreiben Video-Wasserzeichen"
            }
        ]

    Notes:
        - Uses Qdrant semantic search on kg_nodes_v1 collection
        - Compares each requirement against all others
        - Returns pairs with similarity >= threshold
    """
    try:
        from ..memory.qdrant_kg import QdrantKGClient

        if len(requirements) < 2:
            return []

        logger.info(f"Detecting duplicates among {len(requirements)} requirements (threshold={similarity_threshold})")

        client = QdrantKGClient()
        duplicates = []

        # Compare each requirement against all others
        for i, req1 in enumerate(requirements):
            # Semantic search for similar requirements
            results = client.search_nodes(req1, top_k=len(requirements))

            for result in results:
                # Extract similarity score
                similarity = result.get("score", 0.0)

                # Check if above threshold and not the same requirement
                if similarity >= similarity_threshold:
                    # Try to find which requirement this matches
                    result_text = result.get("payload", {}).get("name", "")

                    # Find matching requirement index
                    for j, req2 in enumerate(requirements):
                        if j != i and req2 in result_text:
                            # Avoid duplicate pairs (only add if i < j)
                            if i < j:
                                duplicates.append({
                                    "req1_idx": i,
                                    "req2_idx": j,
                                    "similarity": similarity,
                                    "req1_text": req1[:100] + "..." if len(req1) > 100 else req1,
                                    "req2_text": req2[:100] + "..." if len(req2) > 100 else req2,
                                    "reason": f"Semantische Ähnlichkeit: {similarity:.2%}"
                                })
                            break

        logger.info(f"Found {len(duplicates)} duplicate pairs")
        return duplicates

    except Exception as e:
        logger.error(f"Duplicate detection failed: {e}")
        # Fallback: Simple string matching for critical duplicates
        duplicates = []
        for i in range(len(requirements)):
            for j in range(i + 1, len(requirements)):
                # Very basic string similarity (Jaccard)
                words1 = set(requirements[i].lower().split())
                words2 = set(requirements[j].lower().split())
                if not words1 or not words2:
                    continue
                jaccard = len(words1 & words2) / len(words1 | words2)
                if jaccard >= 0.7:  # High string overlap
                    duplicates.append({
                        "req1_idx": i,
                        "req2_idx": j,
                        "similarity": jaccard,
                        "req1_text": requirements[i][:100],
                        "req2_text": requirements[j][:100],
                        "reason": f"String-Ähnlichkeit: {jaccard:.2%}"
                    })
        return duplicates


# --- NEW: Feedback-based Rewriting ---

def rewrite_with_feedback(
    requirement_text: str,
    evaluation: List[Dict[str, Any]],
    score: float = 0.0
) -> Dict[str, Any]:
    """
    Rewrites a requirement based on specific validation feedback.
    
    Uses the evaluation feedback to generate targeted improvements
    following IEEE 29148 standards.

    Args:
        requirement_text: The original requirement to improve
        evaluation: List of criterion evaluations from validate, each with:
            - criterion: Name of the criterion
            - score: Score for this criterion (0-1)
            - passed: Boolean whether it passed
            - feedback: Specific feedback on what's wrong
        score: Overall validation score (for reference)

    Returns:
        {
            "original_text": "...",
            "rewritten_text": "...",
            "improvement_summary": "Addressed 5 failed criteria",
            "addressed_criteria": ["clarity", "testability", ...],
            "error": null
        }

    Example:
        result = rewrite_with_feedback(
            requirement_text="The system must be fast",
            evaluation=[
                {"criterion": "measurability", "score": 0.3, "passed": false, 
                 "feedback": "No metrics defined"}
            ],
            score=0.35
        )
    """
    try:
        import asyncio
        from ..agents.rewrite_worker import RewriteTask, RewriteWorkerAgent
        
        logger.info(f"Rewriting requirement with {len(evaluation)} criteria feedback")
        
        # Create a rewrite task with the feedback
        task = RewriteTask(
            req_id="rewrite-single",
            original_text=requirement_text,
            score=score,
            evaluation=evaluation,
            index=0,
            attempt=1
        )
        
        # Create a semaphore for single use
        semaphore = asyncio.Semaphore(1)
        
        # Create worker and run rewrite
        worker = RewriteWorkerAgent(
            worker_id="rewrite-worker-single",
            semaphore=semaphore
        )
        
        # Run in event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, use asyncio.to_thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(worker.rewrite(task))
                )
                result = future.result(timeout=60)
        else:
            result = loop.run_until_complete(worker.rewrite(task))
        
        return {
            "original_text": result.original_text,
            "rewritten_text": result.rewritten_text,
            "improvement_summary": result.improvement_summary,
            "addressed_criteria": result.addressed_criteria,
            "error": result.error
        }
        
    except Exception as e:
        logger.error(f"Rewrite with feedback failed: {e}")
        return {
            "original_text": requirement_text,
            "rewritten_text": requirement_text,
            "improvement_summary": f"Error: {str(e)}",
            "addressed_criteria": [],
            "error": str(e)
        }


def rewrite_batch_with_feedback(
    failed_requirements: List[Dict[str, Any]],
    max_concurrent: int = 3,
    max_attempts: int = 3,
    target_score: float = 0.7,
    enable_revalidation: bool = True
) -> Dict[str, Any]:
    """
    Rewrites multiple failed requirements in parallel with feedback-based improvement.
    
    Args:
        failed_requirements: List of requirement dicts, each with:
            - req_id: Requirement ID
            - title/text: Original requirement text
            - score: Validation score (should be < 0.7)
            - evaluation: List of criterion evaluations
            - tag: Optional category
        max_concurrent: Maximum parallel rewrites (default 3)
        max_attempts: Maximum rewrite attempts per requirement (default 3)
        target_score: Target validation score (default 0.7)
        enable_revalidation: Whether to re-validate after rewriting (default True)

    Returns:
        {
            "total_count": 10,
            "rewritten_count": 8,
            "improved_count": 6,
            "unchanged_count": 2,
            "error_count": 0,
            "total_time_ms": 45000,
            "details": [...]
        }

    Example:
        from arch_team.tools.validation_tools import rewrite_batch_with_feedback
        
        failed_reqs = [
            {
                "req_id": "REQ-001",
                "title": "System must be fast",
                "score": 0.35,
                "evaluation": [{"criterion": "measurability", "passed": false, ...}]}
        ]
        
        result = rewrite_batch_with_feedback(
            failed_requirements=failed_reqs,
            max_concurrent=3,
            enable_revalidation=True
        )
    """
    try:
        import asyncio
        from ..agents.rewrite_delegator import rewrite_requirements_parallel
        
        logger.info(f"Batch rewriting {len(failed_requirements)} requirements "
                   f"(max_concurrent={max_concurrent}, max_attempts={max_attempts})")
        
        # Run in event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, use asyncio.to_thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(
                        rewrite_requirements_parallel(
                            failed_requirements=failed_requirements,
                            max_concurrent=max_concurrent,
                            max_attempts=max_attempts,
                            target_score=target_score,
                            enable_revalidation=enable_revalidation
                        )
                    )
                )
                result = future.result(timeout=300)  # 5 minute timeout for batch
        else:
            result = loop.run_until_complete(
                rewrite_requirements_parallel(
                    failed_requirements=failed_requirements,
                    max_concurrent=max_concurrent,
                    max_attempts=max_attempts,
                    target_score=target_score,
                    enable_revalidation=enable_revalidation
                )
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Batch rewrite with feedback failed: {e}")
        return {
            "total_count": len(failed_requirements),
            "rewritten_count": 0,
            "improved_count": 0,
            "unchanged_count": 0,
            "error_count": len(failed_requirements),
            "total_time_ms": 0,
            "details": [],
            "error": str(e)
        }


# Export tools for AutoGen (will be converted to FunctionTool in requirements_agent.py)
VALIDATION_TOOLS = [
    evaluate_requirement,
    rewrite_requirement,
    suggest_improvements,
    detect_duplicates,
    rewrite_with_feedback,
    rewrite_batch_with_feedback,
]

# Alias for lowercase import compatibility
validation_tools = VALIDATION_TOOLS
