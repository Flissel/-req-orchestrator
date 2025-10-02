# -*- coding: utf-8 -*-
"""
Tools for arch_team agents.

This module provides FunctionTool wrappers for AutoGen agents to interact with
backend validation APIs and Qdrant knowledge graph.
"""
from __future__ import annotations

from .validation_tools import (
    evaluate_requirement,
    rewrite_requirement,
    suggest_improvements,
    detect_duplicates,
    VALIDATION_TOOLS,
)

__all__ = [
    "evaluate_requirement",
    "rewrite_requirement",
    "suggest_improvements",
    "detect_duplicates",
    "VALIDATION_TOOLS",
]
