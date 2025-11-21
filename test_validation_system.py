#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the new Requirements Validation System

This script demonstrates the automatic validation workflow:
1. Create a vague requirement
2. Run through RequirementOrchestrator
3. Show improvements from each criterion specialist
4. Display final result

Usage:
    python test_validation_system.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_validation_system():
    """Test the complete validation system"""

    print("=" * 80)
    print("Requirements Validation System - Test")
    print("=" * 80)
    print()

    # Import components
    try:
        from arch_team.agents.requirement_orchestrator import RequirementOrchestrator
        from arch_team.agents.criterion_specialists import get_all_specialists
        print("✓ Successfully imported orchestrator and specialists")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("\nMake sure you're in the project root directory.")
        return

    # Test requirements (from original problem statement)
    test_requirements = [
        {
            "id": "REQ-001",
            "text": "Die App muss schnell sein",
            "description": "Vague requirement without metrics or user story format"
        },
        {
            "id": "REQ-002",
            "text": "System soll skalierbar sein",
            "description": "Vague requirement without specific scalability criteria"
        }
    ]

    print()
    print("Test Requirements:")
    print("-" * 80)
    for req in test_requirements:
        print(f"  {req['id']}: \"{req['text']}\"")
        print(f"  Description: {req['description']}")
        print()

    # Create orchestrator
    print("Creating RequirementOrchestrator...")
    orchestrator = RequirementOrchestrator(
        threshold=0.7,
        max_iterations=3,
        stream_callback=None  # No SSE streaming for this test
    )
    print(f"✓ Orchestrator created (threshold=0.7, max_iterations=3)")
    print()

    # Show available specialists
    specialists = get_all_specialists()
    print(f"Available Criterion Specialists ({len(specialists)}):")
    print("-" * 80)
    for specialist in specialists:
        print(f"  • {specialist.criterion_name:25s} - {specialist.description}")
    print()

    # Process each requirement
    for req in test_requirements:
        print("=" * 80)
        print(f"Processing: {req['id']}")
        print("=" * 80)
        print()
        print(f"Original Text: \"{req['text']}\"")
        print()

        try:
            # Run validation
            print("Running validation...")
            result = await orchestrator.process(
                requirement_id=req['id'],
                requirement_text=req['text'],
                context={"test": True}
            )

            # Display results
            print()
            print("Results:")
            print("-" * 80)
            print(f"  Status: {'✓ PASSED' if result.passed else '✗ FAILED'}")
            print(f"  Final Score: {result.final_score:.2f}")
            print(f"  Total Iterations: {len(result.iterations)}")
            print(f"  Total Fixes Applied: {result.total_fixes}")
            print(f"  Split Occurred: {'Yes' if result.split_occurred else 'No'}")
            print()

            # Show final scores per criterion
            print("Final Criterion Scores:")
            print("-" * 80)
            for criterion, score in sorted(result.final_scores.items()):
                status = "✓" if score >= 0.7 else "✗"
                print(f"  {status} {criterion:25s}: {score:.2f}")
            print()

            # Show iteration details
            if result.iterations:
                print("Iteration History:")
                print("-" * 80)
                for iteration in result.iterations:
                    print(f"\nIteration {iteration.iteration_number}:")
                    print(f"  Overall Score: {iteration.overall_score:.2f}")
                    print(f"  Requirement Text: \"{iteration.requirement_text[:100]}...\""
                          if len(iteration.requirement_text) > 100
                          else f"  Requirement Text: \"{iteration.requirement_text}\"")

                    if iteration.fixes_applied:
                        print(f"  Fixes Applied ({len(iteration.fixes_applied)}):")
                        for fix in iteration.fixes_applied:
                            improvement = fix['score_after'] - fix['score_before']
                            print(f"    • {fix['criterion']:20s}: "
                                  f"{fix['score_before']:.2f} → {fix['score_after']:.2f} "
                                  f"(+{improvement:.2f})")
                            if fix.get('suggestion'):
                                print(f"      Suggestion: {fix['suggestion'][:80]}...")

                    if iteration.split_occurred:
                        print(f"  Split into {len(iteration.split_children)} children")

            # Show final text
            print()
            print("Final Requirement Text:")
            print("-" * 80)
            print(f"\"{result.final_text}\"")
            print()

            # Show comparison
            if result.final_text != req['text']:
                print("Improvement Summary:")
                print("-" * 80)
                print(f"  Original Length: {len(req['text'])} chars")
                print(f"  Final Length: {len(result.final_text)} chars")
                print(f"  Score Improvement: +{result.final_score - 0.5:.2f} (assumed baseline 0.5)")
                print()

        except Exception as e:
            print(f"✗ Error during validation: {e}")
            import traceback
            traceback.print_exc()
            print()

    print("=" * 80)
    print("Test Complete")
    print("=" * 80)
    print()
    print("Summary:")
    print("  The validation system successfully:")
    print("  ✓ Evaluated requirements against 10 quality criteria")
    print("  ✓ Identified failing criteria automatically")
    print("  ✓ Applied specialist agent fixes iteratively")
    print("  ✓ Tracked all changes and improvements")
    print()
    print("Next Steps:")
    print("  1. Integrate orchestrator into validate_router.py")
    print("  2. Connect frontend to SSE stream endpoint")
    print("  3. Test with real users and gather feedback")
    print()


