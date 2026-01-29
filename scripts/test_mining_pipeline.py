#!/usr/bin/env python3
"""Test script for the Mining + Validation Pipeline API."""

import asyncio
import json
import time
import httpx


async def test_pipeline():
    """Test the /api/v1/mining/validate endpoint."""
    print("=" * 60)
    print("Mining + Validation Pipeline Test")
    print("=" * 60)
    
    url = "http://localhost:8087/api/v1/mining/validate"
    
    payload = {
        "files": [
            {
                "filename": "test.md",
                "content": """# Test Requirements

## Functional Requirements

- REQ-F001: Das System soll eine Login-Funktion mit Email und Passwort bieten
- REQ-F002: Die App speichert Nutzerdaten verschluesselt in einer SQLite-Datenbank
- REQ-F003: Das System muss alle Benutzereingaben validieren

## Non-Functional Requirements

- REQ-NF001: Performance muss unter 2 Sekunden Reaktionszeit liegen
- REQ-NF002: Das System soll 99.9% Verfuegbarkeit garantieren
"""
            }
        ],
        "quality_threshold": 0.7,
        "max_iterations": 2,
        "auto_mode": True,
        "persist_to_db": False  # Don't persist for testing
    }
    
    print(f"\n📤 Sende Request an {url}")
    start = time.time()
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload)
    
    elapsed = time.time() - start
    print(f"⏱️  Response in {elapsed:.2f}s")
    print(f"📊 Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("\n✅ Pipeline erfolgreich!")
        print("-" * 40)
        
        # Mining stats
        mining = result.get("mining", {})
        print(f"⛏️  Mining: {mining.get('mined_count', 0)} Requirements ({mining.get('time_ms', 0)}ms)")
        
        # Validation stats
        validation = result.get("validation", {})
        if validation:
            print(f"✅ Validation: {validation.get('initial_pass_rate', 0)*100:.0f}% → {validation.get('final_pass_rate', 0)*100:.0f}% Pass-Rate")
            print(f"🔄 {validation.get('iterations', 0)} Iterationen ({validation.get('time_ms', 0)}ms)")
        
        # Statistics
        stats = result.get("statistics", {})
        print(f"📈 Passed: {stats.get('passed', 0)} | Failed: {stats.get('failed', 0)} | Improved: {stats.get('improved', 0)}")
        print(f"⏱️  Total: {stats.get('total_time_ms', 0)}ms")
        
        # Requirements
        reqs = result.get("final_requirements", [])
        print(f"\n📋 {len(reqs)} Requirements:")
        for req in reqs[:5]:  # Show first 5
            score = req.get("_validation_score", req.get("score", 0))
            verdict = "✅" if score >= 0.7 else "❌"
            title = req.get("title", "")[:60]
            print(f"  {verdict} {req.get('req_id', 'N/A')}: {title}... (Score: {score:.2f})")
        
        if len(reqs) > 5:
            print(f"  ... und {len(reqs) - 5} weitere")
            
    else:
        print(f"\n❌ Fehler: {response.status_code}")
        try:
            error = response.json()
            print(f"   Message: {error.get('message', 'Unknown error')}")
            print(f"   Error: {error.get('error', 'N/A')}")
        except:
            print(f"   Raw: {response.text[:500]}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(test_pipeline())