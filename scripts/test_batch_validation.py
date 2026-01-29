#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test-Skript für optimierte Batch-Validierung.

Vergleicht:
1. Sequenzielle Validierung (1 LLM Call pro Requirement)
2. Batch-Validierung (5 Requirements pro LLM Call)

Erwarteter Speedup: ~3x
"""
import asyncio
import json
import time
import sys
from typing import List, Dict, Any

# Test Requirements
TEST_REQUIREMENTS = [
    {"id": "REQ-001", "text": "Das System soll eine Antwortzeit unter 200ms haben"},
    {"id": "REQ-002", "text": "Als Benutzer möchte ich mich einloggen können"},
    {"id": "REQ-003", "text": "Die Datenbank muss ACID-konform sein"},
    {"id": "REQ-004", "text": "Das System soll 1000 gleichzeitige Benutzer unterstützen"},
    {"id": "REQ-005", "text": "Passwörter müssen mit bcrypt gehasht werden"},
    {"id": "REQ-006", "text": "Die API soll REST-konform sein"},
    {"id": "REQ-007", "text": "Das System soll eine Verfügbarkeit von 99.9% haben"},
    {"id": "REQ-008", "text": "Logdateien müssen 30 Tage aufbewahrt werden"},
    {"id": "REQ-009", "text": "Die Benutzeroberfläche soll responsiv sein"},
    {"id": "REQ-010", "text": "Das System soll alle 4 Stunden ein Backup erstellen"},
]


async def test_sequential_validation(requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Test sequenzielle Validierung (1 Call pro Requirement)."""
    import aiohttp
    
    start_time = time.time()
    results = []
    
    async with aiohttp.ClientSession() as session:
        for req in requirements:
            payload = {"text": req["text"]}
            try:
                async with session.post(
                    "http://localhost:8087/api/v2/evaluate/single",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    result = await response.json()
                    results.append({
                        "id": req["id"],
                        "score": result.get("score", 0.0),
                        "verdict": result.get("verdict", "error")
                    })
            except Exception as e:
                results.append({
                    "id": req["id"],
                    "score": 0.0,
                    "verdict": "error",
                    "error": str(e)
                })
    
    elapsed = time.time() - start_time
    
    return {
        "mode": "sequential",
        "total_requirements": len(requirements),
        "elapsed_seconds": round(elapsed, 2),
        "avg_per_requirement": round(elapsed / len(requirements), 2),
        "results": results
    }


async def test_batch_validation(requirements: List[Dict[str, Any]], batch_size: int = 5) -> Dict[str, Any]:
    """Test Batch-Validierung (mehrere Requirements pro Call)."""
    import aiohttp
    
    start_time = time.time()
    
    payload = {
        "items": requirements,
        "batch_size": batch_size
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "http://localhost:8087/api/v2/evaluate/batch/optimized",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                results = await response.json()
        except Exception as e:
            results = [{"error": str(e)}]
    
    elapsed = time.time() - start_time
    
    return {
        "mode": "batch_optimized",
        "total_requirements": len(requirements),
        "batch_size": batch_size,
        "elapsed_seconds": round(elapsed, 2),
        "avg_per_requirement": round(elapsed / len(requirements), 2),
        "results": results if isinstance(results, list) else [results]
    }


async def test_parallel_sequential(requirements: List[Dict[str, Any]], max_concurrent: int = 5) -> Dict[str, Any]:
    """Test parallele sequenzielle Validierung (asyncio.gather)."""
    import aiohttp
    
    start_time = time.time()
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def validate_one(req: Dict[str, Any], session: aiohttp.ClientSession) -> Dict[str, Any]:
        async with semaphore:
            payload = {"text": req["text"]}
            try:
                async with session.post(
                    "http://localhost:8087/api/v2/evaluate/single",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    result = await response.json()
                    return {
                        "id": req["id"],
                        "score": result.get("score", 0.0),
                        "verdict": result.get("verdict", "error")
                    }
            except Exception as e:
                return {
                    "id": req["id"],
                    "score": 0.0,
                    "verdict": "error",
                    "error": str(e)
                }
    
    async with aiohttp.ClientSession() as session:
        tasks = [validate_one(req, session) for req in requirements]
        results = await asyncio.gather(*tasks)
    
    elapsed = time.time() - start_time
    
    return {
        "mode": "parallel_sequential",
        "total_requirements": len(requirements),
        "max_concurrent": max_concurrent,
        "elapsed_seconds": round(elapsed, 2),
        "avg_per_requirement": round(elapsed / len(requirements), 2),
        "results": list(results)
    }


async def main():
    print("=" * 60)
    print("BATCH VALIDATION PERFORMANCE TEST")
    print("=" * 60)
    print(f"Testing with {len(TEST_REQUIREMENTS)} requirements\n")
    
    # Test 1: Batch Optimized (neue Methode)
    print("1. Testing BATCH OPTIMIZED validation...")
    batch_result = await test_batch_validation(TEST_REQUIREMENTS, batch_size=5)
    print(f"   Time: {batch_result['elapsed_seconds']}s")
    print(f"   Avg per req: {batch_result['avg_per_requirement']}s")
    
    # Show some results
    for r in batch_result['results'][:3]:
        if isinstance(r, dict) and 'score' in r:
            print(f"   - {r.get('id', '?')}: {r.get('verdict', '?')} (score: {r.get('score', 0):.2f})")
    print()
    
    # Test 2: Parallel Sequential (bestehende Methode)
    print("2. Testing PARALLEL SEQUENTIAL validation...")
    parallel_result = await test_parallel_sequential(TEST_REQUIREMENTS, max_concurrent=5)
    print(f"   Time: {parallel_result['elapsed_seconds']}s")
    print(f"   Avg per req: {parallel_result['avg_per_requirement']}s")
    print()
    
    # Compare
    print("=" * 60)
    print("RESULTS COMPARISON")
    print("=" * 60)
    print(f"Batch Optimized: {batch_result['elapsed_seconds']}s")
    print(f"Parallel Sequential: {parallel_result['elapsed_seconds']}s")
    
    if parallel_result['elapsed_seconds'] > 0 and batch_result['elapsed_seconds'] > 0:
        speedup = parallel_result['elapsed_seconds'] / batch_result['elapsed_seconds']
        print(f"\nSpeedup: {speedup:.2f}x")
        
        if speedup > 1.5:
            print("✅ Batching is significantly faster!")
        elif speedup > 1.0:
            print("✅ Batching is faster")
        else:
            print("⚠️ Batching is not faster (may be due to overhead)")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        import aiohttp
    except ImportError:
        print("Installing aiohttp...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
        import aiohttp
    
    asyncio.run(main())