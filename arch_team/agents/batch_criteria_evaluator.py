# -*- coding: utf-8 -*-
"""Batch Criteria Evaluator - Single LLM Call for All Criteria

This module provides a fast evaluation approach that evaluates ALL 9 IEEE 29148
criteria in a SINGLE LLM call, reducing API calls from 9 to 1.

Performance improvement: ~9x faster than individual criterion evaluations.

Usage:
    evaluator = BatchCriteriaEvaluator()
    scores = await evaluator.evaluate(requirement_text)
    # Returns: {"atomic": 0.8, "clarity": 0.9, ...}"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# All 9 IEEE 29148 criteria with descriptions
CRITERIA_DEFINITIONS = {
    "atomic": {
        "name": "Atomicity",
        "description": "Requirement expresses a single, testable concern without combining multiple requirements",
        "indicators": ["single concern", "no 'and' or 'or' combining different actions", "can be verified independently"]
    },
    "clarity": {
        "name": "Clarity",
        "description": "Requirement uses clear, unambiguous language that can be understood by all stakeholders",
        "indicators": ["user story format preferred", "active voice", "defined terms", "no jargon without explanation"]
    },
    "testability": {
        "name": "Testability",
        "description": "Requirement can be verified through testing, inspection, or demonstration",
        "indicators": ["measurable outcome", "specific acceptance criteria", "clear pass/fail conditions"]
    },
    "measurability": {
        "name": "Measurability",
        "description": "Requirement includes quantifiable metrics (time, percentage, count)",
        "indicators": ["specific numbers", "time constraints", "performance metrics", "threshold values"]
    },
    "concise": {
        "name": "Conciseness",
        "description": "Requirement is brief (<50 words) while containing all necessary information",
        "indicators": ["<50 words", "no redundancy", "no unnecessary details"]
    },
    "unambiguous": {
        "name": "Unambiguous",
        "description": "Requirement has only one possible interpretation",
        "indicators": ["no vague terms", "no 'etc.'", "no 'as needed'", "specific scope"]
    },
    "consistent_language": {
        "name": "Consistent Language",
        "description": "Requirement uses consistent terminology throughout",
        "indicators": ["same terms for same concepts", "follows project glossary", "consistent capitalization"]
    },
    "design_independent": {
        "name": "Design Independent",
        "description": "Requirement describes WHAT not HOW (no implementation details)",
        "indicators": ["no technology names", "no database/API specifics", "focuses on user need"]
    },
    "purpose_independent": {
        "name": "Purpose Independent",
        "description": "Requirement states the need without business justification mixed in",
        "indicators": ["no 'because'", "no business goals in requirement text", "goal in separate section"]
    }
}

BATCH_EVALUATION_PROMPT = """You are an expert requirements analyst evaluating a software requirement against IEEE 29148 quality criteria.

REQUIREMENT TO EVALUATE:
"{requirement_text}"

Evaluate this requirement against ALL 9 criteria below. For each criterion, provide:
- score: A decimal from 0.0 to 1.0 (0.0 = completely fails, 1.0 = perfectly meets)
- reason: ONE sentence explaining the score

CRITERIA:
1. atomic: Single concern, no combined requirements using "and"/"or"
2. clarity: Clear language, preferably user story format, understood by all stakeholders
3. testability: Can be verified through testing with clear pass/fail conditions
4. measurability: Has quantifiable metrics (time, percentage, count, threshold values)
5. concise: Brief (<50 words) without redundancy
6. unambiguous: Only one possible interpretation, no vague terms
7. consistent_language: Uses consistent terminology
8. design_independent: Describes WHAT not HOW (no technology/implementation details)
9. purpose_independent: States need without business justification mixed in

