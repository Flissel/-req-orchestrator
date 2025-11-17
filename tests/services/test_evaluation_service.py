# -*- coding: utf-8 -*-
import pytest
from typing import Any, Dict, List, Mapping, Optional, Sequence

from backend.core_v2.services.evaluation_service import EvaluationService
from backend.core_v2.services.ports import RequestContext, ServiceError


class FakePersistence:
    """
    Minimaler Fake für PersistencePort:
    - implementiert nur load_criteria(), da EvaluationService diese Funktion nutzt.
    """

    def __init__(self, criteria: Optional[List[Mapping[str, Any]]] = None) -> None:
        self._criteria = list(criteria or [])

    # entspricht PersistencePort.load_criteria(self, *, ctx)
    def load_criteria(self, *, ctx: Optional[RequestContext] = None) -> List[Mapping[str, Any]]:
        return list(self._criteria)


class FakeLLM:
    """
    Minimaler Fake für LLMPort:
    - implementiert nur evaluate(), da EvaluationService dies benötigt.
    """

    def __init__(self, details: Optional[List[Mapping[str, Any]]] = None) -> None:
        self._details = list(details or [])

    # entspricht LLMPort.evaluate(self, requirement_text, criteria_keys, *, context, ctx)
    def evaluate(
        self,
        requirement_text: str,
        criteria_keys: Sequence[str],
        *,
        context: Optional[Mapping[str, Any]] = None,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        # ignoriert criteria_keys bewusst; liefert deterministische Details zurück
        return list(self._details)


def test_evaluate_single_pass_with_zero_threshold():
    """
    Happy Path:
    - evaluate_single liefert verdict=pass bei threshold=0.0 unabhängig vom Score.
    """
    # Zwei simple Kriterien; Gewichtung wird im Service/Utils berechnet, hier nicht relevant
    criteria = [{"key": "clarity"}, {"key": "measurability"}]
    details = [
        {"criterion": "clarity", "score": 0.4, "passed": True, "feedback": ""},
        {"criterion": "measurability", "score": 0.3, "passed": True, "feedback": ""},
    ]

    svc = EvaluationService(persistence=FakePersistence(criteria), llm=FakeLLM(details))
    ctx = RequestContext(request_id="req-1")

    res = svc.evaluate_single(
        "System shall respond within 200 ms.",
        context={"language": "de"},
        criteria_keys=["clarity", "measurability"],
        threshold=0.0,  # erzwingt pass
        ctx=ctx,
    )

    assert isinstance(res, dict)
    assert res.get("requirementText")
    assert isinstance(res.get("evaluation"), list)
    assert res.get("verdict") == "pass"
    assert isinstance(res.get("score"), float)


def test_evaluate_batch_fail_with_one_threshold():
    """
    Batch Path:
    - evaluate_batch mit threshold=1.0 → alle Items fail, wenn Score < 1.0 (FakeLLM gibt leere Details zurück).
    """
    svc = EvaluationService(persistence=FakePersistence([]), llm=FakeLLM([]))
    ctx = RequestContext(request_id="batch-1")

    res = svc.evaluate_batch(
        ["A first requirement", "A second requirement"],
        context={},
        criteria_keys=None,  # Service nutzt Default-Fallback
        threshold=1.0,  # erzwingt fail, solange Score < 1.0
        ctx=ctx,
    )

    assert isinstance(res, list)
    assert len(res) == 2
    assert res[0]["id"] == "item-1"
    assert res[1]["id"] == "item-2"
    assert res[0]["verdict"] == "fail"
    assert res[1]["verdict"] == "fail"
    # Felder vorhanden
    for item in res:
        assert "originalText" in item
        assert "evaluation" in item
        assert "score" in item


def test_evaluate_single_invalid_request_raises():
    """
    Error Path:
    - Leerer requirementText löst ServiceError("invalid_request") aus.
    """
    svc = EvaluationService(persistence=FakePersistence([]), llm=FakeLLM([]))
    with pytest.raises(ServiceError) as ex:
        svc.evaluate_single(
            "",
            context=None,
            criteria_keys=None,
            ctx=RequestContext(request_id="err-1"),
        )
    assert isinstance(ex.value, ServiceError)
    assert getattr(ex.value, "code", "") == "invalid_request"