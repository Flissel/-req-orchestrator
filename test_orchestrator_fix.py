"""
Test script to validate the duplicate evaluation bug fix in RequirementOrchestrator

This script:
1. Loads requirements from the latest debug JSON file
2. Processes a small subset through the orchestrator
3. Verifies the fix prevents duplicate evaluations
4. Saves detailed results with timestamps
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from arch_team.agents.requirement_orchestrator import BatchOrchestrator, RequirementValidationResult


# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)


def load_test_requirements(debug_file: str = "debug/requirements_20251120_135618.json", limit: int = 3) -> List[Dict[str, str]]:
    """Load a subset of requirements from debug JSON file"""
    logger.info(f"Loading test requirements from {debug_file}")

    with open(debug_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    requirements = data.get("requirements", [])
    logger.info(f"Found {len(requirements)} total requirements in file")

    # Select requirements that are likely to need fixes (shorter, less detailed)
    # These are more likely to trigger the validation workflow
    test_reqs = []
    for req in requirements[:20]:  # Look at first 20
        title = req.get("title", "")
        req_id = req.get("req_id", "UNKNOWN")

        # Select requirements that look like they need improvement
        if len(title) < 200 or "must provide" in title.lower() or "must read" in title.lower():
            test_reqs.append({
                "id": req_id,
                "text": title
            })

            if len(test_reqs) >= limit:
                break

    logger.info(f"Selected {len(test_reqs)} requirements for testing:")
    for req in test_reqs:
        logger.info(f"  - {req['id']}: {req['text'][:60]}...")

    return test_reqs


def analyze_results(results: List[RequirementValidationResult]) -> Dict[str, Any]:
    """Analyze validation results and extract key metrics"""
    analysis = {
        "total_processed": len(results),
        "passed": 0,
        "failed": 0,
        "split_occurred": 0,
        "total_fixes": 0,
        "total_iterations": 0,
        "requirements": []
    }

    for result in results:
        req_analysis = {
            "requirement_id": result.requirement_id,
            "passed": result.passed,
            "final_score": result.final_score,
            "split_occurred": result.split_occurred,
            "num_iterations": len(result.iterations),
            "total_fixes": result.total_fixes,
            "iterations_detail": []
        }

        # Count pass/fail
        if result.passed:
            analysis["passed"] += 1
        else:
            analysis["failed"] += 1

        if result.split_occurred:
            analysis["split_occurred"] += 1

        analysis["total_fixes"] += result.total_fixes
        analysis["total_iterations"] += len(result.iterations)

        # Analyze each iteration
        for iteration in result.iterations:
            iter_detail = {
                "iteration": iteration.iteration_number,
                "phase": iteration.phase,
                "overall_score": iteration.overall_score,
                "fixes_applied": len(iteration.fixes_applied),
                "fix_details": []
            }

            for fix in iteration.fixes_applied:
                iter_detail["fix_details"].append({
                    "criterion": fix["criterion"],
                    "score_before": fix["score_before"],
                    "score_after": fix.get("score_after")
                })

            req_analysis["iterations_detail"].append(iter_detail)

        analysis["requirements"].append(req_analysis)

    return analysis


def print_summary(analysis: Dict[str, Any]) -> None:
    """Print human-readable summary of results"""
    print("\n" + "="*80)
    print("VALIDATION TEST RESULTS SUMMARY")
    print("="*80)

    print(f"\n📊 Overview:")
    print(f"  • Total requirements processed: {analysis['total_processed']}")
    print(f"  • Passed: {analysis['passed']} ({analysis['passed']/max(analysis['total_processed'],1)*100:.0f}%)")
    print(f"  • Failed: {analysis['failed']} ({analysis['failed']/max(analysis['total_processed'],1)*100:.0f}%)")
    print(f"  • Split occurred: {analysis['split_occurred']}")
    print(f"  • Total fixes applied: {analysis['total_fixes']}")
    print(f"  • Total iterations: {analysis['total_iterations']}")
    print(f"  • Average fixes per requirement: {analysis['total_fixes']/max(analysis['total_processed'],1):.1f}")
    print(f"  • Average iterations per requirement: {analysis['total_iterations']/max(analysis['total_processed'],1):.1f}")

    print(f"\n📋 Detailed Results:")
    for req in analysis["requirements"]:
        status_icon = "✓" if req["passed"] else "✗"
        print(f"\n  {status_icon} {req['requirement_id']}: Score {req['final_score']*100:.0f}% ({'PASS' if req['passed'] else 'FAIL'})")
        print(f"     Iterations: {req['num_iterations']}, Total fixes: {req['total_fixes']}")

        for iter_detail in req["iterations_detail"]:
            print(f"     → Iteration {iter_detail['iteration']}: {iter_detail['fixes_applied']} fixes applied, score: {iter_detail['overall_score']:.2f}")
            for fix in iter_detail["fix_details"]:
                score_before = fix['score_before']
                score_after = fix.get('score_after', 'N/A')
                print(f"        • {fix['criterion']}: {score_before:.2f} → {score_after if isinstance(score_after, str) else f'{score_after:.2f}'}")

    print("\n" + "="*80)

    # Check for duplicate evaluation bug indicators
    print("\n🔍 Bug Detection:")
    has_duplicates = False
    for req in analysis["requirements"]:
        if req["num_iterations"] > 1:
            # Check if later iterations have similar fix counts to first iteration
            if len(req["iterations_detail"]) > 1:
                first_iter_fixes = req["iterations_detail"][0]["fixes_applied"]
                second_iter_fixes = req["iterations_detail"][1]["fixes_applied"] if len(req["iterations_detail"]) > 1 else 0

                if first_iter_fixes > 0 and second_iter_fixes == first_iter_fixes:
                    print(f"  ⚠️  {req['requirement_id']}: Possible duplicate - {first_iter_fixes} fixes in iteration 1 AND iteration 2")
                    has_duplicates = True

    if not has_duplicates:
        print("  ✓ No duplicate evaluation patterns detected!")

    print("="*80 + "\n")


async def main():
    """Main test execution"""
    logger.info("Starting orchestrator validation test...")

    # Load test requirements
    test_reqs = load_test_requirements(limit=3)

    if not test_reqs:
        logger.error("No test requirements found!")
        return

    # Create orchestrator
    logger.info("Creating BatchOrchestrator...")
    orchestrator = BatchOrchestrator(
        threshold=0.7,
        max_iterations=3
    )

    # Process requirements
    logger.info(f"Processing {len(test_reqs)} requirements...")
    results = await orchestrator.process_batch(
        requirements=test_reqs,
        context={"project": "Moiré Mouse Tracking"}
    )

    # Analyze results
    logger.info("Analyzing results...")
    analysis = analyze_results(results)

    # Print summary
    print_summary(analysis)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"debug/validation_test_results_{timestamp}.json"

    logger.info(f"Saving detailed results to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": timestamp,
            "test_file": "debug/requirements_20251120_135618.json",
            "num_requirements_tested": len(test_reqs),
            "analysis": analysis,
            "raw_results": [
                {
                    "requirement_id": r.requirement_id,
                    "passed": r.passed,
                    "final_score": r.final_score,
                    "final_text": r.final_text,
                    "split_occurred": r.split_occurred,
                    "total_fixes": r.total_fixes,
                    "iterations": [iter.to_dict() for iter in r.iterations]
                }
                for r in results
            ]
        }, f, indent=2, ensure_ascii=False)

    logger.info(f"✓ Test complete! Results saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
