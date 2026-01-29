#!/usr/bin/env python3
"""
Test Script for Tech Stack Agent System

Tests all major endpoints:
- GET /api/v1/techstack/templates - List templates
- POST /api/v1/techstack/detect - Auto-detect template
- POST /api/v1/techstack/match - Match requirement to template
- POST /api/v1/techstack/kg/rebuild - Rebuild Knowledge Graph
- POST /api/v1/techstack/kg/status - Get KG status
- POST /api/v1/techstack/transform - Transform requirements
- POST /api/v1/techstack/pipeline/process - Full pipeline step
"""

import requests
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:8087/api/v1/techstack"

# Sample requirements for testing
SAMPLE_REQUIREMENTS = [
    {
        "req_id": "REQ-TEST-001",
        "title": "The system must provide a web-based dashboard with real-time updates",
        "tag": "functional",
        "tags": ["web", "frontend", "realtime"]
    },
    {
        "req_id": "REQ-TEST-002",
        "title": "The API must support RESTful endpoints with JSON responses",
        "tag": "functional",
        "tags": ["api", "rest", "backend"]
    },
    {
        "req_id": "REQ-TEST-003",
        "title": "Data must be persisted in a PostgreSQL database",
        "tag": "functional",
        "tags": ["database", "postgresql"]
    }
]

SIMULATION_REQUIREMENTS = [
    {
        "req_id": "REQ-SIM-001",
        "title": "The simulation must model physical particle interactions in real-time",
        "tag": "functional",
        "tags": ["simulation", "physics", "performance"]
    },
    {
        "req_id": "REQ-SIM-002",
        "title": "The C++ core must process 10M particles per second",
        "tag": "performance",
        "tags": ["c++", "performance", "numerical"]
    }
]


def test_endpoint(name: str, method: str, endpoint: str, data: dict = None):
    """Test a single endpoint and report results."""
    url = f"{BASE_URL}{endpoint}"
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"  {method} {url}")
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            print(f"  ❌ Unknown method: {method}")
            return None
        
        if response.status_code == 200:
            result = response.json()
            print(f"  ✅ Status: {response.status_code}")
            
            # Print key info based on endpoint type
            if "templates" in result:
                print(f"  📋 Templates found: {len(result.get('templates', []))}")
            if "recommended_template" in result:
                print(f"  🎯 Recommended: {result['recommended_template']} (confidence: {result.get('confidence', 0):.2%})")
            if "status" in result:
                print(f"  📊 Status: {result['status']}")
            if "success" in result:
                print(f"  {'✅' if result['success'] else '❌'} Success: {result['success']}")
            if "transformation_applied" in result:
                print(f"  🔄 Transformed: {result['transformation_applied']}")
            
            return result
        else:
            print(f"  ❌ Status: {response.status_code}")
            print(f"  Error: {response.text[:200]}")
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"  ❌ Connection error - is the server running on port 8087?")
        return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def main():
    print("="*60)
    print("TECH STACK AGENT SYSTEM TEST")
    print(f"Started: {datetime.now().isoformat()}")
    print("="*60)
    
    # Test 1: List Templates
    result = test_endpoint(
        "List Templates",
        "GET",
        "/templates"
    )
    
    if result:
        templates = result.get("templates", [])
        print(f"\n  Available templates:")
        for t in templates[:5]:
            print(f"    - {t['id']}: {t['name']} ({t['category']})")
        if len(templates) > 5:
            print(f"    ... and {len(templates) - 5} more")
    
    # Test 2: Detect Tech Stack (Web App)
    result = test_endpoint(
        "Detect Tech Stack (Web Requirements)",
        "POST",
        "/detect",
        {"requirements": SAMPLE_REQUIREMENTS, "min_confidence": 0.1}
    )
    
    if result:
        print(f"\n  Reasons:")
        for r in result.get("reasons", []):
            print(f"    - {r}")
        print(f"\n  Alternatives:")
        for alt in result.get("alternative_templates", []):
            print(f"    - {alt['template_id']}: {alt['confidence']:.2%}")
    
    # Test 3: Detect Tech Stack (Simulation)
    result = test_endpoint(
        "Detect Tech Stack (Simulation Requirements)",
        "POST",
        "/detect",
        {"requirements": SIMULATION_REQUIREMENTS, "min_confidence": 0.1}
    )
    
    if result:
        print(f"\n  Reasons:")
        for r in result.get("reasons", []):
            print(f"    - {r}")
    
    # Test 4: Match Single Requirement
    result = test_endpoint(
        "Match Single Requirement",
        "POST",
        "/match",
        {"requirement_text": "The mobile app must support iOS and Android push notifications", "top_k": 3}
    )
    
    if result:
        print(f"\n  Top matches:")
        for m in result.get("matches", []):
            print(f"    - {m['template_name']}: {m['confidence']:.2%}")
    
    # Test 5: KG Status
    result = test_endpoint(
        "Knowledge Graph Status",
        "GET",
        "/kg/status"
    )
    
    # Test 6: Rebuild KG
    result = test_endpoint(
        "Rebuild Knowledge Graph",
        "POST",
        "/kg/rebuild",
        {"force": False}
    )
    
    if result and result.get("success"):
        print(f"\n  Templates indexed: {result.get('templates_indexed', 0)}")
        print(f"  Nodes created: {result.get('nodes_created', 0)}")
    
    # Test 7: Transform Requirements
    result = test_endpoint(
        "Transform Requirements (01-web-app)",
        "POST",
        "/transform",
        {"requirements": SAMPLE_REQUIREMENTS, "template_id": "01-web-app"}
    )
    
    if result and result.get("transformation_applied"):
        print(f"\n  Template: {result.get('template', {}).get('name', 'Unknown')}")
        print(f"  Stack: {', '.join(result.get('template', {}).get('stack', []))}")
    
    # Test 8: Full Pipeline Process
    result = test_endpoint(
        "Full Pipeline Processing",
        "POST",
        "/pipeline/process",
        {
            "validated_requirements": SAMPLE_REQUIREMENTS,
            "version": "v1",
            "selected_template": None  # Auto-detect
        }
    )
    
    if result:
        print(f"\n  Pipeline Result:")
        print(f"    Template: {result.get('template_id', 'Unknown')}")
        print(f"    Confidence: {result.get('confidence', 0):.2%}")
        print(f"    KG Updated: {result.get('kg_updated', False)}")
        print(f"    Traces Created: {result.get('kg_traces', 0)}")
    
    # Test 9: Categories
    result = test_endpoint(
        "List Categories",
        "GET",
        "/categories"
    )
    
    if result:
        print(f"\n  Categories: {', '.join(result.get('categories', []))}")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()