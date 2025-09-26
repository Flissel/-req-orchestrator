# -*- coding: utf-8 -*-
"""
Comprehensive Test Suite für FastAPI Requirements Engineering System
Tests für AutoGen Agents, gRPC Workers, und FastAPI Endpoints
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
from fastapi.testclient import TestClient
from autogen_core import DefaultTopicId
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime

# Test Imports
from backend_app.agents import (
    RequirementsEvaluatorAgent,
    RequirementsSuggestionAgent,
    RequirementsRewriteAgent,
    RequirementProcessingRequest,
    EvaluationResult,
    SuggestionResult,
    RewriteResult
)
from backend_app.db_async import get_db_async, save_evaluation_async
from backend_app.llm_async import llm_evaluate_async, llm_suggest_async, llm_rewrite_async
from fastapi_main import app

# Test Configuration
TEST_DATABASE_PATH = "./test_data/test_app.db"
TEST_GRPC_HOST = "localhost:50052"  # Different port for testing

class TestConfig:
    """Test-Konfiguration"""
    OPENAI_API_KEY = "test_key"
    OPENAI_MODEL = "gpt-4o-mini"
    MOCK_MODE = True
    DATABASE_PATH = TEST_DATABASE_PATH
    GRPC_HOST = TEST_GRPC_HOST

# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_client():
    """FastAPI Test Client"""
    with TestClient(app) as client:
        yield client

@pytest.fixture
async def async_client():
    """Async HTTP Client für FastAPI"""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def mock_requirement_request():
    """Mock Requirement Request"""
    return {
        "requirementText": "Das System soll eine REST API bereitstellen.",
        "context": {
            "language": "de",
            "area": "api", 
            "priority": "high"
        },
        "criteriaKeys": ["clarity", "testability", "completeness"]
    }

@pytest.fixture
def mock_evaluation_result():
    """Mock Evaluation Result"""
    return {
        "score": 0.85,
        "verdict": "good",
        "details": {
            "clarity": 0.9,
            "testability": 0.8,
            "completeness": 0.85
        },
        "latency_ms": 150,
        "model": "gpt-4o-mini"
    }

@pytest.fixture
async def test_grpc_runtime():
    """Test gRPC Runtime"""
    runtime = GrpcWorkerAgentRuntime(host_address=TEST_GRPC_HOST)
    yield runtime
    await runtime.stop()

# =============================================================================
# AutoGen Agents Tests
# =============================================================================

class TestAutoGenAgents:
    """Tests für AutoGen Agents"""
    
    @pytest.mark.asyncio
    async def test_requirements_evaluator_agent_creation(self):
        """Test: Requirements Evaluator Agent Creation"""
        agent = RequirementsEvaluatorAgent("TestEvaluator")
        
        assert agent is not None
        assert "TestEvaluator" in str(agent.id)
        assert agent.processed_count == 0
    
    @pytest.mark.asyncio
    async def test_requirements_suggestion_agent_creation(self):
        """Test: Requirements Suggestion Agent Creation"""
        agent = RequirementsSuggestionAgent("TestSuggester")
        
        assert agent is not None
        assert "TestSuggester" in str(agent.id)
        assert agent.processed_count == 0
    
    @pytest.mark.asyncio
    async def test_requirements_rewrite_agent_creation(self):
        """Test: Requirements Rewrite Agent Creation"""
        agent = RequirementsRewriteAgent("TestRewriter")
        
        assert agent is not None
        assert "TestRewriter" in str(agent.id)
        assert agent.processed_count == 0
    
    @pytest.mark.asyncio
    @patch('backend_app.agents.llm_evaluate')
    async def test_evaluator_agent_message_handling(self, mock_llm_evaluate):
        """Test: Evaluator Agent Message Handling"""
        # Mock LLM Response
        mock_llm_evaluate.return_value = {
            "score": 0.85,
            "verdict": "good",
            "details": {"clarity": 0.9, "testability": 0.8, "completeness": 0.85}
        }
        
        agent = RequirementsEvaluatorAgent("TestEvaluator")
        
        # Mock Message Context
        mock_context = MagicMock()
        mock_context.sender = MagicMock()
        mock_context.sender.type = "test_sender"
        mock_context.sender.key = "test_key"
        
        # Test Message
        test_message = RequirementProcessingRequest(
            requirement_id="test_req_001",
            requirement_text="Test requirement",
            context={"language": "de", "area": "test"},
            request_id="test_request_001"
        )
        
        # Mock publish_message method
        agent.publish_message = AsyncMock()
        
        # Execute
        await agent.evaluate_requirement(test_message, mock_context)
        
        # Assertions
        assert agent.processed_count == 1
        mock_llm_evaluate.assert_called_once()
        agent.publish_message.assert_called()

# =============================================================================
# Database Tests
# =============================================================================

class TestDatabase:
    """Tests für Database Operations"""
    
    @pytest.mark.asyncio
    async def test_database_connection(self):
        """Test: Database Connection"""
        db = await get_db_async()
        assert db is not None
    
    @pytest.mark.asyncio
    async def test_save_evaluation(self, mock_evaluation_result):
        """Test: Save Evaluation"""
        requirement_checksum = "test_checksum_001"
        
        evaluation_id = await save_evaluation_async(
            requirement_checksum=requirement_checksum,
            evaluation_data=mock_evaluation_result
        )
        
        assert evaluation_id is not None
        assert evaluation_id.startswith("eval_")

# =============================================================================
# LLM Service Tests
# =============================================================================

class TestLLMService:
    """Tests für LLM Service"""
    
    @pytest.mark.asyncio
    async def test_llm_evaluate_async(self):
        """Test: LLM Evaluate Async"""
        requirement_text = "Das System soll eine API bereitstellen."
        context = {"language": "de", "area": "api"}
        
        result = await llm_evaluate_async(requirement_text, context)
        
        assert result is not None
        assert "score" in result
        assert "verdict" in result
        assert "details" in result
        assert "latency_ms" in result
        assert "model" in result
        
        # In Mock-Mode sollten realistische Werte zurückgegeben werden
        assert 0.0 <= result["score"] <= 1.0
        assert result["verdict"] in ["excellent", "good", "acceptable", "needs_improvement", "poor"]
    
    @pytest.mark.asyncio
    async def test_llm_suggest_async(self):
        """Test: LLM Suggest Async"""
        requirement_text = "Das System soll eine API bereitstellen."
        context = {"language": "de", "area": "api"}
        
        result = await llm_suggest_async(requirement_text, context)
        
        assert result is not None
        assert "suggestions" in result
        assert "latency_ms" in result
        assert "model" in result
        assert isinstance(result["suggestions"], list)
        assert len(result["suggestions"]) > 0
    
    @pytest.mark.asyncio
    async def test_llm_rewrite_async(self):
        """Test: LLM Rewrite Async"""
        requirement_text = "Das System soll eine API bereitstellen."
        context = {"language": "de", "area": "api"}
        
        result = await llm_rewrite_async(requirement_text, context)
        
        assert result is not None
        assert "rewritten_requirement" in result
        assert "latency_ms" in result
        assert "model" in result
        assert len(result["rewritten_requirement"]) > 0

# =============================================================================
# FastAPI Endpoints Tests
# =============================================================================

class TestFastAPIEndpoints:
    """Tests für FastAPI Endpoints"""
    
    def test_health_endpoint(self, test_client):
        """Test: Health Endpoint"""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert "timestamp" in response.json()
    
    def test_system_status_endpoint(self, test_client):
        """Test: System Status Endpoint"""
        response = test_client.get("/api/v1/system/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        required_fields = ["grpcHostRunning", "activeWorkers", "totalProcessedToday", "systemLoad", "uptime"]
        for field in required_fields:
            assert field in data
    
    @pytest.mark.asyncio
    async def test_evaluate_requirement_endpoint(self, async_client, mock_requirement_request):
        """Test: Evaluate Requirement Endpoint"""
        response = await async_client.post(
            "/api/v1/requirements/evaluate",
            json=mock_requirement_request
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "requestId" in data
        assert "status" in data
        assert "websocketUrl" in data
        assert data["status"] == "processing"
    
    @pytest.mark.asyncio
    async def test_batch_requirements_endpoint(self, async_client, mock_requirement_request):
        """Test: Batch Requirements Endpoint"""
        batch_request = {
            "requirements": [mock_requirement_request, mock_requirement_request],
            "processingTypes": ["evaluation", "suggestion"],
            "parallelLimit": 2
        }
        
        response = await async_client.post(
            "/api/v1/requirements/batch",
            json=batch_request
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "batchId" in data
        assert "totalRequirements" in data
        assert "processingTypes" in data
        assert "status" in data
        assert "websocketUrl" in data
        assert data["totalRequirements"] == 2
        assert data["status"] == "processing"
    
    def test_invalid_requirement_request(self, test_client):
        """Test: Invalid Requirement Request"""
        invalid_request = {
            "requirementText": "",  # Empty text should fail validation
            "context": {}
        }
        
        response = test_client.post(
            "/api/v1/requirements/evaluate",
            json=invalid_request
        )
        
        assert response.status_code == 422  # Validation Error

# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration Tests für das gesamte System"""
    
    @pytest.mark.asyncio
    async def test_full_requirement_processing_flow(self, async_client, mock_requirement_request):
        """Test: Vollständiger Requirements Processing Flow"""
        # 1. Requirement zur Verarbeitung senden
        response = await async_client.post(
            "/api/v1/requirements/evaluate",
            json=mock_requirement_request
        )
        
        assert response.status_code == 200
        data = response.json()
        request_id = data["requestId"]
        
        # 2. Status abfragen (simuliert)
        # In einem echten Test würde man auf WebSocket-Updates warten
        # oder den Status-Endpoint abfragen
        
        # 3. Verarbeitungsergebnis validieren
        # Dies würde normalerweise über WebSocket oder Status-Endpoint erfolgen
        assert request_id is not None
        assert len(request_id) > 0
    
    @pytest.mark.asyncio
    async def test_batch_processing_flow(self, async_client, mock_requirement_request):
        """Test: Batch Processing Flow"""
        # Batch von 3 Requirements erstellen
        batch_request = {
            "requirements": [
                mock_requirement_request,
                {**mock_requirement_request, "requirementText": "Requirement 2"},
                {**mock_requirement_request, "requirementText": "Requirement 3"}
            ],
            "processingTypes": ["evaluation"],
            "parallelLimit": 2
        }
        
        response = await async_client.post(
            "/api/v1/requirements/batch",
            json=batch_request
        )
        
        assert response.status_code == 200
        data = response.json()
        
        batch_id = data["batchId"]
        assert batch_id is not None
        assert data["totalRequirements"] == 3

# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance Tests"""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, async_client, mock_requirement_request):
        """Test: Concurrent Requests"""
        # 10 gleichzeitige Requests senden
        tasks = []
        for i in range(10):
            task = async_client.post(
                "/api/v1/requirements/evaluate",
                json={**mock_requirement_request, "requirementText": f"Requirement {i}"}
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
        # Alle Requests sollten erfolgreich sein
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert "requestId" in data
    
    @pytest.mark.asyncio
    async def test_large_batch_processing(self, async_client, mock_requirement_request):
        """Test: Large Batch Processing"""
        # Großer Batch mit 50 Requirements
        large_batch = {
            "requirements": [
                {**mock_requirement_request, "requirementText": f"Large batch requirement {i}"}
                for i in range(50)
            ],
            "processingTypes": ["evaluation"],
            "parallelLimit": 5
        }
        
        response = await async_client.post(
            "/api/v1/requirements/batch",
            json=large_batch
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["totalRequirements"] == 50

# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests für Error Handling"""
    
    def test_malformed_json_request(self, test_client):
        """Test: Malformed JSON Request"""
        response = test_client.post(
            "/api/v1/requirements/evaluate",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    def test_missing_required_fields(self, test_client):
        """Test: Missing Required Fields"""
        incomplete_request = {
            "context": {"language": "de"}
            # requirementText fehlt
        }
        
        response = test_client.post(
            "/api/v1/requirements/evaluate",
            json=incomplete_request
        )
        
        assert response.status_code == 422
    
    def test_invalid_processing_types(self, test_client, mock_requirement_request):
        """Test: Invalid Processing Types"""
        invalid_batch = {
            "requirements": [mock_requirement_request],
            "processingTypes": ["invalid_type"],  # Ungültiger Type
            "parallelLimit": 1
        }
        
        response = test_client.post(
            "/api/v1/requirements/batch",
            json=invalid_batch
        )
        
        # Should handle invalid processing types gracefully
        # Implementation dependent - might be 400 or 422
        assert response.status_code in [400, 422]

# =============================================================================
# Test Utilities
# =============================================================================

def create_test_data():
    """Erstellt Test-Daten"""
    test_requirements = [
        {
            "requirementText": "Das System soll eine REST API bereitstellen.",
            "context": {"language": "de", "area": "api", "priority": "high"}
        },
        {
            "requirementText": "Die Anwendung muss SSL/TLS verwenden.",
            "context": {"language": "de", "area": "security", "priority": "high"}
        },
        {
            "requirementText": "Antwortzeiten sollen unter 200ms liegen.",
            "context": {"language": "de", "area": "performance", "priority": "medium"}
        }
    ]
    
    return test_requirements

def cleanup_test_data():
    """Räumt Test-Daten auf"""
    import os
    if os.path.exists(TEST_DATABASE_PATH):
        os.remove(TEST_DATABASE_PATH)

# =============================================================================
# Test Runner Configuration
# =============================================================================

if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--capture=no",
        "--asyncio-mode=auto"
    ])
