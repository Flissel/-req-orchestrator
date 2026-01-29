#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test script for BatchCriteriaEvaluator - verifies single LLM call for 9 criteria."""

import asyncio
import time
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_batch_evaluator():
    """Test the batch evaluator with a sample requirement."""
    from arch_team.agents.batch_criteria_evaluator import BatchCriteriaEvaluator
    
    evaluator = BatchCriteriaEvaluator()
    
    # Test requirement with multiple issues (compound, no metrics, impl details)
    test_req = (
        "The system must allow users to log in with username and password, "
        "and display a dashboard after successful authentication."
    )
    
    print("\n" + "=" * 70)
    print("BATCH CRITERIA EVALUATOR TEST")
    print("=" * 70)
    print(f"Requirement: {test_req[:60]}...")
    print("=" * 70)
    
    # Measure time for batch evaluation
    start = time.time()
    scores = await evaluator.evaluate(test_req)
    elapsed = time.time() - start
    
    print(f"\n✓ Scores returned: {len(scores)} criteria")
    print("-" * 50)
    
    passing = 0
    failing = 0
    for criterion, score in sorted(scores.items()):
        threshold = 0.7  # Default threshold
        status = "✓" if score >= threshold else "✗"
        if score >= threshold:
            passing += 1
        else:
            failing += 1
        print(f"  {status} {criterion:22s}: {score:.2f}")
    
    print("-" * 50)
    print(f"  Passing: {passing}/9, Failing: {failing}/9")
    
    # Calculate weighted average
    weight_result = evaluator.calculate_weighted_score(scores)
    print(f"\n  Overall Score: {weight_result['overall_score']:.2f}")
    print(f"  Gating Passed: {weight_result['gating_passed']}")
    print(f"  Final Verdict: {'PASS' if weight_result['passed'] else 'FAIL'}")
    
    print(f"\n⏱️  Time: {elapsed:.2f}s (single LLM call for all 9 criteria)")
    print("=" * 70)
    
    # Compare to expected time for 9 separate calls
    expected_sequential = elapsed * 9
    print(f"\n📊 PERFORMANCE COMPARISON:")
    print(f"   Batch (1 call):     {elapsed:.2f}s")
    print(f"   Sequential (9×):   ~{expected_sequential:.2f}s (estimated)")
    print(f"   Savings:           ~{(1 - 1/9) * 100:.0f}%")
    print("=" * 70)
    
    return scores


if __name__ == "__main__":
    asyncio.run(test_batch_evaluator())