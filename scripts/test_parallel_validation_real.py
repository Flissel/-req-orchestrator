#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Parallel Validation with Real Mined Requirements.

Loads a large JSON file from debug/ and tests the parallel validation
against the sequential approach to measure actual speedup.

Usage:
    python scripts/test_parallel_validation_real.py [json_file] [max_concurrent]
    
    Example:
    python scripts/test_parallel_validation_real.py debug/requirements_20251125_142309.json 5
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


async def test_parallel_validation(requirements: list, max_concurrent: int = 5):
    """
    Test parallel validation with real requirements.
    
    Returns timing, result statistics, and detailed validation results.
    """
    from arch_team.agents.validation_delegator import ValidationDelegatorAgent
    
    print(f"\n{'='*60}")
    print(f"PARALLEL VALIDATION TEST")
    print(f"{'='*60}")
    print(f"Requirements: {len(requirements)}")
    print(f"Max concurrent workers: {max_concurrent}")
    print(f"{'='*60}\n")
    
    delegator = ValidationDelegatorAgent(max_concurrent=max_concurrent)
    
    start_time = time.time()
    result = await delegator.validate_batch(requirements)
    elapsed = time.time() - start_time
    
    # Get detailed results using to_dict_results
    detailed_results = delegator.to_dict_results(result)
    
    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"Total time: {elapsed:.2f}s")
    print(f"Time per requirement: {elapsed/len(requirements)*1000:.0f}ms")
    print(f"")
    print(f"Passed: {result.passed_count}")
    print(f"Failed: {result.failed_count}")
    print(f"Errors: {result.error_count}")
    print(f"")
    print(f"Sequential estimate: {len(requirements) * 2.5:.0f}s (assuming 2.5s/req)")
    print(f"Actual time: {elapsed:.1f}s")
    print(f"Speedup: {(len(requirements) * 2.5) / elapsed:.1f}x")
    print(f"{'='*60}\n")
    
    return {
        "elapsed_seconds": elapsed,
        "requirements_count": len(requirements),
        "passed": result.passed_count,
        "failed": result.failed_count,
        "errors": result.error_count,
        "speedup": (len(requirements) * 2.5) / elapsed,
        "validated_requirements": detailed_results  # Full details per requirement
    }


def load_requirements_from_json(json_path: str, limit: int = None) -> list:
    """
    Load requirements from a debug JSON file.
    
    The JSON structure is expected to have:
    - requirements: list of requirement objects
    """
    print(f"Loading requirements from: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    requirements = data.get("requirements", [])
    
    if not requirements:
        # Try alternative structure
        requirements = data.get("items", [])
    
    if limit:
        requirements = requirements[:limit]
    
    print(f"Loaded {len(requirements)} requirements")
    
    # Normalize requirement format
    normalized = []
    for idx, req in enumerate(requirements):
        normalized.append({
            "req_id": req.get("req_id", req.get("id", f"REQ-{idx+1}")),
            "title": req.get("title", req.get("text", req.get("redefinedRequirement", ""))),
            "tag": req.get("tag", req.get("category", "unknown"))
        })
    
    return normalized


async def main():
    # Parse command line arguments
    if len(sys.argv) < 2:
        # Default to latest JSON file
        debug_dir = project_root / "debug"
        json_files = sorted(debug_dir.glob("requirements_*.json"), reverse=True)
        if not json_files:
            print("No JSON files found in debug/")
            sys.exit(1)
        json_path = str(json_files[0])
        print(f"Using latest file: {json_path}")
    else:
        json_path = sys.argv[1]

    # Use ENV variable for max_concurrent, with fallback to command line or default 10
    default_concurrent = int(os.environ.get("VALIDATION_MAX_CONCURRENT", "10"))
    max_concurrent = int(sys.argv[2]) if len(sys.argv) > 2 else default_concurrent
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 50  # Limit for testing
    
    # Load requirements
    requirements = load_requirements_from_json(json_path, limit=limit)
    
    if not requirements:
        print("No requirements found in JSON file")
        sys.exit(1)
    
    # Run parallel validation test
    result = await test_parallel_validation(requirements, max_concurrent)
    
    # Save benchmark statistics (without detailed results for smaller file)
    benchmark_file = project_root / "debug" / "parallel_validation_benchmark.json"
    benchmark_data = {
        "elapsed_seconds": result["elapsed_seconds"],
        "requirements_count": result["requirements_count"],
        "passed": result["passed"],
        "failed": result["failed"],
        "errors": result["errors"],
        "speedup": result["speedup"]
    }
    with open(benchmark_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, indent=2)
    print(f"Benchmark saved to: {benchmark_file}")
    
    # Save full validated requirements with all details
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    full_result_file = project_root / "debug" / f"validated_requirements_{timestamp}.json"
    full_result = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "source_file": json_path,
            "requirements_count": result["requirements_count"],
            "max_concurrent": max_concurrent,
            "elapsed_seconds": result["elapsed_seconds"],
            "passed": result["passed"],
            "failed": result["failed"],
            "errors": result["errors"]
        },
        "requirements": result["validated_requirements"]
    }
    with open(full_result_file, 'w', encoding='utf-8') as f:
        json.dump(full_result, f, indent=2, ensure_ascii=False)
    print(f"Full validated requirements saved to: {full_result_file}")


if __name__ == "__main__":
    asyncio.run(main())