#!/usr/bin/env python
"""
Test script to verify criterion specialists use OpenRouter/Claude Haiku configuration.
"""
import os
import sys

# Load environment variables
from dotenv import load_dotenv
load_dotenv(override=True)

# Import the criterion specialists
from arch_team.agents.criterion_specialists import get_all_specialists
from backend.core import settings

def main():
    print("=" * 80)
    print("OpenRouter / Claude Haiku 4.5 Integration Test")
    print("=" * 80)
    print()

    # Check environment configuration
    print("1. Environment Configuration:")
    print(f"   LLM_PROVIDER: {os.environ.get('LLM_PROVIDER', 'NOT SET')}")
    print(f"   OPENAI_MODEL: {os.environ.get('OPENAI_MODEL', 'NOT SET')}")
    print(f"   OPENROUTER_API_KEY present: {bool(os.environ.get('OPENROUTER_API_KEY'))}")
    print(f"   OPENAI_API_KEY present: {bool(os.environ.get('OPENAI_API_KEY'))}")
    print()

    # Check settings.get_llm_config()
    print("2. Backend Settings (get_llm_config):")
    llm_config = settings.get_llm_config()
    print(f"   API Key present: {bool(llm_config.get('api_key'))}")
    print(f"   Base URL: {llm_config.get('base_url')}")
    print(f"   Model: {llm_config.get('model')}")
    print()

    # Initialize criterion specialists and check their configuration
    print("3. Criterion Specialists Initialization:")
    specialists = get_all_specialists()
    print(f"   Total specialists loaded: {len(specialists)}")
    print()

    # Check first specialist in detail
    if specialists:
        first_specialist = specialists[0]
        print(f"4. First Specialist Details ({first_specialist.__class__.__name__}):")
        print(f"   Criterion: {first_specialist.criterion_name}")
        print(f"   Has client: {hasattr(first_specialist, 'client') and first_specialist.client is not None}")

        if hasattr(first_specialist, 'client') and first_specialist.client:
            client = first_specialist.client
            print(f"   Client API key starts with: {str(client.api_key)[:10]}...")
            if hasattr(client, 'base_url'):
                print(f"   Client base_url: {client.base_url}")
            else:
                print(f"   Client base_url: NOT SET (using OpenAI default)")

            # Determine provider
            if hasattr(client, 'base_url') and client.base_url and 'openrouter' in str(client.base_url):
                print(f"   ✅ USING OPENROUTER")
            else:
                print(f"   ❌ NOT USING OPENROUTER (likely using OpenAI)")
        print()

    print("=" * 80)
    print("Test Complete")
    print("=" * 80)

if __name__ == "__main__":
    main()
