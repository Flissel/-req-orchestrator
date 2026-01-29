# -*- coding: utf-8 -*-
"""
Unit Tests for Parallel Validation System.

Tests the ValidationWorkerAgent, ValidationDelegatorAgent, and parallel execution
with various worker configurations.

Run with: pytest tests/test_parallel_validation.py -v
"""
import asyncio
import os
import time
from unittest.mock import patch, MagicMock
import pytest

# Add project root to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestValidationTask:
    """Tests for ValidationTask dataclass."""
    
    def test_create_task(self):
        """Test creating a validation task."""
        from arch_team.agents.validation_worker import ValidationTask
        
        task = ValidationTask(
            req_id="REQ-001",
            text="Das System muss schnell sein",
            criteria_keys=["clarity", "testability"],
            threshold=0.7,
            tag="performance",
            index=0
        )
        
        assert task.req_id == "REQ-001"
        assert task.text == "Das System muss schnell sein"
        assert task.criteria_keys == ["clarity", "testability"]
        assert task.threshold == 0.7
        assert task.tag == "performance"
        assert task.index == 0
    
    def test_task_defaults(self):
        """Test default values for validation task."""
        from arch_team.agents.validation_worker import ValidationTask
        
        task = ValidationTask(req_id="REQ-002", text="Test requirement")
        
        assert task.criteria_keys is None
        assert task.threshold == 0.7
        assert task.tag is None
        assert task.index == 0


class TestValidationResult:
    """Tests for ValidationResult dataclass."""
    
    def test_create_result(self):
        """Test creating a validation result."""
        from arch_team.agents.validation_worker import ValidationResult
        
        result = ValidationResult(
            req_id="REQ-001",
            title="Test requirement",
            score=0.85,
            verdict="pass",
            evaluation=[{"criterion": "clarity", "score": 0.9}],
            tag="functional",
            worker_id="worker-0",
            processing_time_ms=150
        )
        
        assert result.score == 0.85
        assert result.verdict == "pass"
        assert result.worker_id == "worker-0"
    
    def test_result_with_error(self):
        """Test result with error."""
        from arch_team.agents.validation_worker import ValidationResult
        
        result = ValidationResult(
            req_id="REQ-002",
            title="Failed requirement",
            score=0.0,
            verdict="error",
            error="API timeout"
        )
        
        assert result.verdict == "error"
        assert result.error == "API timeout"


