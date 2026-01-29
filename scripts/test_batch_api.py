#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Script for OpenAI Batch API

Tests the batch processing endpoints:
- POST /batch/submit - Submit requirements for batch processing
- GET /batch/status/{batch_id} - Check batch status
- GET /batch/results/{batch_id} - Get batch results
- POST /batch/cancel/{batch_id} - Cancel batch
- GET /batch/active - List active batches

Usage:
    python scripts/test_batch_api.py
    
Note: Batch API requires direct OpenAI API key (not OpenRouter).
"""

import asyncio
import httpx
import json
from datetime import datetime

# Configuration
API_BASE = "http://localhost:8087"

# Sample requirements for batch processing
SAMPLE_REQUIREMENTS = [
    {
        "id": "REQ-001",
        "text": "As a user, I want to log in with my email and password so that I can access my account securely.",
        "context": {"project": "Test Project", "category": "Authentication"}
    },
    {
        "id": "REQ-002", 
        "text": "The system shall process user requests within 200ms under normal load (95th percentile).",
        "context": {"project": "Test Project", "category": "Performance"}
    },
    {
        "id": "REQ-003",
        "text": "Users can view, edit, delete, and share their documents from the dashboard.",
        "context": {"project": "Test Project", "category": "Documents"}
    },
    {
        "id": "REQ-004",
        "text": "The application should be fast and reliable.",
        "context": {"project": "Test Project", "category": "Quality"}
    },
    {
        "id": "REQ-005",
        "text": "Given a registered user, when they request password reset, then an email with reset link shall be sent within 30 seconds.",
        "context": {"project": "Test Project", "category": "Authentication"}
    }
]


async def test_batch_submit():
    """Test submitting requirements for batch processing"""
    print("\n" + "="*60)
    print("Testing Batch Submit")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE}/batch/submit",
            json={
                "requirements": SAMPLE_REQUIREMENTS,
                "metadata": {
                    "test_run": "batch_api_test",
                    "timestamp": datetime.now().isoformat()
                }
            },
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Batch ID: {data.get('batch_id')}")
            print(f"Status: {data.get('status')}")
            print(f"Request Count: {data.get('request_count')}")
            print(f"Message: {data.get('message')}")
            return data.get('batch_id')
        elif response.status_code == 503:
            print("⚠️  Batch API not available")
            print("   This requires a direct OpenAI API key (not OpenRouter)")
            print("   Set OPENAI_API_KEY in your .env file")
            return None
        else:
            print(f"Error: {response.text}")
            return None


async def test_batch_status(batch_id: str):
    """Test checking batch status"""
    print("\n" + "="*60)
    print(f"Testing Batch Status: {batch_id}")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/batch/status/{batch_id}",
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2))
            return data
        else:
            print(f"Error: {response.text}")
            return None


async def test_batch_results(batch_id: str):
    """Test getting batch results"""
    print("\n" + "="*60)
    print(f"Testing Batch Results: {batch_id}")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/batch/results/{batch_id}",
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Total Count: {data.get('total_count')}")
            print(f"Success Count: {data.get('success_count')}")
            print(f"Failed Count: {data.get('failed_count')}")
            print("\nResults:")
            for result in data.get('results', []):
                print(f"\n  {result.get('id')}:")
                print(f"    Success: {result.get('success')}")
                if result.get('success'):
                    scores = result.get('scores', {})
                    print(f"    Scores: {scores}")
                    print(f"    Summary: {result.get('summary', 'N/A')}")
                else:
                    print(f"    Error: {result.get('error')}")
            return data
        else:
            print(f"Error: {response.text}")
            return None


async def test_active_batches():
    """Test listing active batches"""
    print("\n" + "="*60)
    print("Testing Active Batches")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/batch/active",
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2))
            return data
        else:
            print(f"Error: {response.text}")
            return None


async def wait_for_batch(batch_id: str, poll_interval: float = 10.0, max_polls: int = 60):
    """Wait for batch to complete with status polling"""
    print("\n" + "="*60)
    print(f"Waiting for batch completion: {batch_id}")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        for i in range(max_polls):
            response = await client.get(
                f"{API_BASE}/batch/status/{batch_id}",
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                progress = data.get('progress_percent', 0)
                
                print(f"[{i+1}/{max_polls}] Status: {status} - Progress: {progress}%")
                
                if status == 'completed':
                    print("✅ Batch completed!")
                    return True
                elif status in ('failed', 'expired', 'cancelled'):
                    print(f"❌ Batch {status}")
                    return False
            else:
                print(f"Error checking status: {response.text}")
            
            await asyncio.sleep(poll_interval)
        
        print("⏰ Timeout waiting for batch completion")
        return False


async def run_full_test():
    """Run complete batch processing test"""
    print("\n" + "#"*60)
    print("# OpenAI Batch API Test")
    print("#"*60)
    print(f"# Time: {datetime.now().isoformat()}")
    print(f"# API Base: {API_BASE}")
    print(f"# Requirements: {len(SAMPLE_REQUIREMENTS)}")
    print("#"*60)
    
    # 1. Submit batch
    batch_id = await test_batch_submit()
    
    if not batch_id:
        print("\n❌ Batch submission failed - check if OpenAI API key is configured")
        return
    
    # 2. Check status
    await test_batch_status(batch_id)
    
    # 3. List active batches
    await test_active_batches()
    
    # 4. Wait for completion (optional - can be long)
    print("\n" + "-"*60)
    print("Batch submitted successfully!")
    print("To wait for completion, use:")
    print(f"  python -c \"import asyncio; from scripts.test_batch_api import wait_for_batch; asyncio.run(wait_for_batch('{batch_id}'))\"")
    print("\nTo get results when complete:")
    print(f"  curl {API_BASE}/batch/results/{batch_id}")


async def run_quick_test():
    """Quick test to check if Batch API is available"""
    print("Quick Test: Checking Batch API availability...")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/batch/active",
            timeout=10.0
        )
        
        if response.status_code == 200:
            print("✅ Batch API endpoints are registered")
            return True
        elif response.status_code == 503:
            print("⚠️  Batch API available but OpenAI client not initialized")
            print("   This is expected when using OpenRouter instead of direct OpenAI")
            return False
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        asyncio.run(run_quick_test())
    else:
        asyncio.run(run_full_test())