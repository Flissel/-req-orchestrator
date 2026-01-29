#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Rewrite Agent with Real Validated Requirements.

Loads validation results from a JSON file and tests the parallel rewrite
functionality to improve failed requirements.

Usage:
    python scripts/test_rewrite_agent.py [json_file] [max_concurrent] [limit]
    
    Example:
    python scripts/test_rewrite_agent.py debug/validated_requirements_20251126_135652.json 3 5
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")


async def test_rewrite_parallel(failed_requirements: list, max_concurrent: int = 3, max_attempts: int = 3):
    """
    Test parallel rewrite with real failed requirements.
    
    Returns timing and result statistics.
    """
    from arch_team.agents.rewrite_delegator import RewriteDelegatorAgent
    
    print(f"\n{'='*60}")
    print(f"PARALLEL REWRITE TEST")
    print(f"{'='*60}")
    print(f"Failed requirements: {len(failed_requirements)}")
    print(f"Max concurrent workers: {max_concurrent}")
    print(f"Max attempts per requirement: {max_attempts}")
    print(f"{'='*60}\n")
    
    delegator = RewriteDelegatorAgent(
        max_concurrent=max_concurrent,
        max_attempts=max_attempts,
        target_score=0.7,
        enable_revalidation=False  # Disable for faster testing
    )
    
    start_time = time.time()
    result = await delegator.rewrite_batch(failed_requirements)
    elapsed = time.time() - start_time
    
    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"Total time: {elapsed:.2f}s")
    print(f"Time per requirement: {elapsed/len(failed_requirements)*1000:.0f}ms")
    print(f"")
    print(f"Total: {result.total_count}")
    print(f"Rewritten: {result.rewritten_count}")
    print(f"Improved: {result.improved_count}")
    print(f"Unchanged: {result.unchanged_count}")
    print(f"Errors: {result.error_count}")
    print(f"{'='*60}\n")
    
    # Show sample rewrites
    print("SAMPLE REWRITES:")
    print("-" * 60)
    for i, r in enumerate(result.results[:3]):
        print(f"\n[{i+1}] {r.req_id}")
        print(f"ORIGINAL: {r.original_text[:100]}...")
        print(f"REWRITTEN: {r.rewritten_text[:200]}..." if len(r.rewritten_text) > 200 else f"REWRITTEN: {r.rewritten_text}")
        print(f"ADDRESSED: {', '.join(r.addressed_criteria)}")
        if r.error:
            print(f"ERROR: {r.error}")
        print("-" * 60)
    
    return {
        "elapsed_seconds": elapsed,
        "total_count": result.total_count,
        "rewritten_count": result.rewritten_count,
        "improved_count": result.improved_count,
        "unchanged_count": result.unchanged_count,
        "error_count": result.error_count,
        "details": delegator.to_dict_results(result)
    }


def load_failed_requirements_from_json(json_path: str, limit: int = None) -> list:
    """
    Load failed requirements from a validation results JSON file.
    
    The JSON structure is expected to have:
    - requirements: list of validated requirement objects
    """
    print(f"Loading requirements from: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle different JSON structures
    if "requirements" in data:
        requirements = data["requirements"]
    elif "validation_results" in data and "details" in data["validation_results"]:
        requirements = data["validation_results"]["details"]
    else:
        requirements = data.get("items", [])
    
    # Filter to only failed requirements
    failed = [
        req for req in requirements
        if req.get("verdict") == "fail" or req.get("score", 1.0) < 0.7
    ]
    
    if limit:
        failed = failed[:limit]
    
    print(f"Found {len(failed)} failed requirements (out of {len(requirements)} total)")
    
    # Normalize requirement format for rewrite
    normalized = []
    for idx, req in enumerate(failed):
        normalized.append({
            "req_id": req.get("req_id", req.get("id", f"REQ-{idx+1}")),
            "title": req.get("title", req.get("text", req.get("original_text", ""))),
            "text": req.get("title", req.get("text", req.get("original_text", ""))),
            "score": req.get("score", 0.0),
            "evaluation": req.get("evaluation", []),
            "tag": req.get("tag", "unknown")
        })
    
    return normalized


async def main():
    # Parse command line arguments
    if len(sys.argv) < 2:
        # Default to latest validated JSON file
        debug_dir = project_root / "debug"
        json_files = sorted(debug_dir.glob("validated_requirements_*.json"), reverse=True)
        if not json_files:
            # Try regular requirements files
            json_files = sorted(debug_dir.glob("requirements_*.json"), reverse=True)
        if not json_files:
            print("No JSON files found in debug/")
            sys.exit(1)
        json_path = str(json_files[0])
        print(f"Using latest file: {json_path}")
    else:
        json_path = sys.argv[1]
    
    max_concurrent = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5  # Default to 5 for testing
    
    # Load failed requirements
    failed_requirements = load_failed_requirements_from_json(json_path, limit=limit)
    
    if not failed_requirements:
        print("No failed requirements found in JSON file")
        sys.exit(1)
    
    # Run parallel rewrite test
    result = await test_rewrite_parallel(failed_requirements, max_concurrent)
    
    # Save result
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = project_root / "debug" / f"rewrite_results_{timestamp}.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {result_file}")


if __name__ == "__main__":
    asyncio.run(main())