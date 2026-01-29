#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test RequirementOrchestrator with BatchCriteriaEvaluator integration."""

import asyncio
import time
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_orchestrator():
    """Test the orchestrator with batch evaluation."""
    from arch_team.agents.requirement_orchestrator import RequirementOrchestrator
    
    # Create orchestrator (will use BatchCriteriaEvaluator internally)
    orchestrator = RequirementOrchestrator(threshold=0.7, max_iterations=2)
    
    test_req = (
        "The system must allow users to log in with username and password, "
        "and display a dashboard after successful authentication."
    )
    
    print("\n" + "=" * 70)
    print("ORCHESTRATOR + BATCH EVALUATOR TEST")
    print("=" * 70)
    print(f"Requirement: {test_req[:60]}...")
    print(f"Max Iterations: 2")
    print("=" * 70)
    
    start = time.time()
    
    result = await orchestrator.process(
        requirement_id="TEST-BATCH-001",
        requirement_text=test_req,
        context={"project": "Test Project"}
    )
    
    elapsed = time.time() - start
    
    print(f"\n📊 RESULT:")
    print(f"   Passed: {result.passed}")
    print(f"   Final Score: {result.final_score:.2f}")
    print(f"   Split Occurred: {result.split_occurred}")
    print(f"   Total Fixes: {result.total_fixes}")
    print(f"   Iterations: {len(result.iterations)}")
    
    if result.final_scores:
        print(f"\n   Final Scores:")
        for criterion, score in sorted(result.final_scores.items()):
            status = "✓" if score >= 0.7 else "✗"
            print(f"      {status} {criterion}: {score:.2f}")
    
    print(f"\n⏱️  Total Time: {elapsed:.2f}s")
    print("=" * 70)
    
    # Count LLM calls from log (approximation based on iterations)
    expected_old_calls = len(result.iterations) * 9  # 9 criteria per iteration (old way)
    expected_batch_calls = len(result.iterations) * 1  # 1 call per iteration (batch way)
    
    print(f"\n📈 PERFORMANCE (estimated):")
    print(f"   With Batch Eval:  {expected_batch_calls} LLM calls for evaluation")
    print(f"   Without Batch:    {expected_old_calls} LLM calls for evaluation")
    print(f"   API Call Savings: {(1 - expected_batch_calls/expected_old_calls) * 100:.0f}%")
    print("=" * 70)
    
    return result


if __name__ == "__main__":
    asyncio.run(test_orchestrator())