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

# API Base URL (from arch_team.service or backend_app_v2)
API_BASE = os.environ.get("VALIDATION_API_BASE", "http://localhost:8087")


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
            "criteria_keys": criteria_keys or ["clarity", "testability", "measurability"]
        }

        logger.info(f"Evaluating requirement via {url}")
        response = requests.post(url, json=payload, timeout=30)
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


# Export tools for AutoGen (will be converted to FunctionTool in requirements_agent.py)
VALIDATION_TOOLS = [
    evaluate_requirement,
    rewrite_requirement,
    suggest_improvements,
    detect_duplicates,
]
