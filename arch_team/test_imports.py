#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test imports for requirements validation implementation."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("Testing imports...")

# Test 1: Tools
try:
    from arch_team.tools.validation_tools import VALIDATION_TOOLS
    print(f"[OK] Tools loaded: {len(VALIDATION_TOOLS)} tools")
except Exception as e:
    print(f"[FAIL] Tools import failed: {e}")

# Test 2: Prompts
try:
    from arch_team.agents.prompts import requirements_operator_prompt
    from arch_team.agents.prompts import qa_validator_prompt
    from arch_team.agents.prompts import user_clarification_prompt
    total_chars = len(requirements_operator_prompt.PROMPT) + len(qa_validator_prompt.PROMPT) + len(user_clarification_prompt.PROMPT)
    print(f"[OK] Prompts loaded (total {total_chars} chars)")
except Exception as e:
    print(f"[FAIL] Prompts import failed: {e}")

# Test 3: Agent (may fail if AutoGen not installed)
try:
    from arch_team.agents.requirements_agent import RequirementsValidationAgent
    print("[OK] Agent import OK")
except ImportError as e:
    print(f"[WARN] Agent import failed (AutoGen not installed?): {str(e)[:80]}...")
except Exception as e:
    print(f"[FAIL] Agent import failed: {e}")

print("\nImport tests completed!")
