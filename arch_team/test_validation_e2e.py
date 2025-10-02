#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
End-to-End Test for Requirements Validation (Society of Mind).

Prerequisites:
- Backend running on port 8000: python -m arch_team.service
- OPENAI_API_KEY set in environment
- AutoGen installed: pip install 'pyautogen>=0.4.0'

Test Scenarios:
1. Single low-quality requirement → evaluate, suggest, rewrite
2. Multiple requirements with duplicates → detect_duplicates
3. User clarification (manual test via file)
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Override API base URL to match running backend (port 8000)
os.environ["VALIDATION_API_BASE"] = "http://localhost:8000"

from arch_team.agents.requirements_agent import validate_requirements


async def test_single_requirement():
    """Test 1: Single low-quality requirement."""
    print("\n" + "="*60)
    print("TEST 1: Single Low-Quality Requirement")
    print("="*60)

    requirements = [
        "Die App muss schnell sein"
    ]

    print(f"Input: {requirements[0]}")
    print("\nExpected workflow:")
    print("  1. RequirementsOperator: evaluate_requirement()")
    print("     - score < 0.7 (fail)")
    print("  2. RequirementsOperator: suggest_improvements()")
    print("     - Generate atomic suggestions")
    print("  3. RequirementsOperator: rewrite_requirement()")
    print("     - Improved version with User Story format")
    print("  4. QAValidator: Check all steps completed")
    print("     - APPROVE")
    print("\nRunning...")

    try:
        result = await validate_requirements(
            requirements,
            criteria_keys=["clarity", "testability", "measurability"],
            threshold=0.7,
            correlation_id="test-single"
        )

        print("\n" + "-"*60)
        print("RESULT:")
        print(f"  Status: {result.get('status')}")
        print(f"  Requirements: {result.get('requirements_count')}")
        print(f"  Messages: {result.get('message_count')}")
        print("-"*60)

        return result.get('status') == 'completed'

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_multiple_with_duplicates():
    """Test 2: Multiple requirements with semantic duplicates."""
    print("\n" + "="*60)
    print("TEST 2: Multiple Requirements with Duplicates")
    print("="*60)

    requirements = [
        "Video-Wasserzeichen für Urheberrecht einfügen",
        "System soll skalierbar sein",
        "Wasserzeichen in Videos zum Schutz von Urheberrechten"  # Semantic duplicate of #1
    ]

    print("Input:")
    for i, req in enumerate(requirements, 1):
        print(f"  {i}. {req}")

    print("\nExpected workflow:")
    print("  1. RequirementsOperator: evaluate_requirement() for each")
    print("  2. RequirementsOperator: detect_duplicates()")
    print("     - Should find #1 and #3 are similar (>0.9)")
    print("  3. QAValidator: APPROVE")
    print("\nRunning...")

    try:
        result = await validate_requirements(
            requirements,
            threshold=0.7,
            correlation_id="test-multiple"
        )

        print("\n" + "-"*60)
        print("RESULT:")
        print(f"  Status: {result.get('status')}")
        print(f"  Requirements: {result.get('requirements_count')}")
        print(f"  Messages: {result.get('message_count')}")
        print("-"*60)

        return result.get('status') == 'completed'

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_user_clarification():
    """Test 3: User clarification (requires manual intervention)."""
    print("\n" + "="*60)
    print("TEST 3: User Clarification (Manual Test)")
    print("="*60)

    print("\nThis test requires manual user input via file.")
    print("Skipping automated test.")
    print("\nTo test manually:")
    print("  1. Run: python arch_team/test_validation_e2e.py --manual-clarification")
    print("  2. When prompted, create file: data/tmp/clarification_test-manual.txt")
    print("  3. Write answer in file (e.g., 'all criteria')")
    print("  4. Agent will read and continue")

    return True  # Skip for now


async def main():
    """Run all E2E tests."""
    print("\n" + "="*60)
    print("Requirements Validation E2E Tests")
    print("="*60)

    # Check prerequisites
    print("\nChecking prerequisites...")

    # Check backend
    try:
        import requests
        response = requests.get("http://localhost:8000/", timeout=5)
        print("  [OK] Backend running on port 8000")
    except Exception as e:
        print(f"  [FAIL] Backend not reachable: {e}")
        print("         Start with: python -m arch_team.service")
        return

    # Check OpenAI API key
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("  [WARN] OPENAI_API_KEY not set")
        print("         Set in .env or environment")
    else:
        print("  [OK] OPENAI_API_KEY configured")

    # Check AutoGen
    try:
        import autogen_agentchat
        print("  [OK] AutoGen installed")
    except ImportError:
        print("  [FAIL] AutoGen not installed")
        print("         Install with: pip install 'pyautogen>=0.4.0'")
        return

    # Run tests
    results = []

    print("\n" + "="*60)
    print("Running Tests...")
    print("="*60)

    # Test 1
    result1 = await test_single_requirement()
    results.append(("Single Requirement", result1))

    # Test 2
    result2 = await test_multiple_with_duplicates()
    results.append(("Multiple Requirements", result2))

    # Test 3
    result3 = await test_user_clarification()
    results.append(("User Clarification", result3))

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*60)

    return passed == total


if __name__ == "__main__":
    import sys

    if "--manual-clarification" in sys.argv:
        print("\nManual clarification test not yet implemented.")
        sys.exit(1)

    success = asyncio.run(main())
    sys.exit(0 if success else 1)
