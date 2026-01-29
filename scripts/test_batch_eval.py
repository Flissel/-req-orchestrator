#!/usr/bin/env python
"""Test the batch criteria evaluator via the validate/auto endpoint"""

import requests
import json
import time

def test_validate_auto():
    """Test the /api/v1/validate/auto endpoint"""
    url = "http://localhost:8087/api/v1/validate/auto"
    
    # Test requirement - use correct field names
    payload = {
        "requirement_id": "TEST-001",
        "requirement_text": "The system must allow users to log in within 3 seconds"
    }
    
    print(f"Testing: {payload['requirement_text']}")
    print("-" * 60)
    
    start = time.time()
    response = requests.post(url, json=payload)
    elapsed = time.time() - start
    
    print(f"Status: {response.status_code}")
    print(f"Time: {elapsed:.2f}s")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Passed: {data.get('passed', 'N/A')}")
        print(f"Final Score: {data.get('final_score', 0):.2f}")
        print(f"Iterations: {len(data.get('iterations', []))}")
        
        # Show final scores
        final_scores = data.get('final_scores', {})
        if final_scores:
            print("\nFinal Scores:")
            for criterion, score in sorted(final_scores.items()):
                status = "✓" if score >= 0.7 else "✗"
                print(f"  {status} {criterion}: {score:.2f}")
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    test_validate_auto()