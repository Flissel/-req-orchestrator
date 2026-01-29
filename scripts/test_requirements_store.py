#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Requirements Store API.
Loads requirements from debug JSON and stores to Qdrant via API.
"""
import json
import requests
import sys

def main():
    # Load debug requirements
    debug_file = 'debug/requirements_20251128_161731.json'
    
    try:
        with open(debug_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Debug file not found: {debug_file}")
        sys.exit(1)
    
    requirements = data.get('requirements', [])
    print(f"Loaded {len(requirements)} requirements from {debug_file}")
    
    if not requirements:
        print("ERROR: No requirements found")
        sys.exit(1)
    
    # Store to API
    api_url = 'http://localhost:8087/api/requirements/store'
    
    payload = {
        'requirements': requirements,
        'version': 'auto',
        'metadata': {'source': 'port_manager_requirements.md'}
    }
    
    print(f"\nStoring to {api_url}...")
    
    try:
        response = requests.post(api_url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        print(f"\nResult:")
        print(f"  Success: {result.get('success')}")
        print(f"  Version: {result.get('version')}")
        print(f"  Collection: {result.get('collection')}")
        print(f"  Count: {result.get('count')}")
        print(f"  Stored at: {result.get('stored_at')}")
        
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text[:500]}")
        sys.exit(1)
    
    # Verify by listing versions
    print("\n--- Verifying stored versions ---")
    versions_response = requests.get('http://localhost:8087/api/requirements/versions')
    print(f"Versions: {versions_response.json()}")

if __name__ == '__main__':
    main()