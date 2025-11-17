# -*- coding: utf-8 -*-
import pytest

from backend.core.rag import StructuredRequirement, EvaluationItem, SuggestionItem


def test_from_validate_item_alias_corrected_text():
    item = {
        "id": 1,
        "originalText": "The system shall respond within 200ms.",
        "correctedText": "The system shall respond within 200 ms (p95).",
        "evaluation": [
            {"criterion": "clarity", "isValid": True, "reason": ""},
        ],
        "score": 0.91,
        "verdict": "pass",
        "suggestions": [{"text": "Add metric p95", "priority": "high"}],
        "foo": "bar-extra-field",
    }

    sr = StructuredRequirement.from_validate_item(item)

    assert sr.id == 1
    assert sr.originalText == "The system shall respond within 200ms."
    assert sr.rewrittenText == "The system shall respond within 200 ms (p95)."
    assert sr.score == 0.91
    assert sr.verdict == "pass"
    assert isinstance(sr.evaluation, list) and len(sr.evaluation) == 1
    assert isinstance(sr.evaluation[0], EvaluationItem)
    assert sr.evaluation[0].criterion == "clarity"
    assert sr.evaluation[0].isValid is True
    assert sr.metadata.get("foo") == "bar-extra-field"

    d = sr.to_dict()
    # ensure none fields are excluded and aliases resolved
    assert "rewrittenText" in d
    assert "correctedText" not in d
    assert "redefinedRequirement" not in d


def test_from_validate_item_alias_redefined_requirement_and_atoms_extra_fields():
    item = {
        "id": "REQ_1",
        "originalText": "The API shall return JSON.",
        "redefinedRequirement": "The API shall return a JSON object with {status:'ok'}.",
        "evaluation": [],
        # Atom-like suggestion with extra fields
        "suggestions": [
            {
                "type": "correction",
                "correction": "Add explicit status field",
                "priority": "atom",
                "metrics": {"impact": "medium"},
            }
        ],
        "score": 0.75,
        "verdict": "pass",
    }

    sr = StructuredRequirement.from_validate_item(item)

    assert sr.id == "REQ_1"
    assert sr.rewrittenText == "The API shall return a JSON object with {status:'ok'}."
    assert sr.score == 0.75
    assert sr.verdict == "pass"
    assert len(sr.suggestions) == 1
    sug = sr.suggestions[0]
    assert isinstance(sug, SuggestionItem)
    # extra fields should be preserved due to extra="allow"
    assert getattr(sug, "type") == "correction"
    assert getattr(sug, "correction") == "Add explicit status field"
    # priority propagated
    assert sug.priority == "atom"


def test_from_agent_answer_item_maps_reqid_and_metadata():
    item = {
        "reqId": "REQ_9",
        "originalText": "System shall log all requests.",
        "redefinedRequirement": "System shall log all HTTP requests with method, path, and status code.",
        "evaluation": [
            {"criterion": "measurability", "isValid": False, "reason": "Missing thresholds"}
        ],
        "suggestions": [{"text": "Define log format schema"}],
        "score": 0.42,
        "verdict": "fail",
        "extraX": 123,  # should end up in metadata
    }

    sr = StructuredRequirement.from_agent_answer_item(item)

    assert sr.id == "REQ_9"
    assert sr.originalText.startswith("System shall log")
    assert "HTTP requests" in sr.rewrittenText
    assert isinstance(sr.evaluation[0], EvaluationItem)
    assert sr.evaluation[0].criterion == "measurability"
    assert sr.evaluation[0].isValid is False
    assert isinstance(sr.suggestions[0], SuggestionItem)
    assert sr.score == 0.42
    assert sr.verdict == "fail"
    assert sr.metadata.get("extraX") == 123


def test_to_dict_excludes_none_fields():
    # No rewrittenText / score / verdict provided
    sr = StructuredRequirement(
        id="REQ_5",
        originalText="The service shall support CORS.",
        evaluation=[],
        suggestions=[],
        metadata={"source": "unit-test"},
    )
    d = sr.to_dict()
    assert "rewrittenText" not in d
    assert "score" not in d
    assert "verdict" not in d
    assert d["id"] == "REQ_5"
    assert d["originalText"] == "The service shall support CORS."
    assert d["metadata"]["source"] == "unit-test"


def test_suggestions_fallback_from_plain_string():
    # suggestions contains a plain string; should map to SuggestionItem(text=...)
    item = {
        "id": 2,
        "originalText": "The system shall provide a health endpoint.",
        "correctedText": "The system shall provide /health returning a JSON object.",
        "evaluation": [],
        "suggestions": ["Consider adding /health JSON example"],
    }
    sr = StructuredRequirement.from_validate_item(item)
    assert len(sr.suggestions) == 1
    assert isinstance(sr.suggestions[0], SuggestionItem)
    assert sr.suggestions[0].text == "Consider adding /health JSON example"
    # priority not set
    assert sr.suggestions[0].priority is None