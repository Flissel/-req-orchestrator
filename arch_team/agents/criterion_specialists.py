# -*- coding: utf-8 -*-
"""
Criterion Specialist Agents for Requirements Validation

Each specialist agent handles one quality criterion:
- Evaluates the criterion score (0.0 - 1.0)
- Suggests fixes when score < threshold
- Applies fixes using LLM-based transformation

Usage:
    agent = ClarityAgent()
    score = await agent.evaluate(requirement_text)
    if score < 0.7:
        suggestion = await agent.suggest_fix(requirement_text, score)
        fixed_text = await agent.apply_fix(requirement_text, suggestion)
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core import settings
from backend.core.llm import _make_chat_args, _extract_json_string

# Load criteria config at module level for efficient access
_CRITERIA_CONFIG: Dict[str, Dict[str, Any]] = {}

def _load_criteria_config() -> Dict[str, Dict[str, Any]]:
    """Load criteria configuration from config/criteria.json"""
    global _CRITERIA_CONFIG
    if _CRITERIA_CONFIG:
        return _CRITERIA_CONFIG

    config_path = Path(__file__).parent.parent.parent / "config" / "criteria.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            criteria_list = json.load(f)
        _CRITERIA_CONFIG = {c["key"]: c for c in criteria_list if c.get("active", True)}
    except Exception as e:
        logging.warning(f"Failed to load criteria config: {e}")
        _CRITERIA_CONFIG = {}
    return _CRITERIA_CONFIG

# OpenAI client (v1 API)
try:
    from openai import OpenAI as _OpenAIClient
    OPENAI_AVAILABLE = True
except Exception:
    _OpenAIClient = None
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

# Mock mode flag
MOCK_MODE = os.environ.get("MOCK_MODE", "").lower() in ("1", "true", "yes")


class CriterionSpecialistAgent(ABC):
    """Base class for all criterion specialist agents"""

    # Tier priority order (lower = more important, process first)
    TIER_PRIORITY = {"gating": 1, "priority": 2, "polish": 3}

    def __init__(self, criterion_name: str, description: str, threshold: float = 0.7):
        """
        Initialize criterion specialist agent

        Args:
            criterion_name: Name of the quality criterion (e.g., "clarity", "testability")
            description: Human-readable description of what this agent checks
            threshold: Minimum acceptable score (default: 0.7)
        """
        self.criterion_name = criterion_name
        self.description = description
        self.client: Optional[Any] = None

        # Load criteria config to get tier and threshold from config file
        config = _load_criteria_config()
        criterion_config = config.get(criterion_name, {})
        self.tier = criterion_config.get("tier", "priority")
        self.threshold = criterion_config.get("threshold", threshold)
        self.weight = criterion_config.get("weight", 0.10)
        self.action = criterion_config.get("action", "")
        self.fail_fast = criterion_config.get("failFast", False)

        # Initialize OpenAI client if available
        if OPENAI_AVAILABLE and not MOCK_MODE:
            # Use dynamic provider configuration (supports OpenAI and OpenRouter)
            llm_config = settings.get_llm_config()
            api_key = llm_config.get("api_key", "")
            base_url = llm_config.get("base_url")

            if api_key:
                # Initialize client with OpenRouter configuration
                self.client = _OpenAIClient(
                    api_key=api_key,
                    base_url=base_url
                )
                logger.info(f"{self.__class__.__name__} initialized with OpenRouter API (tier={self.tier}, threshold={self.threshold})")
            else:
                logger.warning(f"{self.__class__.__name__}: OPENROUTER_API_KEY not configured, falling back to mock mode")
        else:
            logger.info(f"{self.__class__.__name__} initialized in mock mode (tier={self.tier})")

    def get_structured_feedback(self, score: float, llm_feedback: str = "") -> Dict[str, Any]:
        """
        Generate structured actionable feedback based on tier and score.

        Args:
            score: The criterion score (0.0 - 1.0)
            llm_feedback: Optional feedback from LLM evaluation

        Returns:
            Structured feedback dict with tier, priority, action, etc.
        """
        passed = score >= self.threshold

        return {
            "criterion": self.criterion_name,
            "tier": self.tier,
            "priority": self.TIER_PRIORITY.get(self.tier, 2),
            "score": score,
            "threshold": self.threshold,
            "passed": passed,
            "feedback": llm_feedback,
            "action": self.action if not passed else "",
            "fail_fast": self.fail_fast and not passed,
            "severity": self._get_severity(score, passed)
        }

    def _get_severity(self, score: float, passed: bool) -> str:
        """Determine severity level based on score and tier"""
        if passed:
            return "ok"
        if self.tier == "gating":
            return "critical" if score < 0.5 else "error"
        elif self.tier == "priority":
            return "warning" if score >= 0.5 else "error"
        else:  # polish
            return "info" if score >= 0.4 else "warning"

    async def evaluate(self, requirement_text: str, context: Optional[Dict[str, Any]] = None) -> float:
        """
        Evaluate the criterion for a requirement

        Args:
            requirement_text: The requirement to evaluate
            context: Optional context (metadata, project info, etc.)

        Returns:
            Score between 0.0 (fails criterion) and 1.0 (perfect)
        """
        if MOCK_MODE or not self.client:
            return self._mock_evaluate(requirement_text, context)

        try:
            system_prompt = self._get_evaluation_prompt()
            user_payload = {
                "requirement": requirement_text,
                "criterion": self.criterion_name,
                "context": context or {}
            }

            chat_args = _make_chat_args(system_prompt, user_payload)
            response = self.client.chat.completions.create(**chat_args)

            content = response.choices[0].message.content or "{}"
            json_str = _extract_json_string(content)
            result = json.loads(json_str)

            score = float(result.get("score", 0.5))
            feedback = result.get("feedback", "")

            logger.debug(f"{self.criterion_name} evaluation: {score:.2f} - {feedback}")
            return max(0.0, min(1.0, score))  # Clamp to [0, 1]

        except Exception as e:
            logger.error(f"Error evaluating {self.criterion_name}: {e}")
            return 0.5  # Neutral score on error

    async def suggest_fix(self, requirement_text: str, score: float, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Suggest how to fix the requirement to improve the criterion score

        Args:
            requirement_text: The requirement text
            score: Current criterion score
            context: Optional context

        Returns:
            Suggestion text explaining what to improve
        """
        if MOCK_MODE or not self.client:
            return self._mock_suggest(requirement_text, score, context)

        try:
            system_prompt = self._get_suggestion_prompt()
            user_payload = {
                "requirement": requirement_text,
                "criterion": self.criterion_name,
                "current_score": score,
                "context": context or {}
            }

            chat_args = _make_chat_args(system_prompt, user_payload)
            response = self.client.chat.completions.create(**chat_args)

            content = response.choices[0].message.content or "{}"
            json_str = _extract_json_string(content)
            result = json.loads(json_str)

            suggestion = result.get("suggestion", "No specific suggestion available")
            logger.debug(f"{self.criterion_name} suggestion: {suggestion[:100]}...")
            return suggestion

        except Exception as e:
            logger.error(f"Error suggesting fix for {self.criterion_name}: {e}")
            return f"Unable to generate suggestion for {self.criterion_name}"

    async def apply_fix(self, requirement_text: str, suggestion: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Apply the suggested fix to generate improved requirement text

        Args:
            requirement_text: Original requirement text
            suggestion: The suggestion from suggest_fix()
            context: Optional context

        Returns:
            Improved requirement text
        """
        if MOCK_MODE or not self.client:
            return self._mock_apply(requirement_text, suggestion, context)

        try:
            system_prompt = self._get_application_prompt()
            user_payload = {
                "requirement": requirement_text,
                "criterion": self.criterion_name,
                "suggestion": suggestion,
                "context": context or {}
            }

            chat_args = _make_chat_args(system_prompt, user_payload)
            response = self.client.chat.completions.create(**chat_args)

            content = response.choices[0].message.content or "{}"
            json_str = _extract_json_string(content)
            result = json.loads(json_str)

            improved_text = result.get("improved_requirement", requirement_text)
            logger.debug(f"{self.criterion_name} applied fix: {improved_text[:100]}...")
            return improved_text

        except Exception as e:
            logger.error(f"Error applying fix for {self.criterion_name}: {e}")
            return requirement_text  # Return original on error

    async def generate_clarifying_questions(
        self,
        requirement_text: str,
        score: float,
        feedback: str = "",
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate clarifying questions when automatic fixing cannot proceed.
        Called when score is below threshold AND automatic fix is not feasible.

        Args:
            requirement_text: The requirement text
            score: Current criterion score
            feedback: LLM feedback explaining why it failed
            context: Optional context

        Returns:
            List of question dicts:
            [
                {
                    "criterion": "clarity",
                    "question": "Who is the intended user/role for this requirement?",
                    "suggested_answers": ["End User", "Administrator", "API Consumer"],
                    "context_hint": "The requirement doesn't specify a clear user role"
                }
            ]
        """
        if MOCK_MODE or not self.client:
            return self._mock_generate_questions(requirement_text, score, context)

        try:
            system_prompt = self._get_clarification_prompt()
            user_payload = {
                "requirement": requirement_text,
                "criterion": self.criterion_name,
                "current_score": score,
                "feedback": feedback,
                "context": context or {}
            }

            chat_args = _make_chat_args(system_prompt, user_payload)
            response = self.client.chat.completions.create(**chat_args)

            content = response.choices[0].message.content or "{}"
            json_str = _extract_json_string(content)
            result = json.loads(json_str)

            questions = result.get("questions", [])
            # Add criterion to each question
            for q in questions:
                q["criterion"] = self.criterion_name

            logger.info(f"{self.criterion_name}: Generated {len(questions)} clarifying question(s)")
            return questions

        except Exception as e:
            logger.error(f"Error generating questions for {self.criterion_name}: {e}")
            # Return a default question based on criterion
            return [{
                "criterion": self.criterion_name,
                "question": f"Please provide more details to improve {self.criterion_name}",
                "suggested_answers": [],
                "context_hint": f"The requirement scored {score:.0%} on {self.criterion_name}"
            }]

    def _get_clarification_prompt(self) -> str:
        """Return the system prompt for generating clarifying questions"""
        return f"""You are a requirements engineering expert specialized in {self.criterion_name}.

The requirement below fails the {self.criterion_name} criterion and cannot be automatically fixed.
Generate 1-2 specific clarifying questions to ask the user for missing information.

Criterion: {self.criterion_name}
Description: {self.description}

Return JSON:
{{
  "questions": [
    {{
      "question": "Specific question in German (user's language)",
      "suggested_answers": ["option1", "option2", "option3"],
      "context_hint": "Brief explanation of what triggered this question"
    }}
  ]
}}

Keep questions focused on getting the SPECIFIC missing information needed to fix the {self.criterion_name} issue."""

    def _mock_generate_questions(
        self,
        requirement_text: str,
        score: float,
        context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Default mock question generation - subclasses can override for better mocks"""
        return [{
            "criterion": self.criterion_name,
            "question": f"Bitte geben Sie mehr Details an, um {self.criterion_name} zu verbessern.",
            "suggested_answers": [],
            "context_hint": f"Score: {score:.0%} - unter Schwellenwert {self.threshold:.0%}"
        }]

    # Abstract methods for subclasses to implement

    @abstractmethod
    def _get_evaluation_prompt(self) -> str:
        """Return the system prompt for evaluation"""
        pass

    @abstractmethod
    def _get_suggestion_prompt(self) -> str:
        """Return the system prompt for suggesting fixes"""
        pass

    @abstractmethod
    def _get_application_prompt(self) -> str:
        """Return the system prompt for applying fixes"""
        pass

    @abstractmethod
    def _mock_evaluate(self, requirement_text: str, context: Optional[Dict[str, Any]]) -> float:
        """Mock evaluation for testing without API"""
        pass

    @abstractmethod
    def _mock_suggest(self, requirement_text: str, score: float, context: Optional[Dict[str, Any]]) -> str:
        """Mock suggestion for testing without API"""
        pass

    @abstractmethod
    def _mock_apply(self, requirement_text: str, suggestion: str, context: Optional[Dict[str, Any]]) -> str:
        """Mock application for testing without API"""
        pass


# ============================================================================
# CLARITY AGENT - Ensures clear, unambiguous wording with user story format
# ============================================================================

class ClarityAgent(CriterionSpecialistAgent):
    """Ensures requirements are clearly formulated using user story format (ISO 29148)"""

    def __init__(self):
        super().__init__(
            criterion_name="clarity",
            description="Checks if requirement uses clear, unambiguous language with user story format"
        )

    def _get_evaluation_prompt(self) -> str:
        return """You are a requirements clarity expert. Evaluate if the requirement is clearly formulated.

Criteria:
- Uses user story format: "As a [role], I want [feature] so that [benefit]"
- No ambiguous terms like "schnell", "benutzerfreundlich", "skalierbar" without definition
- Specific and concrete language
- No jargon without explanation

Return JSON:
{
  "score": 0.0-1.0,
  "feedback": "Brief explanation of clarity issues or strengths"
}"""

    def _get_suggestion_prompt(self) -> str:
        return """You are a requirements clarity expert. Suggest how to improve clarity.

Focus on:
- Converting to user story format if missing
- Replacing vague terms with specific ones
- Adding role, action, and benefit
- Removing ambiguity

Return JSON:
{
  "suggestion": "Specific actionable advice to improve clarity"
}"""

    def _get_application_prompt(self) -> str:
        return """You are a requirements clarity expert. Rewrite the requirement to improve clarity.

Apply the suggestion to:
- Use user story format: "As a [role], I want [feature] so that [benefit]"
- Replace vague terms with specific ones
- Make language concrete and unambiguous
- Preserve original intent

Return JSON:
{
  "improved_requirement": "The rewritten requirement text"
}"""

    def _mock_evaluate(self, requirement_text: str, context: Optional[Dict[str, Any]]) -> float:
        text = requirement_text.lower()
        has_user_story = "as a" in text or "als" in text
        has_vague_terms = any(term in text for term in ["schnell", "gut", "benutzerfreundlich", "skalierbar"])
        length = len(requirement_text.split())

        score = 0.5
        if has_user_story:
            score += 0.3
        if not has_vague_terms:
            score += 0.2
        if 10 <= length <= 30:
            score += 0.1

        return min(1.0, score)

    def _mock_suggest(self, requirement_text: str, score: float, context: Optional[Dict[str, Any]]) -> str:
        return "Convert to user story format: 'As a [role], I want [feature] so that [benefit]' and replace vague terms with specific metrics"

    def _mock_apply(self, requirement_text: str, suggestion: str, context: Optional[Dict[str, Any]]) -> str:
        # Simple mock: prepend user story format
        if "as a" not in requirement_text.lower() and "als" not in requirement_text.lower():
            return f"As a user, I want {requirement_text.lower()} so that I can use the system effectively"
        return requirement_text

    def _mock_generate_questions(
        self,
        requirement_text: str,
        score: float,
        context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate clarity-specific mock questions"""
        questions = []
        text = requirement_text.lower()

        if "as a" not in text and "als" not in text:
            questions.append({
                "criterion": "clarity",
                "question": "Wer ist der primäre Benutzer/Akteur für diese Anforderung?",
                "suggested_answers": ["Endbenutzer", "Administrator", "Systemintegrator", "API-Konsument"],
                "context_hint": "Die Anforderung spezifiziert keine klare Benutzerrolle"
            })

        if not questions:
            questions.append({
                "criterion": "clarity",
                "question": "Können Sie das gewünschte Verhalten genauer beschreiben?",
                "suggested_answers": [],
                "context_hint": f"Die Anforderung ist zu vage formuliert (Score: {score:.0%})"
            })

        return questions[:2]


# ============================================================================
# TESTABILITY AGENT - Ensures acceptance criteria are defined
# ============================================================================

class TestabilityAgent(CriterionSpecialistAgent):
    """Ensures requirements have testable acceptance criteria (Given-When-Then)"""

    def __init__(self):
        super().__init__(
            criterion_name="testability",
            description="Checks if requirement has clear, testable acceptance criteria"
        )

    def _get_evaluation_prompt(self) -> str:
        return """You are a requirements testability expert. Evaluate if the requirement is testable.

Criteria:
- Has acceptance criteria in Given-When-Then format
- Clear pass/fail conditions
- Verifiable outcomes
- No untestable statements like "user-friendly" or "fast"

Return JSON:
{
  "score": 0.0-1.0,
  "feedback": "Brief explanation of testability issues or strengths"
}"""

    def _get_suggestion_prompt(self) -> str:
        return """You are a requirements testability expert. Suggest how to add testability.

Focus on:
- Adding Given-When-Then acceptance criteria
- Defining clear pass/fail conditions
- Making outcomes verifiable
- Removing untestable language

Return JSON:
{
  "suggestion": "Specific actionable advice to improve testability"
}"""

    def _get_application_prompt(self) -> str:
        return """You are a requirements testability expert. Rewrite the requirement to add testability.

Apply the suggestion to:
- Add Given-When-Then acceptance criteria
- Define clear pass/fail conditions
- Make outcomes verifiable
- Preserve original intent

Return JSON:
{
  "improved_requirement": "The requirement with added acceptance criteria"
}"""

    def _mock_evaluate(self, requirement_text: str, context: Optional[Dict[str, Any]]) -> float:
        text = requirement_text.lower()
        has_criteria = any(keyword in text for keyword in ["given", "when", "then", "accept", "kriterium"])
        has_untestable = any(term in text for term in ["benutzerfreundlich", "intuitiv", "elegant"])
        has_numbers = any(char.isdigit() for char in text)

        score = 0.5
        if has_criteria:
            score += 0.3
        if not has_untestable:
            score += 0.1
        if has_numbers:
            score += 0.1

        return min(1.0, score)

    def _mock_suggest(self, requirement_text: str, score: float, context: Optional[Dict[str, Any]]) -> str:
        return "Add acceptance criteria: Given [precondition], When [action], Then [expected result]"

    def _mock_apply(self, requirement_text: str, suggestion: str, context: Optional[Dict[str, Any]]) -> str:
        # Simple mock: append acceptance criteria
        if "given" not in requirement_text.lower():
            return f"{requirement_text}\n\nAcceptance Criteria:\n- Given the system is operational\n- When the user performs the action\n- Then the expected result occurs"
        return requirement_text

    def _mock_generate_questions(
        self,
        requirement_text: str,
        score: float,
        context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate testability-specific mock questions"""
        questions = []
        text = requirement_text.lower()

        # Check for acceptance criteria
        if not any(term in text for term in ["given", "when", "then", "akzeptanz", "kriterium"]):
            questions.append({
                "criterion": "testability",
                "question": "Wie kann diese Anforderung verifiziert werden? Was sind die Akzeptanzkriterien?",
                "suggested_answers": [],
                "context_hint": "Die Anforderung enthält keine testbaren Akzeptanzkriterien"
            })

        # Check for untestable qualitative terms
        if any(term in text for term in ["benutzerfreundlich", "intuitiv", "elegant", "einfach"]):
            questions.append({
                "criterion": "testability",
                "question": "Wie können wir 'benutzerfreundlich' messen? Welche konkreten Testfälle gelten?",
                "suggested_answers": [
                    "Aufgabe in < 3 Schritten erledigt",
                    "Fehlerrate < 5%",
                    "Benutzer braucht keine Anleitung"
                ],
                "context_hint": "Qualitative Begriffe wie 'benutzerfreundlich' sind nicht direkt testbar"
            })

        # Default question
        if not questions:
            questions.append({
                "criterion": "testability",
                "question": "Bitte beschreiben Sie einen konkreten Testfall für diese Anforderung (Given-When-Then)",
                "suggested_answers": [],
                "context_hint": f"Die Anforderung ist nicht ausreichend testbar (Score: {score:.0%})"
            })

        return questions[:2]


# ============================================================================
# MEASURABILITY AGENT - Ensures quantifiable metrics are defined
# ============================================================================

class MeasurabilityAgent(CriterionSpecialistAgent):
    """Ensures requirements have quantifiable metrics with units"""

    def __init__(self):
        super().__init__(
            criterion_name="measurability",
            description="Checks if requirement has quantifiable metrics (numbers, units, thresholds)"
        )

    def _get_evaluation_prompt(self) -> str:
        return """You are a requirements measurability expert. Evaluate if the requirement is measurable.

Criteria:
- Contains numeric thresholds (e.g., "< 200ms", ">= 95%", "1000 users")
- Has units of measurement (ms, %, users, requests/sec)
- Defines quantifiable success criteria
- No unmeasurable terms like "fast", "scalable" without metrics

Return JSON:
{
  "score": 0.0-1.0,
  "feedback": "Brief explanation of measurability issues or strengths"
}"""

    def _get_suggestion_prompt(self) -> str:
        return """You are a requirements measurability expert. Suggest how to add measurability.

Focus on:
- Adding numeric thresholds
- Defining units of measurement
- Converting vague terms to metrics (e.g., "fast" → "< 200ms response time")
- Specifying quantifiable success criteria

Return JSON:
{
  "suggestion": "Specific actionable advice to improve measurability"
}"""

    def _get_application_prompt(self) -> str:
        return """You are a requirements measurability expert. Rewrite the requirement to add measurability.

Apply the suggestion to:
- Add numeric thresholds with units
- Convert vague terms to specific metrics
- Define quantifiable success criteria
- Preserve original intent

Return JSON:
{
  "improved_requirement": "The requirement with added metrics"
}"""

    def _mock_evaluate(self, requirement_text: str, context: Optional[Dict[str, Any]]) -> float:
        text = requirement_text.lower()
        has_numbers = any(char.isdigit() for char in text)
        has_units = any(unit in text for unit in ["ms", "s", "sekunde", "%", "prozent", "users", "requests"])
        has_vague = any(term in text for term in ["schnell", "langsam", "viel", "wenig", "skalierbar"])

        score = 0.3
        if has_numbers:
            score += 0.3
        if has_units:
            score += 0.3
        if not has_vague:
            score += 0.1

        return min(1.0, score)

    def _mock_suggest(self, requirement_text: str, score: float, context: Optional[Dict[str, Any]]) -> str:
        return "Add quantifiable metrics: Replace vague terms with numbers and units (e.g., '< 200ms response time', '>= 95% uptime')"

    def _mock_apply(self, requirement_text: str, suggestion: str, context: Optional[Dict[str, Any]]) -> str:
        # Simple mock: append metric
        text = requirement_text
        if "schnell" in text.lower():
            text = text.replace("schnell", "with response time < 200ms")
        elif "skalierbar" in text.lower():
            text = text.replace("skalierbar", "handling >= 1000 concurrent users")
        return text

    def _mock_generate_questions(
        self,
        requirement_text: str,
        score: float,
        context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate measurability-specific mock questions"""
        questions = []
        text = requirement_text.lower()

        # Check for vague performance terms
        if any(term in text for term in ["schnell", "fast", "quick", "performant"]):
            questions.append({
                "criterion": "measurability",
                "question": "Welche Antwortzeit ist akzeptabel?",
                "suggested_answers": ["< 100ms", "< 200ms", "< 500ms", "< 1 Sekunde"],
                "context_hint": "Die Anforderung erwähnt Geschwindigkeit ohne konkreten Zielwert"
            })

        if any(term in text for term in ["skalierbar", "scalable", "viele"]):
            questions.append({
                "criterion": "measurability",
                "question": "Wie viele gleichzeitige Benutzer sollen unterstützt werden?",
                "suggested_answers": ["100", "1.000", "10.000", "100.000"],
                "context_hint": "Die Anforderung erwähnt Skalierbarkeit ohne konkreten Zielwert"
            })

        if any(term in text for term in ["verfügbar", "available", "uptime"]):
            questions.append({
                "criterion": "measurability",
                "question": "Welche Verfügbarkeit wird erwartet?",
                "suggested_answers": ["95%", "99%", "99.9%", "99.99%"],
                "context_hint": "Die Anforderung erwähnt Verfügbarkeit ohne konkreten SLA"
            })

        # Default if no specific pattern matched
        if not questions:
            questions.append({
                "criterion": "measurability",
                "question": "Welche quantifizierbaren Erfolgskriterien gelten für diese Anforderung?",
                "suggested_answers": [],
                "context_hint": f"Die Anforderung enthält keine messbaren Metriken (Score: {score:.0%})"
            })

        return questions[:2]


# ============================================================================
# ATOMICITY AGENT - Wrapper around existing RequirementsAtomicityAgent
# ============================================================================

class AtomicityAgent(CriterionSpecialistAgent):
    """
    Ensures requirements contain only one testable statement.
    Delegates to existing RequirementsAtomicityAgent for splitting logic.
    """

    def __init__(self):
        super().__init__(
            criterion_name="atomic",
            description="Checks if requirement contains exactly one testable statement (no AND/OR)"
        )

    def _get_evaluation_prompt(self) -> str:
        return """You are a requirements atomicity expert. Evaluate if the requirement is atomic.

Criteria:
- Contains ONLY ONE testable statement
- No compound requirements (joined by AND/OR/comma)
- Single, focused concern
- Can be tested independently

Return JSON:
{
  "score": 0.0-1.0,
  "feedback": "Brief explanation if requirement should be split"
}"""

    def _get_suggestion_prompt(self) -> str:
        return """You are a requirements atomicity expert. Suggest how to split the requirement.

If the requirement contains multiple statements:
- Identify each atomic sub-requirement
- Explain why it should be split
- Suggest individual requirements

Return JSON:
{
  "suggestion": "Explanation of why to split and how many sub-requirements"
}"""

    def _get_application_prompt(self) -> str:
        # Note: Actual splitting is handled by RequirementsAtomicityAgent
        return """You are a requirements atomicity expert. This agent does NOT perform splitting.

Return JSON:
{
  "improved_requirement": "<SPLIT_REQUIRED>"
}

The orchestrator will use RequirementsAtomicityAgent from backend.core.agents for actual splitting."""

    def _mock_evaluate(self, requirement_text: str, context: Optional[Dict[str, Any]]) -> float:
        text = requirement_text.lower()
        compound_indicators = [" and ", " und ", " or ", " oder ", ","]
        has_compound = any(indicator in text for indicator in compound_indicators)

        # Count sentences
        sentence_count = text.count(".") + text.count("!") + text.count("?") + 1

        if has_compound or sentence_count > 2:
            return 0.4  # Not atomic
        return 0.9  # Likely atomic

    def _mock_suggest(self, requirement_text: str, score: float, context: Optional[Dict[str, Any]]) -> str:
        return "Requirement contains multiple statements. Split into separate atomic requirements."

    def _mock_apply(self, requirement_text: str, suggestion: str, context: Optional[Dict[str, Any]]) -> str:
        # Signal that splitting is required
        return "<SPLIT_REQUIRED>"


# ============================================================================
# REMAINING CRITERION AGENTS - Conciseness, Unambiguous, etc.
# ============================================================================

class ConcisenessAgent(CriterionSpecialistAgent):
    """Ensures requirements are concise (10-30 words, no redundancy)"""

    def __init__(self):
        super().__init__(
            criterion_name="concise",
            description="Checks if requirement is concise without redundancy"
        )

    def _get_evaluation_prompt(self) -> str:
        return """You are a requirements conciseness expert. Evaluate if the requirement is concise.

Criteria:
- 10-30 words (optimal length)
- No redundant phrases
- No unnecessary details
- Direct and to the point

Return JSON:
{
  "score": 0.0-1.0,
  "feedback": "Brief explanation of conciseness issues"
}"""

    def _get_suggestion_prompt(self) -> str:
        return """You are a requirements conciseness expert. Suggest how to make it more concise.

Focus on:
- Removing redundant phrases
- Eliminating unnecessary words
- Keeping only essential information
- Target 10-30 words

Return JSON:
{
  "suggestion": "Specific advice to improve conciseness"
}"""

    def _get_application_prompt(self) -> str:
        return """You are a requirements conciseness expert. Rewrite to be more concise.

Apply the suggestion to:
- Remove redundancy
- Eliminate unnecessary words
- Keep essential meaning
- Preserve original intent

Return JSON:
{
  "improved_requirement": "The concise requirement text"
}"""

    def _mock_evaluate(self, requirement_text: str, context: Optional[Dict[str, Any]]) -> float:
        word_count = len(requirement_text.split())
        if 10 <= word_count <= 30:
            return 0.9
        elif word_count < 10:
            return 0.6  # Too brief
        else:
            return max(0.3, 1.0 - (word_count - 30) * 0.01)  # Penalty for length

    def _mock_suggest(self, requirement_text: str, score: float, context: Optional[Dict[str, Any]]) -> str:
        word_count = len(requirement_text.split())
        if word_count > 30:
            return f"Reduce from {word_count} to 10-30 words by removing redundancy"
        return "Add more specific details to reach optimal length"

    def _mock_apply(self, requirement_text: str, suggestion: str, context: Optional[Dict[str, Any]]) -> str:
        words = requirement_text.split()
        if len(words) > 30:
            return " ".join(words[:30]) + "..."  # Truncate
        return requirement_text


class UnambiguousAgent(CriterionSpecialistAgent):
    """Ensures requirements have only one valid interpretation"""

    def __init__(self):
        super().__init__(
            criterion_name="unambiguous",
            description="Checks if requirement has only one valid interpretation"
        )

    def _get_evaluation_prompt(self) -> str:
        return """You are a requirements ambiguity expert. Evaluate if the requirement is unambiguous.

Criteria:
- Only one valid interpretation possible
- No vague pronouns (it, this, that) without clear reference
- No ambiguous quantifiers (some, many, few)
- Clear subject, action, object

Return JSON:
{
  "score": 0.0-1.0,
  "feedback": "Brief explanation of ambiguity issues"
}"""

    def _get_suggestion_prompt(self) -> str:
        return """You are a requirements ambiguity expert. Suggest how to remove ambiguity.

Focus on:
- Clarifying vague pronouns
- Replacing ambiguous quantifiers with specific numbers
- Making subject and object explicit
- Ensuring single interpretation

Return JSON:
{
  "suggestion": "Specific advice to remove ambiguity"
}"""

    def _get_application_prompt(self) -> str:
        return """You are a requirements ambiguity expert. Rewrite to remove ambiguity.

Apply the suggestion to:
- Clarify vague references
- Make quantifiers specific
- Ensure single interpretation
- Preserve original intent

Return JSON:
{
  "improved_requirement": "The unambiguous requirement text"
}"""

    def _mock_evaluate(self, requirement_text: str, context: Optional[Dict[str, Any]]) -> float:
        text = requirement_text.lower()
        vague_pronouns = ["it", "this", "that", "es", "dies", "das"]
        ambiguous_quantifiers = ["some", "many", "few", "einige", "viele", "wenige"]

        has_vague = any(f" {pron} " in f" {text} " for pron in vague_pronouns)
        has_ambiguous = any(quant in text for quant in ambiguous_quantifiers)

        score = 0.8
        if has_vague:
            score -= 0.2
        if has_ambiguous:
            score -= 0.2

        return max(0.3, score)

    def _mock_suggest(self, requirement_text: str, score: float, context: Optional[Dict[str, Any]]) -> str:
        return "Replace vague pronouns with explicit nouns and ambiguous quantifiers with specific numbers"

    def _mock_apply(self, requirement_text: str, suggestion: str, context: Optional[Dict[str, Any]]) -> str:
        # Simple mock: replace common vague terms
        text = requirement_text
        replacements = {
            " it ": " the system ",
            " this ": " the feature ",
            " some ": " at least 3 ",
            " many ": " more than 10 "
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text


class ConsistentLanguageAgent(CriterionSpecialistAgent):
    """Ensures consistent terminology throughout the requirement"""

    def __init__(self):
        super().__init__(
            criterion_name="consistent_language",
            description="Checks if requirement uses consistent terminology"
        )

    def _get_evaluation_prompt(self) -> str:
        return """You are a requirements language consistency expert. Evaluate terminology consistency.

Criteria:
- Same terms used for same concepts
- No synonyms for key entities (User vs. Nutzer, System vs. App)
- Consistent verb tense
- Consistent modal verbs (must vs. should vs. may)

Return JSON:
{
  "score": 0.0-1.0,
  "feedback": "Brief explanation of consistency issues"
}"""

    def _get_suggestion_prompt(self) -> str:
        return """You are a requirements language consistency expert. Suggest how to improve consistency.

Focus on:
- Standardizing terminology
- Using consistent verb tense
- Using consistent modal verbs (must, should, may)
- Aligning with project glossary

Return JSON:
{
  "suggestion": "Specific advice to improve language consistency"
}"""

    def _get_application_prompt(self) -> str:
        return """You are a requirements language consistency expert. Rewrite for consistency.

Apply the suggestion to:
- Standardize terminology
- Use consistent verb tense
- Use consistent modal verbs
- Preserve original intent

Return JSON:
{
  "improved_requirement": "The requirement with consistent language"
}"""

    def _mock_evaluate(self, requirement_text: str, context: Optional[Dict[str, Any]]) -> float:
        # Check for common inconsistencies
        text = requirement_text.lower()
        has_mixed_modals = sum([text.count(modal) for modal in ["must", "should", "may", "muss", "soll", "kann"]]) > 1

        score = 0.8
        if has_mixed_modals:
            score -= 0.2

        return max(0.5, score)

    def _mock_suggest(self, requirement_text: str, score: float, context: Optional[Dict[str, Any]]) -> str:
        return "Use consistent terminology and modal verbs throughout the requirement"

    def _mock_apply(self, requirement_text: str, suggestion: str, context: Optional[Dict[str, Any]]) -> str:
        # Simple mock: standardize to "must"
        text = requirement_text
        text = text.replace("should", "must").replace("soll", "muss")
        return text


class DesignIndependentAgent(CriterionSpecialistAgent):
    """Ensures requirement specifies WHAT, not HOW (implementation-independent)"""

    def __init__(self):
        super().__init__(
            criterion_name="design_independent",
            description="Checks if requirement specifies WHAT, not HOW"
        )

    def _get_evaluation_prompt(self) -> str:
        return """You are a requirements design independence expert. Evaluate if requirement is implementation-independent.

Criteria:
- Specifies WHAT (desired outcome), not HOW (implementation)
- No UI details (button, dropdown, modal)
- No technology stack (React, SQL, REST)
- No architecture decisions
- Focuses on user needs and business value

Return JSON:
{
  "score": 0.0-1.0,
  "feedback": "Brief explanation of design dependency issues"
}"""

    def _get_suggestion_prompt(self) -> str:
        return """You are a requirements design independence expert. Suggest how to remove implementation details.

Focus on:
- Converting HOW to WHAT
- Removing UI implementation details
- Removing technology references
- Focusing on user needs and outcomes

Return JSON:
{
  "suggestion": "Specific advice to make requirement design-independent"
}"""

    def _get_application_prompt(self) -> str:
        return """You are a requirements design independence expert. Rewrite to remove implementation details.

Apply the suggestion to:
- Convert HOW to WHAT
- Remove UI/tech details
- Focus on desired outcome
- Preserve original intent

Return JSON:
{
  "improved_requirement": "The design-independent requirement"
}"""

    def _mock_evaluate(self, requirement_text: str, context: Optional[Dict[str, Any]]) -> float:
        text = requirement_text.lower()
        impl_keywords = ["button", "dropdown", "modal", "react", "sql", "rest", "api", "database", "table"]
        has_impl = any(keyword in text for keyword in impl_keywords)

        score = 0.8
        if has_impl:
            score = 0.4

        return score

    def _mock_suggest(self, requirement_text: str, score: float, context: Optional[Dict[str, Any]]) -> str:
        return "Remove implementation details (UI elements, technologies). Focus on WHAT the user needs, not HOW to build it"

    def _mock_apply(self, requirement_text: str, suggestion: str, context: Optional[Dict[str, Any]]) -> str:
        # Simple mock: remove common implementation keywords
        text = requirement_text
        impl_keywords = ["button", "dropdown", "modal", "via REST API", "in the database"]
        for keyword in impl_keywords:
            text = text.replace(keyword, "interface")
        return text


class PurposeIndependentAgent(CriterionSpecialistAgent):
    """Ensures requirement focuses on single business purpose"""

    def __init__(self):
        super().__init__(
            criterion_name="purpose_independent",
            description="Checks if requirement focuses on single, clear business purpose"
        )

    def _get_evaluation_prompt(self) -> str:
        return """You are a requirements purpose clarity expert. Evaluate if requirement has clear, single purpose.

Criteria:
- Single, focused business purpose
- No mixed concerns (security AND performance)
- Clear rationale/benefit
- Aligns with user/business goal

Return JSON:
{
  "score": 0.0-1.0,
  "feedback": "Brief explanation of purpose clarity"
}"""

    def _get_suggestion_prompt(self) -> str:
        return """You are a requirements purpose clarity expert. Suggest how to clarify purpose.

Focus on:
- Identifying the primary business purpose
- Separating mixed concerns
- Making rationale explicit
- Connecting to user/business value

Return JSON:
{
  "suggestion": "Specific advice to clarify purpose"
}"""

    def _get_application_prompt(self) -> str:
        return """You are a requirements purpose clarity expert. Rewrite to clarify purpose.

Apply the suggestion to:
- Focus on single business purpose
- Make rationale explicit
- Connect to user/business value
- Preserve original intent

Return JSON:
{
  "improved_requirement": "The requirement with clear purpose"
}"""

    def _mock_evaluate(self, requirement_text: str, context: Optional[Dict[str, Any]]) -> float:
        text = requirement_text.lower()
        has_benefit = any(marker in text for marker in ["so that", "damit", "because", "weil"])
        mixed_concerns = sum([text.count(conj) for conj in [" and ", " und ", " or ", " oder "]]) > 1

        score = 0.6
        if has_benefit:
            score += 0.2
        if not mixed_concerns:
            score += 0.2

        return score

    def _mock_suggest(self, requirement_text: str, score: float, context: Optional[Dict[str, Any]]) -> str:
        return "Clarify the single business purpose and add explicit rationale using 'so that [benefit]'"

    def _mock_apply(self, requirement_text: str, suggestion: str, context: Optional[Dict[str, Any]]) -> str:
        # Simple mock: append benefit clause if missing
        if "so that" not in requirement_text.lower() and "damit" not in requirement_text.lower():
            return f"{requirement_text} so that users can achieve their business goals"
        return requirement_text


# ============================================================================
# FACTORY FUNCTION - Get all specialist agents
# ============================================================================

def get_all_specialists() -> List[CriterionSpecialistAgent]:
    """
    Get instances of all criterion specialist agents

    Returns:
        List of all 9 specialist agents
    """
    return [
        ClarityAgent(),
        TestabilityAgent(),
        MeasurabilityAgent(),
        AtomicityAgent(),
        ConcisenessAgent(),
        UnambiguousAgent(),
        ConsistentLanguageAgent(),
        DesignIndependentAgent(),
        PurposeIndependentAgent()
    ]


def get_specialist_by_criterion(criterion_name: str) -> Optional[CriterionSpecialistAgent]:
    """
    Get a specialist agent by criterion name

    Args:
        criterion_name: Name of the criterion (e.g., "clarity", "testability")

    Returns:
        The specialist agent or None if not found
    """
    specialists = get_all_specialists()
    for specialist in specialists:
        if specialist.criterion_name == criterion_name:
            return specialist
    return None


def get_prioritized_feedback(evaluation_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate prioritized actionable feedback from evaluation results.

    Sorts feedback by:
    1. Tier priority (gating first, then priority, then polish)
    2. Within tier, by severity (critical > error > warning > info)
    3. Within severity, by score (lowest first - most urgent)

    Args:
        evaluation_results: List of evaluation dicts with criterion, score, feedback, passed

    Returns:
        List of structured feedback dicts sorted by priority
    """
    specialists = {s.criterion_name: s for s in get_all_specialists()}
    feedback_list = []

    for result in evaluation_results:
        criterion = result.get("criterion", "")
        score = result.get("score", 0.5)
        llm_feedback = result.get("feedback", result.get("reason", ""))

        specialist = specialists.get(criterion)
        if specialist:
            structured = specialist.get_structured_feedback(score, llm_feedback)
            feedback_list.append(structured)
        else:
            # Fallback for unknown criteria
            config = _load_criteria_config().get(criterion, {})
            threshold = config.get("threshold", 0.70)
            tier = config.get("tier", "priority")
            action = config.get("action", "")
            passed = score >= threshold

            feedback_list.append({
                "criterion": criterion,
                "tier": tier,
                "priority": CriterionSpecialistAgent.TIER_PRIORITY.get(tier, 2),
                "score": score,
                "threshold": threshold,
                "passed": passed,
                "feedback": llm_feedback,
                "action": action if not passed else "",
                "fail_fast": False,
                "severity": "warning" if not passed else "ok"
            })

    # Sort by: tier priority ASC, then severity order, then score ASC (lowest first)
    severity_order = {"critical": 0, "error": 1, "warning": 2, "info": 3, "ok": 4}
    feedback_list.sort(key=lambda x: (
        x.get("priority", 2),
        severity_order.get(x.get("severity", "ok"), 4),
        x.get("score", 1.0)
    ))

    return feedback_list


def generate_action_plan(evaluation_results: List[Dict[str, Any]], max_actions: int = 5) -> Dict[str, Any]:
    """
    Generate a prioritized action plan from evaluation results.

    Returns an action plan with:
    - Overall status (pass/fail with gating criteria check)
    - Prioritized list of actions to take
    - Summary statistics

    Args:
        evaluation_results: List of evaluation dicts
        max_actions: Maximum number of actions to include in plan

    Returns:
        Action plan dict
    """
    prioritized = get_prioritized_feedback(evaluation_results)

    # Check gating criteria
    gating_failed = [f for f in prioritized if f["tier"] == "gating" and not f["passed"]]
    priority_failed = [f for f in prioritized if f["tier"] == "priority" and not f["passed"]]
    polish_failed = [f for f in prioritized if f["tier"] == "polish" and not f["passed"]]

    # Determine overall status
    if gating_failed:
        overall_status = "blocked"
        status_message = f"BLOCKED: {len(gating_failed)} gating criteria failed. Must fix before proceeding."
    elif priority_failed:
        overall_status = "needs_improvement"
        status_message = f"NEEDS WORK: {len(priority_failed)} priority criteria failed."
    elif polish_failed:
        overall_status = "polish"
        status_message = f"POLISH: {len(polish_failed)} polish criteria need attention."
    else:
        overall_status = "pass"
        status_message = "All criteria passed. Ready for release."

    # Build action list (only failed criteria)
    failed_feedback = [f for f in prioritized if not f["passed"]]
    actions = []

    for fb in failed_feedback[:max_actions]:
        actions.append({
            "step": len(actions) + 1,
            "criterion": fb["criterion"],
            "tier": fb["tier"],
            "severity": fb["severity"],
            "action": fb["action"],
            "current_score": f"{fb['score']*100:.0f}%",
            "target": f">= {fb['threshold']*100:.0f}%"
        })

    return {
        "status": overall_status,
        "message": status_message,
        "statistics": {
            "total_criteria": len(prioritized),
            "passed": len([f for f in prioritized if f["passed"]]),
            "failed": len(failed_feedback),
            "gating_failed": len(gating_failed),
            "priority_failed": len(priority_failed),
            "polish_failed": len(polish_failed)
        },
        "actions": actions,
        "all_feedback": prioritized
    }
