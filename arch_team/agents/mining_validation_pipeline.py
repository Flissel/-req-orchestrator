# -*- coding: utf-8 -*-
"""
Mining + Validation Pipeline

Combines ChunkMinerAgent and RequirementsOrchestrator for end-to-end processing:
1. Upload documents (markdown, txt, pdf)
2. ChunkMinerAgent extracts requirements
3. RequirementsOrchestrator validates + improves
4. Output: Validated, quality-checked requirements

Usage:
    from arch_team.agents.mining_validation_pipeline import MiningValidationPipeline
    
    pipeline = MiningValidationPipeline()
    result = await pipeline.process_files(files)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
import json

from .chunk_miner import ChunkMinerAgent
from .requirements_orchestrator import (
    RequirementsOrchestrator,
    OrchestratorConfig,
    OrchestratorResult,
    WorkflowMode
)

logger = logging.getLogger("arch_team.mining_validation_pipeline")


@dataclass
class MiningResult:
    """Result from mining phase."""
    mined_count: int
    requirements: List[Dict[str, Any]]
    time_ms: int
    source_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Complete result from mining + validation pipeline."""
    success: bool
    pipeline_id: str
    
    # Mining phase
    mining_result: MiningResult
    
    # Validation phase
    validation_result: Optional[OrchestratorResult]
    
    # Final output
    final_requirements: List[Dict[str, Any]]
    passed_count: int
    failed_count: int
    improved_count: int
    
    # Statistics
    total_time_ms: int
    mining_time_ms: int
    validation_time_ms: int
    
    # Errors
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "success": self.success,
            "pipeline_id": self.pipeline_id,
            "mining": {
                "mined_count": self.mining_result.mined_count,
                "time_ms": self.mining_result.time_ms,
                "source_files": self.mining_result.source_files,
                "errors": self.mining_result.errors,
            },
            "validation": {
                "initial_pass_rate": self.validation_result.initial_pass_rate if self.validation_result else 0,
                "final_pass_rate": self.validation_result.final_pass_rate if self.validation_result else 0,
                "iterations": self.validation_result.total_iterations if self.validation_result else 0,
                "time_ms": self.validation_time_ms,
            } if self.validation_result else None,
            "final_requirements": self.final_requirements,
            "statistics": {
                "passed": self.passed_count,
                "failed": self.failed_count,
                "improved": self.improved_count,
                "total_time_ms": self.total_time_ms,
            },
            "error": self.error,
        }


