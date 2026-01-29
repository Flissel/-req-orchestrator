#!/usr/bin/env python3
"""
Test script to compare old vs new validation endpoints.

Old: /api/v1/validate/auto (9 separate criterion agents)
New: /api/v1/validate/auto/enhanced (SocietyOfMind with 4-5 coordinated calls)
"""

import asyncio
import httpx
import time
import json

BASE_URL = "http://localhost:8087"

TEST_REQUIREMENTS = [
    {
        "id": "REQ-TEST-001",
        "text": "The system should filter results in real-time"
    },
    {
        "id": "REQ-TEST-002", 
        "text": "Das System muss CPU-Auslastung in Prozent anzeigen"
    },
    {
        "id": "REQ-TEST-003",
        "text": "Users must be able to search processes by name"
    }
]


async def test_enhanced_validation():
    """Test the new enhanced validation endpoint."""
    print("\n" + "="*60)
    print("🧠 TESTING ENHANCED VALIDATION (SocietyOfMind)")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        start_time = time.time()
        
        response = await client.post(
            f"{BASE_URL}/api/v1/validate/auto/enhanced",
            json={
                "requirements": TEST_REQUIREMENTS,
                "threshold": 0.7,
                "max_iterations": 2
            }
        )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"\n✅ Success in {elapsed:.2f}s")
            print(f"   Total processed: {result.get('total_processed')}")
            print(f"   Passed: {result.get('passed_count')}")
            print(f"   Failed: {result.get('failed_count')}")
            print(f"   Improved: {result.get('improved_count')}")
            print(f"   Average Score: {result.get('average_score', 0):.2f}")
            print(f"   API Time: {result.get('total_time_ms', 0)}ms")
            
            print("\n📋 Individual Results:")
            for req in result.get('requirements', []):
                print(f"\n   [{req.get('id')}] Score: {req.get('score', 0):.2f} - {req.get('verdict', 'unknown').upper()}")
                print(f"   Original: {req.get('original_text', '')[:60]}...")
                print(f"   Enhanced: {req.get('enhanced_text', '')[:60]}...")
                if req.get('purpose'):
                    print(f"   Purpose: {req.get('purpose', '')[:60]}...")
                if req.get('gaps_filled'):
                    print(f"   Gaps filled: {req.get('gaps_filled')}")
                if req.get('gaps_remaining'):
                    print(f"   Gaps remaining: {req.get('gaps_remaining')}")
            
            return elapsed, result
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(response.text[:500])
            return elapsed, None


async def test_single_enhanced() -> float:
    """Test single enhanced validation endpoint."""
    print("\n" + "="*60)
    print("🔬 TESTING SINGLE ENHANCED VALIDATION")
    print("="*60)
    
    requirement = TEST_REQUIREMENTS[0]
    print(f"\nRequirement: {requirement['text'][:60]}...")
    
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/validate/single/enhanced",
            json={
                "requirement_id": "REQ-SINGLE-001",
                "requirement_text": "The application must provide a responsive user interface",
                "threshold": 0.7,
                "max_iterations": 3
            }
        )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            req = response.json()
            
            print(f"\n✅ Success in {elapsed:.2f}s ({req.get('time_ms', 0)}ms API)")
            print(f"   ID: {req.get('id')}")
            print(f"   Score: {req.get('score', 0):.2f} - {req.get('verdict', 'unknown').upper()}")
            print(f"   Iterations: {req.get('iterations', 0)}")
            print(f"\n   Original: {req.get('original_text', '')}")
            print(f"   Enhanced: {req.get('enhanced_text', '')}")
            print(f"   Purpose: {req.get('purpose', '')}")
            
            if req.get('gaps_filled'):
                print(f"   Gaps filled: {req.get('gaps_filled')}")
            if req.get('gaps_remaining'):
                print(f"   Gaps remaining: {req.get('gaps_remaining')}")
            if req.get('changes'):
                print(f"   Changes: {req.get('changes')}")
            
            return elapsed
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(response.text[:500])
            return elapsed


async def test_batch_enhanced() -> float:
    """Test batch enhanced validation endpoint."""
    print("\n" + "="*60)
    print("🔬 TESTING BATCH ENHANCED VALIDATION (5 requirements)")
    print("="*60)
    
    print(f"\nProcessing {len(TEST_REQUIREMENTS)} requirements...")
    
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        pass


async def main():
    print("\n" + "="*70)
    print("    ENHANCED VALIDATION TEST - SocietyOfMind Process")
    print("="*70)
    
    # Test single enhanced
    single_time = await test_single_enhanced()
    
    # Test batch enhanced
    batch_time, result = await test_enhanced_validation()
    
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    print(f"   Single requirement: {single_time:.2f}s")
    print(f"   Batch (3 requirements): {batch_time:.2f}s")
    print(f"   Average per requirement: {batch_time/3:.2f}s")
    
    print("\n💡 Expected improvements over old process:")
    print("   - Old: 9 LLM calls/iteration × 3 iterations = 27 calls")
    print("   - New: 4-5 LLM calls/iteration × 2 iterations = 8-10 calls")
    print("   - Expected speedup: ~2-3x faster")


if __name__ == "__main__":
    asyncio.run(main())