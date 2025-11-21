# -*- coding: utf-8 -*-
"""
Tests für RequirementsAtomicityAgent
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from backend.core.agents import (
    RequirementsAtomicityAgent,
    AtomicSplitRequest,
    AtomicSplitResult
)


@pytest.fixture
def atomicity_agent():
    """Fixture für AtomicityAgent"""
    return RequirementsAtomicityAgent("TestAtomicity")


@pytest.fixture
def mock_llm_evaluate():
    """Mock für llm_evaluate"""
    with patch('backend.core.agents.llm_evaluate') as mock:
        # Mock response with low atomic score (0.4)
        mock.return_value = {
            "score": 0.4,
            "verdict": "fail",
            "details": {"atomic": 0.4},
            "model": "gpt-4o-mini"
        }
        yield mock


@pytest.fixture
def mock_llm_client():
    """Mock für OpenAI client"""
    with patch('backend.core.llm.get_llm_client') as mock_get_client:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()

        # Mock successful split response
        mock_choice.message.content = '''
{
  "splits": [
    {
      "text": "Das System muss schnell sein",
      "rationale": "Performance-Anforderung"
    },
    {
      "text": "Das System muss skalierbar sein",
      "rationale": "Skalierbarkeits-Anforderung"
    },
    {
      "text": "Das System muss sicher sein",
      "rationale": "Sicherheits-Anforderung"
    }
  ]
}
'''
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client
        yield mock_client


class TestAtomicityAgent:
    """Test Suite für RequirementsAtomicityAgent"""

    def test_agent_initialization(self, atomicity_agent):
        """Test: Agent wird korrekt initialisiert"""
        assert atomicity_agent is not None
        assert atomicity_agent.processed_count == 0
        assert atomicity_agent.split_count == 0
        assert "Atomicity" in str(atomicity_agent.id)

    @pytest.mark.asyncio
    async def test_evaluate_atomic_method(self, atomicity_agent, mock_llm_evaluate):
        """Test: _evaluate_atomic ruft llm_evaluate mit atomic criterion"""
        result = await atomicity_agent._evaluate_atomic(
            "Das System muss schnell, skalierbar und sicher sein",
            {}
        )

        assert result is not None
        assert "details" in result
        assert "atomic" in result["details"]
        mock_llm_evaluate.assert_called_once()

        # Verify criteria_keys parameter
        call_kwargs = mock_llm_evaluate.call_args[1]
        assert call_kwargs["criteria_keys"] == ["atomic"]

    @pytest.mark.asyncio
    async def test_split_atomic_llm_success(self, atomicity_agent, mock_llm_client):
        """Test: _split_atomic_llm generiert korrekte Splits"""
        splits = await atomicity_agent._split_atomic_llm(
            "Das System muss schnell, skalierbar und sicher sein",
            {},
            max_splits=5
        )

        assert len(splits) == 3
        assert all("text" in split for split in splits)
        assert all("rationale" in split for split in splits)

        # Verify OpenAI API was called correctly
        mock_llm_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_llm_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_split_atomic_llm_invalid_json(self, atomicity_agent):
        """Test: _split_atomic_llm behandelt invalides JSON"""
        with patch('backend.core.llm.get_llm_client') as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_choice = MagicMock()

            # Mock invalid JSON response
            mock_choice.message.content = "This is not JSON"
            mock_response.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            with pytest.raises(ValueError, match="kein valides JSON"):
                await atomicity_agent._split_atomic_llm(
                    "Test requirement",
                    {},
                    max_splits=5
                )

    @pytest.mark.asyncio
    async def test_split_with_retry_success(self, atomicity_agent, mock_llm_client):
        """Test: _split_with_retry erfolgreich beim ersten Versuch"""
        splits = await atomicity_agent._split_with_retry(
            "Das System muss schnell, skalierbar und sicher sein",
            {},
            max_splits=5,
            current_attempt=0
        )

        assert len(splits) == 3
        assert all("text" in split and split["text"].strip() for split in splits)

    @pytest.mark.asyncio
    async def test_split_with_retry_validation_too_few_splits(self, atomicity_agent):
        """Test: _split_with_retry validiert Mindestanzahl von Splits"""
        with patch('backend.core.llm.get_llm_client') as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_choice = MagicMock()

            # Mock response with only 1 split (should require at least 2)
            mock_choice.message.content = '''
{
  "splits": [
    {
      "text": "Das System muss schnell sein",
      "rationale": "Performance"
    }
  ]
}
'''
            mock_response.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception, match="nach 3 Versuchen fehlgeschlagen"):
                await atomicity_agent._split_with_retry(
                    "Test requirement",
                    {},
                    max_splits=5,
                    current_attempt=0
                )

    @pytest.mark.asyncio
    async def test_split_with_retry_max_splits_truncation(self, atomicity_agent):
        """Test: _split_with_retry kürzt zu viele Splits"""
        with patch('backend.core.llm.get_llm_client') as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_choice = MagicMock()

            # Mock response with 6 splits (max is 5)
            mock_choice.message.content = '''
{
  "splits": [
    {"text": "Split 1", "rationale": "R1"},
    {"text": "Split 2", "rationale": "R2"},
    {"text": "Split 3", "rationale": "R3"},
    {"text": "Split 4", "rationale": "R4"},
    {"text": "Split 5", "rationale": "R5"},
    {"text": "Split 6", "rationale": "R6"}
  ]
}
'''
            mock_response.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            splits = await atomicity_agent._split_with_retry(
                "Test requirement",
                {},
                max_splits=5,
                current_attempt=0
            )

            # Should be truncated to max_splits
            assert len(splits) == 5

    @pytest.mark.asyncio
    async def test_split_with_retry_adds_missing_rationale(self, atomicity_agent):
        """Test: _split_with_retry fügt fehlende rationale hinzu"""
        with patch('backend.core.llm.get_llm_client') as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_choice = MagicMock()

            # Mock response without rationale field
            mock_choice.message.content = '''
{
  "splits": [
    {"text": "Split 1"},
    {"text": "Split 2"}
  ]
}
'''
            mock_response.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            splits = await atomicity_agent._split_with_retry(
                "Test requirement",
                {},
                max_splits=5,
                current_attempt=0
            )

            # All splits should have rationale (empty string if missing)
            assert all("rationale" in split for split in splits)
            assert all(split["rationale"] == "" for split in splits)

    @pytest.mark.asyncio
    async def test_split_with_retry_fails_after_3_attempts(self, atomicity_agent):
        """Test: _split_with_retry gibt nach 3 Versuchen auf"""
        with patch('backend.core.llm.get_llm_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("API Error")
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception, match="nach 3 Versuchen fehlgeschlagen"):
                await atomicity_agent._split_with_retry(
                    "Test requirement",
                    {},
                    max_splits=5,
                    current_attempt=0
                )

            # Should have tried 3 times
            assert mock_client.chat.completions.create.call_count == 3


def test_atomic_split_request_dataclass():
    """Test: AtomicSplitRequest Dataclass erstellt korrekt"""
    request = AtomicSplitRequest(
        requirement_id="REQ-001",
        requirement_text="Das System muss schnell, skalierbar und sicher sein",
        context={"project": "Test"},
        max_splits=5
    )

    assert request.requirement_id == "REQ-001"
    assert request.max_splits == 5
    assert request.retry_attempt == 0
    assert request.request_id.startswith("split_")
    assert request.timestamp != ""


def test_atomic_split_result_dataclass():
    """Test: AtomicSplitResult Dataclass erstellt korrekt"""
    result = AtomicSplitResult(
        requirement_id="REQ-001",
        request_id="split_123",
        is_atomic=False,
        atomic_score=0.4,
        splits=[
            {"text": "Split 1", "rationale": "R1"},
            {"text": "Split 2", "rationale": "R2"}
        ],
        latency_ms=1500,
        model_used="gpt-4o-mini"
    )

    assert result.requirement_id == "REQ-001"
    assert result.is_atomic is False
    assert result.atomic_score == 0.4
    assert len(result.splits) == 2
    assert result.error_message is None
    assert result.retry_count == 0
    assert result.latency_ms == 1500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
