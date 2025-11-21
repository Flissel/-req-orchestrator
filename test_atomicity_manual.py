#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manual test script for RequirementsAtomicityAgent
Tests basic functionality without pytest
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.core.agents import (
    RequirementsAtomicityAgent,
    AtomicSplitRequest,
    AtomicSplitResult
)


async def test_atomicity_agent():
    """Test basic AtomicityAgent functionality"""

    print("=" * 60)
    print("Testing RequirementsAtomicityAgent")
    print("=" * 60)

    # 1. Test Agent Initialization
    print("\n1. Testing Agent Initialization...")
    agent = RequirementsAtomicityAgent("TestAtomicity")
    print(f"[OK] Agent created: {agent.id}")
    print(f"[OK] Processed count: {agent.processed_count}")
    print(f"[OK] Split count: {agent.split_count}")

    # 2. Test _evaluate_atomic method
    print("\n2. Testing _evaluate_atomic method...")
    try:
        eval_result = await agent._evaluate_atomic(
            "Das System muss schnell sein",
            {}
        )
        print(f"[OK] Evaluation result: {eval_result}")
        atomic_score = eval_result.get("details", {}).get("atomic", 0.0)
        print(f"[OK] Atomic score: {atomic_score}")
    except Exception as e:
        print(f"[FAIL] Evaluation failed: {str(e)}")

    # 3. Test AtomicSplitRequest dataclass
    print("\n3. Testing AtomicSplitRequest dataclass...")
    request = AtomicSplitRequest(
        requirement_id="REQ-001",
        requirement_text="Das System muss schnell, skalierbar und sicher sein",
        context={"project": "Test"},
        max_splits=5
    )
    print(f"[OK] Request created:")
    print(f"  - requirement_id: {request.requirement_id}")
    print(f"  - request_id: {request.request_id}")
    print(f"  - max_splits: {request.max_splits}")
    print(f"  - retry_attempt: {request.retry_attempt}")

    # 4. Test AtomicSplitResult dataclass
    print("\n4. Testing AtomicSplitResult dataclass...")
    result = AtomicSplitResult(
        requirement_id="REQ-001",
        request_id="split_123",
        is_atomic=False,
        atomic_score=0.4,
        splits=[
            {"text": "Das System muss schnell sein", "rationale": "Performance"},
            {"text": "Das System muss skalierbar sein", "rationale": "Scalability"}
        ],
        latency_ms=1500,
        model_used="gpt-4o-mini"
    )
    print(f"[OK] Result created:")
    print(f"  - is_atomic: {result.is_atomic}")
    print(f"  - atomic_score: {result.atomic_score}")
    print(f"  - splits count: {len(result.splits)}")
    print(f"  - latency_ms: {result.latency_ms}")

    # 5. Test _split_atomic_llm (requires OpenAI API key)
    print("\n5. Testing _split_atomic_llm method...")
    try:
        import os
        if not os.getenv("OPENAI_API_KEY"):
            print("[WARN] Skipping LLM test (no OPENAI_API_KEY)")
        else:
            splits = await agent._split_atomic_llm(
                "Das System muss schnell, skalierbar und sicher sein",
                {},
                max_splits=5
            )
            print(f"[OK] LLM Splitting successful:")
            for i, split in enumerate(splits, 1):
                print(f"  {i}. {split['text']}")
                print(f"     Rationale: {split['rationale']}")
    except Exception as e:
        print(f"[FAIL] LLM Splitting failed: {str(e)}")

    # 6. Test _split_with_retry (requires OpenAI API key)
    print("\n6. Testing _split_with_retry method...")
    try:
        if not os.getenv("OPENAI_API_KEY"):
            print("[WARN] Skipping retry test (no OPENAI_API_KEY)")
        else:
            splits = await agent._split_with_retry(
                "Das System muss schnell, skalierbar und sicher sein",
                {},
                max_splits=5,
                current_attempt=0
            )
            print(f"[OK] Split with retry successful: {len(splits)} splits")
            for i, split in enumerate(splits, 1):
                print(f"  {i}. {split['text']}")
    except Exception as e:
        print(f"[FAIL] Split with retry failed: {str(e)}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    # Run the async test
    try:
        asyncio.run(test_atomicity_agent())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