class MiningValidationPipeline:
    """
    End-to-end pipeline for requirements mining and validation.
    
    Workflow:
    1. ChunkMinerAgent extracts requirements from documents
    2. RequirementsOrchestrator validates against 10 IEEE 29148 criteria
    3. DecisionMaker decides: SPLIT / REWRITE / ACCEPT / CLARIFY / REJECT
    4. Auto-improvement loop until quality threshold met
    5. Output: Validated requirements with scores and verdicts
    """
    
    def __init__(
        self,
        quality_threshold: float = 0.7,
        max_iterations: int = 3,
        auto_mode: bool = True,
        persist_to_db: bool = True,
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None
    ):
        """
        Initialize pipeline.
        
        Args:
            quality_threshold: Minimum score for pass (0.0-1.0)
            max_iterations: Maximum improvement iterations
            auto_mode: True for AUTO mode, False for MANUAL
            persist_to_db: Whether to save to SQLite manifest system
            progress_callback: Optional callback(stage, completed, total, message)
        """
        self.quality_threshold = quality_threshold
        self.max_iterations = max_iterations
        self.auto_mode = auto_mode
        self.persist_to_db = persist_to_db
        self.progress_callback = progress_callback
        
        # Pipeline ID for tracking
        self.pipeline_id = ""
    
    def _send_progress(self, stage: str, completed: int, total: int, message: str):
        """Send progress update."""
        if self.progress_callback:
            try:
                self.progress_callback(stage, completed, total, message)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
    
    async def process_files(
        self,
        files_or_texts: List[Union[str, bytes, Dict[str, Any]]],
        *,
        mining_model: Optional[str] = None,
        neighbor_refs: bool = False,
        correlation_id: Optional[str] = None,
    ) -> PipelineResult:
        """
        Process files through complete mining + validation pipeline.
        
        Args:
            files_or_texts: List of files/texts to process:
                - str: Raw text
                - bytes: Raw bytes
                - dict: {filename, data, content_type} or {text}
            mining_model: Model override for ChunkMiner
            neighbor_refs: Include neighbor chunks as evidence
            correlation_id: SSE session ID for streaming
        
        Returns:
            PipelineResult with all mining and validation data
        """
        import uuid
        
        start_time = time.time()
        self.pipeline_id = str(uuid.uuid4())[:8]
        
        logger.info(f"[{self.pipeline_id}] Starting Mining+Validation Pipeline")
        self._send_progress("init", 0, 3, "Starte Pipeline...")
        
        try:
            # ==========================================
            # PHASE 1: MINING
            # ==========================================
            self._send_progress("mining", 1, 3, "Extrahiere Requirements aus Dokumenten...")
            
            mining_start = time.time()
            mining_result = await self._run_mining(
                files_or_texts,
                model=mining_model,
                neighbor_refs=neighbor_refs
            )
            mining_time_ms = int((time.time() - mining_start) * 1000)
            
            logger.info(f"[{self.pipeline_id}] Mining: {mining_result.mined_count} requirements extracted in {mining_time_ms}ms")
            
            if mining_result.mined_count == 0:
                logger.warning(f"[{self.pipeline_id}] No requirements mined - pipeline complete")
                return PipelineResult(
                    success=True,
                    pipeline_id=self.pipeline_id,
                    mining_result=mining_result,
                    validation_result=None,
                    final_requirements=[],
                    passed_count=0,
                    failed_count=0,
                    improved_count=0,
                    total_time_ms=int((time.time() - start_time) * 1000),
                    mining_time_ms=mining_time_ms,
                    validation_time_ms=0,
                )
            
            # ==========================================
            # PHASE 2: VALIDATION + IMPROVEMENT
            # ==========================================
            self._send_progress("validation", 2, 3, f"Validiere {mining_result.mined_count} Requirements...")
            
            validation_start = time.time()
            validation_result = await self._run_validation(
                mining_result.requirements,
                correlation_id=correlation_id
            )
            validation_time_ms = int((time.time() - validation_start) * 1000)
            
            logger.info(f"[{self.pipeline_id}] Validation: {validation_result.final_pass_rate:.1%} pass rate in {validation_time_ms}ms")
            
            # ==========================================
            # PHASE 3: PERSISTENCE
            # ==========================================
            self._send_progress("persist", 3, 3, "Speichere validierte Requirements...")
            
            if self.persist_to_db:
                await self._persist_results(validation_result.requirements)
            
            # Calculate statistics
            passed = sum(1 for r in validation_result.requirements if r.get("_validation_score", 0) >= self.quality_threshold)
            failed = len(validation_result.requirements) - passed
            improved = sum(1 for r in validation_result.requirements if r.get("_rewritten"))
            
            total_time_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"[{self.pipeline_id}] Pipeline complete: {passed} passed, {failed} failed, {improved} improved ({total_time_ms}ms)")
            
            return PipelineResult(
                success=True,
                pipeline_id=self.pipeline_id,
                mining_result=mining_result,
                validation_result=validation_result,
                final_requirements=validation_result.requirements,
                passed_count=passed,
                failed_count=failed,
                improved_count=improved,
                total_time_ms=total_time_ms,
                mining_time_ms=mining_time_ms,
                validation_time_ms=validation_time_ms,
            )
            
        except Exception as e:
            logger.error(f"[{self.pipeline_id}] Pipeline failed: {e}", exc_info=True)
            
            return PipelineResult(
                success=False,
                pipeline_id=self.pipeline_id,
                mining_result=MiningResult(
                    mined_count=0,
                    requirements=[],
                    time_ms=0,
                    errors=[str(e)]
                ),
                validation_result=None,
                final_requirements=[],
                passed_count=0,
                failed_count=0,
                improved_count=0,
                total_time_ms=int((time.time() - start_time) * 1000),
                mining_time_ms=0,
                validation_time_ms=0,
                error=str(e),
            )
    
    async def _run_mining(
        self,
        files_or_texts: List[Union[str, bytes, Dict[str, Any]]],
        *,
        model: Optional[str] = None,
        neighbor_refs: bool = False,
    ) -> MiningResult:
        """Run ChunkMinerAgent to extract requirements."""
        start = time.time()
        errors: List[str] = []
        source_files: List[str] = []
        
        # Extract source filenames
        for item in files_or_texts:
            if isinstance(item, dict) and "filename" in item:
                source_files.append(item["filename"])
        
        try:
            miner = ChunkMinerAgent()
            
            # Run mining in thread pool (sync to async)
            requirements = await asyncio.to_thread(
                miner.mine_files_or_texts_collect,
                files_or_texts,
                model=model,
                neighbor_refs=neighbor_refs
            )
            
            return MiningResult(
                mined_count=len(requirements),
                requirements=requirements,
                time_ms=int((time.time() - start) * 1000),
                source_files=source_files,
                errors=errors,
            )
            
        except Exception as e:
            logger.error(f"Mining failed: {e}")
            errors.append(str(e))
            return MiningResult(
                mined_count=0,
                requirements=[],
                time_ms=int((time.time() - start) * 1000),
                source_files=source_files,
                errors=errors,
            )
    
    async def _run_validation(
        self,
        mined_requirements: List[Dict[str, Any]],
        *,
        correlation_id: Optional[str] = None,
    ) -> OrchestratorResult:
        """Run RequirementsOrchestrator to validate and improve."""
        # Convert ChunkMiner DTOs to Orchestrator format
        orchestrator_reqs = []
        for req in mined_requirements:
            orchestrator_reqs.append({
                "req_id": req.get("req_id") or req.get("reqId"),
                "title": req.get("title", ""),
                "tag": req.get("tag", "functional"),
                "evidence_refs": req.get("evidence_refs", []),
                # Pass through any extra fields
                "priority": req.get("priority"),
                "measurable_criteria": req.get("measurable_criteria"),
                "actors": req.get("actors"),
            })
        
        # Configure orchestrator
        config = OrchestratorConfig(
            quality_threshold=self.quality_threshold,
            max_iterations=self.max_iterations,
            mode=WorkflowMode.AUTO if self.auto_mode else WorkflowMode.MANUAL,
        )
        
        orchestrator = RequirementsOrchestrator(
            config=config,
            progress_callback=self.progress_callback
        )
        
        # Run validation
        result = await orchestrator.run(
            orchestrator_reqs,
            correlation_id=correlation_id,
        )
        
        return result
    
    async def _persist_results(
        self,
        validated_requirements: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Persist validated requirements to SQLite manifest system.

        Also saves evaluation criteria details for each requirement.
        """
        try:
            from backend.core import db as _db
            from backend.services.manifest_integration import create_manifests_from_chunkminer

            conn = _db.get_db()
            try:
                # 1. Create manifests (existing)
                manifest_ids = create_manifests_from_chunkminer(conn, validated_requirements)
                logger.info(f"[{self.pipeline_id}] Created {len(manifest_ids)} manifests")

                # 2. NEW: Persist evaluation criteria for each requirement
                evaluations_saved = 0
                for req in validated_requirements:
                    evaluation = req.get("evaluation", [])
                    if not evaluation:
                        continue

                    # Get requirement text
                    req_text = req.get("title") or req.get("text", "")
                    if not req_text:
                        continue

                    # Get overall score and verdict
                    score = req.get("score") or req.get("_validation_score", 0.0)
                    verdict = req.get("verdict", "fail")
                    if score >= self.quality_threshold:
                        verdict = "pass"

                    try:
                        eval_id = _db.persist_evaluation_with_details(
                            conn=conn,
                            requirement_text=req_text,
                            score=score,
                            verdict=verdict,
                            details=evaluation,
                            model="mining_pipeline",
                            latency_ms=req.get("processing_time_ms", 0),
                        )
                        evaluations_saved += 1

                        # Store eval_id back on requirement for reference
                        req["_evaluation_id"] = eval_id

                    except Exception as eval_err:
                        logger.warning(f"Failed to persist evaluation for {req.get('req_id')}: {eval_err}")

                logger.info(f"[{self.pipeline_id}] Saved {evaluations_saved} evaluation records with criteria details")
                return manifest_ids
            finally:
                conn.close()

        except Exception as e:
            logger.warning(f"Failed to persist results: {e}")
            return []


# Convenience function for simple usage
async def mine_and_validate(
    files_or_texts: List[Union[str, bytes, Dict[str, Any]]],
    *,
    quality_threshold: float = 0.7,
    max_iterations: int = 3,
    auto_mode: bool = True,
    persist_to_db: bool = True,
) -> PipelineResult:
    """
    Convenience function for end-to-end mining + validation.
    
    Example:
        result = await mine_and_validate([
            {"filename": "reqs.md", "data": open("reqs.md", "rb").read()}
        ])
        
        for req in result.final_requirements:
            print(f"{req['req_id']}: {req['title']} (score: {req.get('_validation_score', 'N/A')})")
    """
    pipeline = MiningValidationPipeline(
        quality_threshold=quality_threshold,
        max_iterations=max_iterations,
        auto_mode=auto_mode,
        persist_to_db=persist_to_db,
    )
    
    return await pipeline.process_files(files_or_texts)