RESPOND WITH ONLY THIS JSON STRUCTURE (no markdown, no explanation outside JSON):
{{
  "atomic": {{"score": 0.0, "reason": "..."}},
  "clarity": {{"score": 0.0, "reason": "..."}},
  "testability": {{"score": 0.0, "reason": "..."}},
  "measurability": {{"score": 0.0, "reason": "..."}},
  "concise": {{"score": 0.0, "reason": "..."}},
  "unambiguous": {{"score": 0.0, "reason": "..."}},
  "consistent_language": {{"score": 0.0, "reason": "..."}},
  "design_independent": {{"score": 0.0, "reason": "..."}},
  "purpose_independent": {{"score": 0.0, "reason": "..."}}
}}"""


class BatchCriteriaEvaluator:
    """
    Evaluates all 9 IEEE 29148 criteria in a SINGLE LLM call.
    
    This is ~9x faster than evaluating each criterion separately.
    
    Usage:
        evaluator = BatchCriteriaEvaluator()
        result = await evaluator.evaluate("The system must...")
        # result = {"atomic": 0.8, "clarity": 0.9, ...}
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.0
    ):
        """
        Initialize the batch evaluator.

        Args:
            model: LLM model to use (default from settings)
            temperature: LLM temperature (default 0.0 for consistency)
        """
        # Import settings to get model configuration
        from backend.core import settings
        self.model = model or settings.OPENAI_MODEL
        self.temperature = temperature
        self._client = None
        
        logger.info(f"BatchCriteriaEvaluator initialized with model={self.model}")
    
    def _get_client(self):
        """Get or create the LLM client using the same pattern as backend/core/llm.py."""
        if self._client is None:
            try:
                from openai import OpenAI as OpenAIClient
                from backend.core import settings
                
                llm_config = settings.get_llm_config()
                self._client = OpenAIClient(
                    api_key=llm_config["api_key"],
                    base_url=llm_config["base_url"]
                )
                logger.info(f"BatchCriteriaEvaluator connected to {llm_config['base_url']}")
            except Exception as e:
                logger.error(f"Failed to create LLM client: {e}")
                raise
        return self._client
    
    async def evaluate(
        self,
        requirement_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """
        Evaluate a requirement against all 9 criteria in a single LLM call.
        
        Args:
            requirement_text: The requirement text to evaluate
            context: Optional context (not used currently)
        
        Returns:
            Dict mapping criterion name to score (0.0-1.0)
        """
        try:
            client = self._get_client()
            
            prompt = BATCH_EVALUATION_PROMPT.format(
                requirement_text=requirement_text
            )
            
            # Use synchronous call (OpenAI v1 client)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            # Handle potential markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            result = json.loads(content)
            
            # Extract just the scores - FIX: use score_data correctly
            scores = {}
            for criterion in CRITERIA_DEFINITIONS.keys():
                if criterion in result:
                    score_data = result[criterion]
                    if isinstance(score_data, dict):
                        scores[criterion] = float(score_data.get("score", 0.5))
                    else:
                        scores[criterion] = float(score_data)
                else:
                    scores[criterion] = 0.5  # Default neutral score
            
            logger.info(f"Batch evaluation complete: {scores}")
            return scores
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            # Return neutral scores on parse error
            return {criterion: 0.5 for criterion in CRITERIA_DEFINITIONS.keys()}
        except Exception as e:
            logger.error(f"Batch evaluation failed: {e}", exc_info=True)
            # Return neutral scores on error
            return {criterion: 0.5 for criterion in CRITERIA_DEFINITIONS.keys()}
    
    async def evaluate_with_reasons(
        self,
        requirement_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Evaluate a requirement and return scores with reasons.
        
        Args:
            requirement_text: The requirement text to evaluate
            context: Optional context
        
        Returns:
            Dict mapping criterion to {"score": float, "reason": str}
        """
        try:
            client = self._get_client()
            
            prompt = BATCH_EVALUATION_PROMPT.format(
                requirement_text=requirement_text
            )
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Handle potential markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            result = json.loads(content)
            
            # Ensure all criteria are present
            for criterion in CRITERIA_DEFINITIONS.keys():
                if criterion not in result:
                    result[criterion] = {"score": 0.5, "reason": "Not evaluated"}
                elif not isinstance(result[criterion], dict):
                    result[criterion] = {"score": float(result[criterion]), "reason": "Score only"}
            
            return result
            
        except Exception as e:
            logger.error(f"Batch evaluation with reasons failed: {e}", exc_info=True)
            return {
                criterion: {"score": 0.5, "reason": "Evaluation failed"}
                for criterion in CRITERIA_DEFINITIONS.keys()
            }


# Singleton instance for reuse
_evaluator_instance: Optional[BatchCriteriaEvaluator] = None


def get_batch_evaluator() -> BatchCriteriaEvaluator:
    """Get or create the singleton batch evaluator instance."""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = BatchCriteriaEvaluator()
    return _evaluator_instance


__all__ = [
    "BatchCriteriaEvaluator",
    "get_batch_evaluator",
    "CRITERIA_DEFINITIONS"
]