#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Script for Requirements Orchestrator

Tests the complete iterative workflow:
Validate → Rewrite → Clarify → Loop

Usage:
    python scripts/test_requirements_orchestrator.py [input_file] [max_iterations]
    
Examples:
    # Test with existing validated requirements
    python scripts/test_requirements_orchestrator.py debug/validated_requirements_20251126_135652.json 3
    
    # Test with sample requirements
    python scripts/test_requirements_orchestrator.py sample 5
"""

import asyncio
import json
import logging
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_orchestrator")


# Sample requirements for testing
SAMPLE_REQUIREMENTS = [
    {
        "req_id": "REQ-TEST-001",
        "title": "The system should be fast",
        "tag": "performance"
    },
    {
        "req_id": "REQ-TEST-002",
        "title": "Users can login",
        "tag": "functional"
    },
    {
        "req_id": "REQ-TEST-003",
        "title": "The application must be secure and easy to use and also handle errors properly",
        "tag": "security"
    },
    {
        "req_id": "REQ-TEST-004",
        "title": "Data should be stored somewhere",
        "tag": "functional"
    },
    {
        "req_id": "REQ-TEST-005",
        "title": "The system shall process all incoming requests within an acceptable timeframe",
        "tag": "performance"
    }
]


def load_requirements(source: str) -> list:
    """Load requirements from file or use samples."""
    if source == "sample":
        logger.info("Using sample requirements")
        return SAMPLE_REQUIREMENTS
    
    path = Path(source)
    if not path.exists():
        logger.error(f"File not found: {source}")
        sys.exit(1)
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle different formats
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        # Check for requirements in various places
        if "requirements" in data:
            return data["requirements"]
        elif "validation_results" in data:
            # Extract from validation results
            results = data["validation_results"]
            if "details" in results:
                return [
                    {
                        "req_id": r.get("req_id"),
                        "title": r.get("title"),
                        "tag": r.get("tag")
                    }
                    for r in results["details"]
                ]
    
    logger.error(f"Could not parse requirements from {source}")
    sys.exit(1)


async def run_orchestrator_test(
    requirements: list,
    max_iterations: int = 3,
    wait_for_answers: bool = False
):
    """Run the requirements orchestrator test."""
    from arch_team.agents.requirements_orchestrator import (
        RequirementsOrchestrator,
        OrchestratorConfig
    )
    
    logger.info("=" * 60)
    logger.info("REQUIREMENTS ORCHESTRATOR TEST")
    logger.info("=" * 60)
    logger.info(f"Input: {len(requirements)} requirements")
    logger.info(f"Max iterations: {max_iterations}")
    logger.info(f"Wait for answers: {wait_for_answers}")
    logger.info("=" * 60)
    
    # Print sample requirements
    logger.info("\nSample requirements:")
    for i, req in enumerate(requirements[:3]):
        logger.info(f"  {i+1}. [{req.get('req_id')}] {req.get('title', '')[:60]}...")
    if len(requirements) > 3:
        logger.info(f"  ... and {len(requirements) - 3} more")
    
    # Create configuration
    config = OrchestratorConfig(
        quality_threshold=0.7,
        max_iterations=max_iterations,
        max_rewrite_attempts=3,
        validation_concurrent=5,
        rewrite_concurrent=3,
        clarification_concurrent=5,
        auto_fix_threshold=0.5,
        wait_for_answers_timeout=60  # Short timeout for testing
    )
    
    # Create orchestrator
    orchestrator = RequirementsOrchestrator(config=config)
    
    # Run workflow
    logger.info("\n🚀 Starting orchestrator workflow...")
    start_time = datetime.now()
    
    try:
        result = await orchestrator.run(
            requirements=requirements,
            correlation_id=None,  # No SSE for testing
            wait_for_answers=wait_for_answers
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Print results
        logger.info("\n" + "=" * 60)
        logger.info("ORCHESTRATOR RESULTS")
        logger.info("=" * 60)
        logger.info(f"Success: {'✅ YES' if result.success else '❌ NO'}")
        logger.info(f"Workflow ID: {result.workflow_id}")
        logger.info(f"Duration: {duration:.1f}s ({result.total_time_ms}ms)")
        logger.info(f"Total iterations: {result.total_iterations}")
        logger.info(f"Initial pass rate: {result.initial_pass_rate:.1%}")
        logger.info(f"Final pass rate: {result.final_pass_rate:.1%}")
        logger.info(f"Improved: {'✅' if result.improved else '❌'} ({(result.final_pass_rate - result.initial_pass_rate):.1%})")
        
        # Iteration details
        if result.iterations:
            logger.info("\n📊 Iteration Details:")
            for it in result.iterations:
                logger.info(f"  Iteration {it.iteration}:")
                logger.info(f"    - Passed: {it.passed_count}/{it.total_requirements}")
                logger.info(f"    - Rewritten: {it.rewritten_count}")
                logger.info(f"    - Questions: {it.clarification_count}")
                logger.info(f"    - Answered: {it.answered_count}")
        
        # Pending questions
        if result.pending_questions:
            logger.info(f"\n❓ Pending Questions ({len(result.pending_questions)}):")
            for q in result.pending_questions[:5]:
                logger.info(f"  - [{q.get('criterion')}] {q.get('question_text', '')[:50]}...")
            if len(result.pending_questions) > 5:
                logger.info(f"  ... and {len(result.pending_questions) - 5} more")
        
        # Error
        if result.error:
            logger.error(f"\n⚠️ Error: {result.error}")
        
        # Save results
        output_dir = Path("./debug")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f"orchestrator_result_{timestamp}.json"
        
        # Prepare JSON-serializable result
        json_result = {
            "success": result.success,
            "workflow_id": result.workflow_id,
            "total_iterations": result.total_iterations,
            "initial_pass_rate": result.initial_pass_rate,
            "final_pass_rate": result.final_pass_rate,
            "improved": result.improved,
            "total_time_ms": result.total_time_ms,
            "error": result.error,
            "iterations": [
                {
                    "iteration": it.iteration,
                    "total_requirements": it.total_requirements,
                    "passed_count": it.passed_count,
                    "failed_count": it.failed_count,
                    "rewritten_count": it.rewritten_count,
                    "clarification_count": it.clarification_count,
                    "answered_count": it.answered_count,
                    "validation_time_ms": it.validation_time_ms,
                    "rewrite_time_ms": it.rewrite_time_ms,
                    "clarification_time_ms": it.clarification_time_ms
                }
                for it in result.iterations
            ],
            "pending_questions": result.pending_questions,
            "final_requirements": result.requirements
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n📁 Results saved to: {output_file}")
        
        return result
        
    except Exception as e:
        logger.error(f"Orchestrator failed: {e}", exc_info=True)
        raise


async def test_individual_components():
    """Test individual components before full orchestrator."""
    logger.info("\n" + "=" * 60)
    logger.info("COMPONENT TESTS")
    logger.info("=" * 60)
    
    # Test 1: ClarificationAgent
    logger.info("\n🔍 Testing ClarificationAgent...")
    try:
        from arch_team.agents.clarification_agent import (
            ClarificationAgent,
            ClarificationTask
        )
        
        agent = ClarificationAgent()
        
        # Create a test task with failed criteria
        task = ClarificationTask(
            req_id="REQ-TEST",
            requirement_text="The system should be fast",
            validation_results=[
                {
                    "criterion": "measurability",
                    "score": 0.2,
                    "passed": False,
                    "feedback": "No quantifiable metrics defined"
                },
                {
                    "criterion": "testability",
                    "score": 0.3,
                    "passed": False,
                    "feedback": "Missing acceptance criteria"
                }
            ],
            overall_score=0.25
        )
        
        result = await agent.analyze(task)
        
        logger.info(f"  ✅ ClarificationAgent: Generated {len(result.questions)} questions")
        for q in result.questions:
            logger.info(f"    - [{q.criterion}] {q.question_text[:50]}...")
        
    except Exception as e:
        logger.error(f"  ❌ ClarificationAgent failed: {e}")
    
    # Test 2: ClarificationService
    logger.info("\n🗄️ Testing ClarificationService...")
    try:
        from backend.services.clarification_service import ClarificationService
        from backend.core import db as _db
        
        # Initialize database
        _db.init_db()
        
        service = ClarificationService()
        conn = _db.get_db()
        
        try:
            # Create a test question
            qid = service.create_question(
                conn,
                requirement_id="REQ-TEST-SERVICE",
                criterion="measurability",
                question_text="Was ist der erwartete maximale Wert?",
                suggested_answers=["< 100ms", "< 500ms", "< 1s"]
            )
            
            # Get summary
            summary = service.get_questions_summary(conn)
            
            logger.info(f"  ✅ ClarificationService: Created question {qid}")
            logger.info(f"    Summary: {summary.get('total', 0)} total, {summary.get('pending', 0)} pending")
            
        finally:
            conn.close()
        
    except Exception as e:
        logger.error(f"  ❌ ClarificationService failed: {e}")
    
    logger.info("\n" + "=" * 60)


async def main():
    """Main entry point."""
    # Parse arguments
    args = sys.argv[1:]
    
    if len(args) == 0 or args[0] in ["-h", "--help"]:
        print(__doc__)
        sys.exit(0)
    
    input_source = args[0]
    max_iterations = int(args[1]) if len(args) > 1 else 3
    wait_for_answers = len(args) > 2 and args[2].lower() in ["true", "1", "yes"]
    
    # Load requirements
    requirements = load_requirements(input_source)
    
    # Initialize database
    from backend.core import db as _db
    _db.init_db()
    
    # Run component tests first
    await test_individual_components()
    
    # Run full orchestrator
    await run_orchestrator_test(
        requirements=requirements,
        max_iterations=max_iterations,
        wait_for_answers=wait_for_answers
    )


if __name__ == "__main__":
    asyncio.run(main())