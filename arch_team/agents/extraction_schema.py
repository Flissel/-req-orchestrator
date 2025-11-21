"""
OpenAI Function Calling Schema for Requirements Extraction

This module defines the structured output schema for requirement extraction
using OpenAI's function calling feature to ensure high-quality, validated output.
"""

REQUIREMENT_EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_requirements",
        "description": "Submit extracted requirements from the document chunk with structured metadata",
        "parameters": {
            "type": "object",
            "properties": {
                "requirements": {
                    "type": "array",
                    "description": "List of extracted requirements from the text",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": (
                                    "Complete requirement statement that MUST start with a subject and modal verb. "
                                    "Use 'must' for mandatory requirements, 'should' for recommended, 'may' for optional. "
                                    "Examples: "
                                    "'The system must authenticate users within 2 seconds', "
                                    "'The overlay shall remain click-through on all monitors', "
                                    "'The application should provide visual feedback for all user actions'. "
                                    "NEVER use imperative form without subject (e.g., 'Render overlay' is INCORRECT)"
                                )
                            },
                            "tag": {
                                "type": "string",
                                "enum": [
                                    "functional",
                                    "performance",
                                    "security",
                                    "usability",
                                    "reliability",
                                    "compliance",
                                    "interface",
                                    "data",
                                    "constraint"
                                ],
                                "description": "Primary category of the requirement"
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["must", "should", "may"],
                                "description": (
                                    "RFC 2119 priority level derived from the modal verb in the requirement. "
                                    "must/shall = mandatory, should = recommended, may/can = optional"
                                )
                            },
                            "measurable_criteria": {
                                "type": "string",
                                "description": (
                                    "Specific, testable acceptance criteria extracted from the requirement. "
                                    "Examples: 'response time < 2 seconds', 'uptime >= 99.9%', "
                                    "'supports 1000 concurrent users', 'AES-256 encryption'. "
                                    "Leave empty if no specific criteria mentioned."
                                )
                            },
                            "actors": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "List of actors/entities that interact with or are affected by this requirement. "
                                    "Examples: ['user', 'admin', 'system', 'database', 'external API']. "
                                    "Can be empty if no specific actors mentioned."
                                )
                            },
                            "evidence": {
                                "type": "string",
                                "description": (
                                    "Direct quote or paraphrase from the source document that supports this requirement. "
                                    "This helps trace the requirement back to original text."
                                )
                            }
                        },
                        "required": ["title", "tag", "priority"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["requirements"],
            "additionalProperties": False
        }
    }
}

# System prompt for extraction with tool calling
EXTRACTION_SYSTEM_PROMPT = """You are a requirements extraction specialist with expertise in software requirements engineering.

Your task is to extract high-quality, well-formed requirements from technical documents.

CRITICAL RULES:
1. **Modal Verbs**: Every requirement MUST start with a subject (system/application/user/etc.) followed by a modal verb (must/shall/should/may)
   ✓ CORRECT: "The system must authenticate users within 2 seconds"
   ✗ INCORRECT: "Authenticate users within 2 seconds"
   ✗ INCORRECT: "Authentication should be fast"

2. **Atomic Requirements**: Each requirement should describe ONE specific capability or constraint
   ✓ CORRECT: "The system must encrypt passwords using AES-256"
   ✗ INCORRECT: "The system must encrypt passwords and validate them against policy"

3. **Testability**: Include measurable criteria whenever the source text provides them
   ✓ CORRECT: "The API must respond within 500 milliseconds"
   ✗ VAGUE: "The API must respond quickly"

4. **Priority Mapping**:
   - "must" or "shall" → priority: "must" (mandatory)
   - "should" → priority: "should" (recommended)
   - "may" or "can" → priority: "may" (optional)

5. **Evidence**: Capture the original text or key phrases that led to this requirement extraction

6. **Categories**: Choose the most specific tag:
   - functional: Features and capabilities
   - performance: Speed, throughput, latency
   - security: Authentication, authorization, encryption
   - usability: User experience and interface
   - reliability: Uptime, error handling, resilience
   - compliance: Standards and regulations
   - interface: APIs, integrations, protocols
   - data: Storage, formats, validation
   - constraint: Limitations and boundaries

Extract ALL requirements from the provided text, even if they need reformulation to meet quality standards.
"""

__all__ = ["REQUIREMENT_EXTRACTION_TOOL", "EXTRACTION_SYSTEM_PROMPT"]