class TestValidationWorkerAgent:
    """Tests for ValidationWorkerAgent."""
    
    @pytest.fixture
    def mock_api_response(self):
        """Mock API response for validation."""
        return {
            "score": 0.85,
            "verdict": "pass",
            "evaluation": [
                {"criterion": "clarity", "score": 0.9, "passed": True, "feedback": "Clear"}
            ]
        }
    
    @pytest.mark.asyncio
    async def test_worker_validates_single_task(self, mock_api_response):
        """Test worker validating a single task."""
        from arch_team.agents.validation_worker import ValidationWorkerAgent, ValidationTask
        
        semaphore = asyncio.Semaphore(5)
        worker = ValidationWorkerAgent("worker-0", semaphore)
        
        task = ValidationTask(req_id="REQ-001", text="Test requirement")
        
        with patch.object(worker, '_call_validation_api', return_value=mock_api_response):
            result = await worker.validate(task)
        
        assert result.req_id == "REQ-001"
        assert result.score == 0.85
        assert result.verdict == "pass"
        assert result.worker_id == "worker-0"
    
    @pytest.mark.asyncio
    async def test_worker_handles_timeout(self):
        """Test worker handles timeout gracefully."""
        from arch_team.agents.validation_worker import ValidationWorkerAgent, ValidationTask
        
        semaphore = asyncio.Semaphore(5)
        worker = ValidationWorkerAgent("worker-0", semaphore)
        worker._timeout = 1  # Set short timeout for test
        
        task = ValidationTask(req_id="REQ-001", text="Test requirement")
        
        async def slow_api(*args, **kwargs):
            await asyncio.sleep(5)  # Longer than timeout
            return {}
        
        with patch.object(worker, '_call_validation_api', side_effect=slow_api):
            result = await worker.validate(task)
        
        assert result.verdict == "error"
        assert "Timeout" in (result.error or "")
    
    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self, mock_api_response):
        """Test that semaphore properly limits concurrent executions."""
        from arch_team.agents.validation_worker import ValidationWorkerAgent, ValidationTask
        
        max_concurrent = 2
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # Track concurrent executions
        concurrent_count = 0
        max_concurrent_observed = 0
        
        async def tracked_api(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent_observed
            concurrent_count += 1
            max_concurrent_observed = max(max_concurrent_observed, concurrent_count)
            await asyncio.sleep(0.1)  # Simulate API call
            concurrent_count -= 1
            return mock_api_response
        
        tasks = [ValidationTask(req_id=f"REQ-{i}", text=f"Req {i}") for i in range(10)]
        workers = [ValidationWorkerAgent(f"worker-{i}", semaphore) for i in range(10)]
        
        # Patch all workers
        for worker in workers:
            worker._call_validation_api = tracked_api
        
        # Run all validations concurrently
        await asyncio.gather(*[
            workers[i].validate(tasks[i])
            for i in range(10)
        ])
        
        # Should never exceed semaphore limit
        assert max_concurrent_observed <= max_concurrent


class TestValidationDelegatorAgent:
    """Tests for ValidationDelegatorAgent."""
    
    @pytest.fixture
    def mock_validation_result(self):
        """Mock validation result."""
        return {
            "score": 0.8,
            "verdict": "pass",
            "evaluation": []
        }
    
    def test_delegator_init_default_concurrent(self):
        """Test delegator initializes with default max_concurrent."""
        from arch_team.agents.validation_delegator import ValidationDelegatorAgent
        
        delegator = ValidationDelegatorAgent()
        assert delegator.max_concurrent == 5
    
    def test_delegator_init_custom_concurrent(self):
        """Test delegator with custom max_concurrent."""
        from arch_team.agents.validation_delegator import ValidationDelegatorAgent
        
        delegator = ValidationDelegatorAgent(max_concurrent=10)
        assert delegator.max_concurrent == 10
    
    def test_delegator_init_from_env(self):
        """Test delegator reads max_concurrent from environment."""
        from arch_team.agents.validation_delegator import ValidationDelegatorAgent
        
        with patch.dict(os.environ, {"VALIDATION_MAX_CONCURRENT": "3"}):
            delegator = ValidationDelegatorAgent()
            assert delegator.max_concurrent == 3
    
    @pytest.mark.asyncio
    async def test_validate_empty_batch(self):
        """Test validating empty batch returns empty result."""
        from arch_team.agents.validation_delegator import ValidationDelegatorAgent
        
        delegator = ValidationDelegatorAgent(max_concurrent=5)
        result = await delegator.validate_batch([])
        
        assert result.total_count == 0
        assert result.passed_count == 0
        assert result.failed_count == 0
        assert result.results == []
    
    @pytest.mark.asyncio
    async def test_validate_batch_parallel(self, mock_validation_result):
        """Test batch validation runs in parallel."""
        from arch_team.agents.validation_delegator import ValidationDelegatorAgent
        from arch_team.agents.validation_worker import ValidationWorkerAgent
        
        requirements = [
            {"req_id": f"REQ-{i}", "title": f"Requirement {i}", "tag": "functional"}
            for i in range(10)
        ]
        
        delegator = ValidationDelegatorAgent(max_concurrent=5)
        
        # Mock the validation API
        with patch('arch_team.agents.validation_worker.ValidationWorkerAgent._call_validation_api',
                   return_value=mock_validation_result):
            result = await delegator.validate_batch(requirements)
        
        assert result.total_count == 10
        assert result.passed_count == 10
        assert result.failed_count == 0
        assert len(result.results) == 10
    
    @pytest.mark.asyncio
    async def test_validate_batch_with_failures(self):
        """Test batch validation handles failures correctly."""
        from arch_team.agents.validation_delegator import ValidationDelegatorAgent
        
        requirements = [
            {"req_id": "REQ-1", "title": "Good requirement"},
            {"req_id": "REQ-2", "title": "Bad requirement"},
        ]
        
        pass_result = {"score": 0.9, "verdict": "pass", "evaluation": []}
        fail_result = {"score": 0.3, "verdict": "fail", "evaluation": []}
        
        call_count = [0]
        
        def mock_api(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                return fail_result
            return pass_result
        
        delegator = ValidationDelegatorAgent(max_concurrent=2)
        
        with patch('arch_team.agents.validation_worker.ValidationWorkerAgent._call_validation_api',
                   side_effect=mock_api):
            result = await delegator.validate_batch(requirements)
        
        assert result.total_count == 2
        assert result.passed_count + result.failed_count == 2
    
    def test_to_dict_results(self):
        """Test converting batch result to dict format."""
        from arch_team.agents.validation_delegator import ValidationDelegatorAgent, BatchValidationResult
        from arch_team.agents.validation_worker import ValidationResult
        
        batch_result = BatchValidationResult(
            total_count=2,
            passed_count=1,
            failed_count=1,
            error_count=0,
            results=[
                ValidationResult(
                    req_id="REQ-1",
                    title="Test 1",
                    score=0.9,
                    verdict="pass",
                    tag="functional"
                ),
                ValidationResult(
                    req_id="REQ-2",
                    title="Test 2",
                    score=0.3,
                    verdict="fail",
                    tag="performance"
                )
            ],
            total_time_ms=1000
        )
        
        delegator = ValidationDelegatorAgent()
        dict_results = delegator.to_dict_results(batch_result)
        
        assert len(dict_results) == 2
        assert dict_results[0]["req_id"] == "REQ-1"
        assert dict_results[0]["score"] == 0.9
        assert dict_results[1]["verdict"] == "fail"


class TestPerformanceBenchmark:
    """Performance benchmark comparing sequential vs parallel validation."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_parallel_faster_than_sequential(self):
        """Benchmark: Parallel should be significantly faster than sequential."""
        from arch_team.agents.validation_delegator import ValidationDelegatorAgent
        
        # Create mock requirements
        num_requirements = 20
        requirements = [
            {"req_id": f"REQ-{i}", "title": f"Requirement {i} text", "tag": "functional"}
            for i in range(num_requirements)
        ]
        
        # Mock API with 100ms delay to simulate network latency
        mock_result = {"score": 0.8, "verdict": "pass", "evaluation": []}
        
        def slow_api(*args, **kwargs):
            time.sleep(0.1)  # 100ms per call
            return mock_result
        
        # === Sequential baseline (estimated) ===
        sequential_time_estimate = num_requirements * 0.1  # 100ms per req
        
        # === Parallel execution ===
        delegator = ValidationDelegatorAgent(max_concurrent=5)
        
        with patch('arch_team.agents.validation_worker.ValidationWorkerAgent._call_validation_api',
                   side_effect=slow_api):
            start = time.time()
            result = await delegator.validate_batch(requirements)
            parallel_time = time.time() - start
        
        # Parallel should be at least 3x faster than sequential
        speedup = sequential_time_estimate / parallel_time
        
        print(f"\n=== Performance Benchmark ===")
        print(f"Requirements: {num_requirements}")
        print(f"Max concurrent: 5")
        print(f"Sequential estimate: {sequential_time_estimate:.2f}s")
        print(f"Parallel actual: {parallel_time:.2f}s")
        print(f"Speedup: {speedup:.1f}x")
        
        assert result.total_count == num_requirements
        assert speedup >= 3.0, f"Expected at least 3x speedup, got {speedup:.1f}x"
    
    @pytest.mark.asyncio
    async def test_various_worker_counts(self):
        """Test performance with different worker counts."""
        from arch_team.agents.validation_delegator import ValidationDelegatorAgent
        
        num_requirements = 10
        requirements = [
            {"req_id": f"REQ-{i}", "title": f"Requirement {i}", "tag": "functional"}
            for i in range(num_requirements)
        ]
        
        mock_result = {"score": 0.8, "verdict": "pass", "evaluation": []}
        
        def fast_api(*args, **kwargs):
            time.sleep(0.05)  # 50ms per call
            return mock_result
        
        results = {}
        
        for worker_count in [1, 2, 5, 10]:
            delegator = ValidationDelegatorAgent(max_concurrent=worker_count)
            
            with patch('arch_team.agents.validation_worker.ValidationWorkerAgent._call_validation_api',
                       side_effect=fast_api):
                start = time.time()
                result = await delegator.validate_batch(requirements)
                elapsed = time.time() - start
            
            results[worker_count] = {
                "time": elapsed,
                "passed": result.passed_count
            }
        
        print("\n=== Worker Count Benchmark ===")
        for workers, data in results.items():
            print(f"Workers: {workers} | Time: {data['time']:.2f}s | Passed: {data['passed']}")
        
        # More workers should be faster (with diminishing returns)
        assert results[5]["time"] < results[1]["time"]


# Convenience function for running benchmark standalone
async def run_benchmark():
    """Run performance benchmark."""
    test = TestPerformanceBenchmark()
    await test.test_parallel_faster_than_sequential()
    await test.test_various_worker_counts()


if __name__ == "__main__":
    asyncio.run(run_benchmark())