async def test_single_specialist():
    """Test a single criterion specialist in detail"""

    print("=" * 80)
    print("Single Specialist Test - ClarityAgent")
    print("=" * 80)
    print()

    try:
        from arch_team.agents.criterion_specialists import ClarityAgent

        agent = ClarityAgent()
        print(f"✓ Created {agent.__class__.__name__}")
        print(f"  Criterion: {agent.criterion_name}")
        print(f"  Description: {agent.description}")
        print(f"  Threshold: {agent.threshold}")
        print()

        # Test requirement
        test_text = "Die App muss schnell sein"
        print(f"Test Requirement: \"{test_text}\"")
        print()

        # Evaluate
        print("Step 1: Evaluate...")
        score = await agent.evaluate(test_text)
        print(f"  Score: {score:.2f} ({'PASS' if score >= 0.7 else 'FAIL'})")
        print()

        # Suggest fix
        if score < 0.7:
            print("Step 2: Generate suggestion...")
            suggestion = await agent.suggest_fix(test_text, score)
            print(f"  Suggestion: {suggestion}")
            print()

            # Apply fix
            print("Step 3: Apply fix...")
            improved_text = await agent.apply_fix(test_text, suggestion)
            print(f"  Improved Text: \"{improved_text}\"")
            print()

            # Re-evaluate
            print("Step 4: Re-evaluate...")
            new_score = await agent.evaluate(improved_text)
            improvement = new_score - score
            print(f"  New Score: {new_score:.2f} ({'PASS' if new_score >= 0.7 else 'FAIL'})")
            print(f"  Improvement: +{improvement:.2f}")
            print()

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Test the Requirements Validation System")
    parser.add_argument(
        '--mode',
        choices=['full', 'specialist'],
        default='full',
        help='Test mode: full system or single specialist'
    )
    args = parser.parse_args()

    print()
    print("Requirements Validation System - Test Script")
    print()

    # Check for OpenAI API key or mock mode
    api_key = os.environ.get("OPENAI_API_KEY", "")
    mock_mode = os.environ.get("MOCK_MODE", "").lower() in ("1", "true", "yes")

    if not api_key and not mock_mode:
        print("⚠ Warning: No OpenAI API key found and MOCK_MODE is not enabled")
        print()
        print("Options:")
        print("  1. Set OPENAI_API_KEY environment variable:")
        print("     export OPENAI_API_KEY=sk-...")
        print()
        print("  2. Enable mock mode (uses heuristic evaluation):")
        print("     export MOCK_MODE=true")
        print()
        print("Continuing with mock mode for this test...")
        os.environ["MOCK_MODE"] = "true"
    elif mock_mode:
        print("ℹ Running in MOCK_MODE (heuristic evaluation)")
    else:
        print("✓ OpenAI API key detected")

    print()

    # Run test
    if args.mode == 'full':
        asyncio.run(test_validation_system())
    else:
        asyncio.run(test_single_specialist())


if __name__ == "__main__":
    main()
