# -*- coding: utf-8 -*-
"""
OpenAI Batch API Processor for Mass Requirements Validation

This module implements the OpenAI Batch API for processing large numbers of
requirements asynchronously with 50% cost savings.

The Batch API:
- Uploads a .jsonl file with many requests
- Processes them asynchronously (up to 24h window)
- Returns results when complete
- Costs 50% less than synchronous API calls

Usage:
    processor = OpenAIBatchProcessor()
    batch_id = await processor.submit_batch(requirements)
    status = await processor.get_batch_status(batch_id)
    results = await processor.get_batch_results(batch_id)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from backend.core import settings

logger = logging.getLogger(__name__)

# OpenAI client
try:
    from openai import OpenAI as _OpenAIClient
    OPENAI_AVAILABLE = True
except ImportError:
    _OpenAIClient = None
    OPENAI_AVAILABLE = False


@dataclass
class BatchJob:
    """Represents an OpenAI Batch job"""
    batch_id: str
    file_id: str
    status: str  # validating, in_progress, completed, failed, expired, cancelled
    request_count: int
    completed_count: int = 0
    failed_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    output_file_id: Optional[str] = None
    error_file_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class OpenAIBatchProcessor:
    """
    Processes requirements evaluation via OpenAI Batch API.
    
    The Batch API is ideal for:
    - 10+ requirements at once
    - Non-time-critical validation
    - Cost optimization (50% discount)
    
    Flow:
    1. Create JSONL file with evaluation requests
    2. Upload file to OpenAI
    3. Create batch job
    4. Poll status until complete
    5. Download and parse results
    """
    
    # Batch API configuration
    ENDPOINT = "/v1/chat/completions"
    COMPLETION_WINDOW = "24h"  # Max processing time
    
    # All 9 IEEE 29148 criteria
    CRITERIA = [
        "atomic", "clarity", "testability", "measurability", "concise",
        "unambiguous", "consistent_language", "design_independent", "purpose_independent"
    ]
    
    def __init__(self):
        """Initialize the batch processor."""
        self.client: Optional[Any] = None
        self.model = settings.OPENAI_MODEL
        self.active_batches: Dict[str, BatchJob] = {}
        
        if OPENAI_AVAILABLE:
            llm_config = settings.get_llm_config()
            api_key = llm_config.get("api_key", "")
            base_url = llm_config.get("base_url")
            
            # Batch API only works with OpenAI directly, not OpenRouter
            if api_key and not (base_url and "openrouter" in base_url.lower()):
                self.client = _OpenAIClient(api_key=api_key)
                logger.info("OpenAIBatchProcessor initialized with OpenAI API")
            elif base_url and "openrouter" in base_url.lower():
                logger.warning("OpenAIBatchProcessor: Batch API not available via OpenRouter, using direct OpenAI key required")
            else:
                logger.warning("OpenAIBatchProcessor: No API key configured")
        else:
            logger.warning("OpenAIBatchProcessor: openai module not available")
    
    def _get_system_prompt(self) -> str:
        """Generate the system prompt for batch evaluation."""
        criteria_descriptions = """
- atomic: Single testable statement (no AND/OR/comma)
- clarity: User story format with clear language
- testability: Has acceptance criteria (Given-When-Then)
- measurability: Quantifiable metrics with units
- concise: 10-30 words, no redundancy
- unambiguous: Single valid interpretation
- consistent_language: Consistent terminology
- design_independent: Specifies WHAT, not HOW
- purpose_independent: Single business purpose"""
        
        return f"""You are a requirements engineering expert evaluating software requirements against IEEE 29148 quality criteria.

Evaluate the provided requirement against ALL 9 criteria.

## Criteria:
{criteria_descriptions}

## Scoring:
- Score each criterion from 0.0 (fails) to 1.0 (perfect)
- Be objective and consistent

## Response Format (JSON only):
{{"scores": {{"atomic": 0.85, "clarity": 0.70, ...}}, "summary": "Brief assessment"}}

Return ONLY valid JSON, no additional text."""

    def _create_batch_request(
        self,
        requirement_id: str,
        requirement_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a single batch request entry in JSONL format."""
        return {
            "custom_id": requirement_id,
            "method": "POST",
            "url": self.ENDPOINT,
            "body": {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": json.dumps({
                        "requirement": requirement_text,
                        "context": context or {}
                    }, ensure_ascii=False)}
                ],
                "temperature": 0.0,
                "response_format": {"type": "json_object"}
            }
        }
    
    def _create_jsonl_file(
        self,
        requirements: List[Dict[str, Any]]
    ) -> str:
        """
        Create a JSONL file for batch processing.
        
        Args:
            requirements: List of {id, text, context} dicts
            
        Returns:
            Path to the created JSONL file
        """
        # Create temp file
        fd, path = tempfile.mkstemp(suffix=".jsonl", prefix="batch_req_")
        
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                for req in requirements:
                    req_id = req.get("id", f"REQ-{hash(req.get('text', ''))}")
                    req_text = req.get("text", "")
                    req_context = req.get("context", {})
                    
                    batch_entry = self._create_batch_request(
                        requirement_id=req_id,
                        requirement_text=req_text,
                        context=req_context
                    )
                    f.write(json.dumps(batch_entry, ensure_ascii=False) + "\n")
            
            logger.info(f"Created JSONL batch file: {path} with {len(requirements)} requests")
            return path
            
        except Exception as e:
            # Cleanup on error
            if os.path.exists(path):
                os.unlink(path)
            raise RuntimeError(f"Failed to create JSONL file: {e}")
    
    async def submit_batch(
        self,
        requirements: List[Dict[str, Any]],
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Submit requirements for batch processing.
        
        Args:
            requirements: List of {id, text, context} dicts
            metadata: Optional metadata to attach to the batch
            
        Returns:
            batch_id for status checking
            
        Raises:
            RuntimeError: If batch submission fails
        """
        if not self.client:
            raise RuntimeError("OpenAI client not initialized. Batch API requires direct OpenAI API key.")
        
        if not requirements:
            raise ValueError("No requirements provided for batch processing")
        
        logger.info(f"Submitting batch of {len(requirements)} requirements")
        
        # Step 1: Create JSONL file
        jsonl_path = self._create_jsonl_file(requirements)
        
        try:
            # Step 2: Upload file to OpenAI
            with open(jsonl_path, "rb") as f:
                file_response = await asyncio.to_thread(
                    self.client.files.create,
                    file=f,
                    purpose="batch"
                )
            
            file_id = file_response.id
            logger.info(f"Uploaded batch file: {file_id}")
            
            # Step 3: Create batch job
            batch_metadata = {
                "source": "requirements-orchestrator",
                "requirement_count": str(len(requirements)),
                "created_at": datetime.now().isoformat(),
                **(metadata or {})
            }
            
            batch_response = await asyncio.to_thread(
                self.client.batches.create,
                input_file_id=file_id,
                endpoint=self.ENDPOINT,
                completion_window=self.COMPLETION_WINDOW,
                metadata=batch_metadata
            )
            
            batch_id = batch_response.id
            
            # Track the batch
            self.active_batches[batch_id] = BatchJob(
                batch_id=batch_id,
                file_id=file_id,
                status=batch_response.status,
                request_count=len(requirements),
                metadata=batch_metadata
            )
            
            logger.info(f"Created batch job: {batch_id} (status: {batch_response.status})")
            return batch_id
            
        finally:
            # Cleanup temp file
            if os.path.exists(jsonl_path):
                os.unlink(jsonl_path)
    
    async def get_batch_status(self, batch_id: str) -> BatchJob:
        """
        Get current status of a batch job.
        
        Args:
            batch_id: The batch ID from submit_batch()
            
        Returns:
            BatchJob with current status
        """
        if not self.client:
            raise RuntimeError("OpenAI client not initialized")
        
        batch_response = await asyncio.to_thread(
            self.client.batches.retrieve,
            batch_id
        )
        
        job = BatchJob(
            batch_id=batch_response.id,
            file_id=batch_response.input_file_id,
            status=batch_response.status,
            request_count=batch_response.request_counts.total,
            completed_count=batch_response.request_counts.completed,
            failed_count=batch_response.request_counts.failed,
            output_file_id=batch_response.output_file_id,
            error_file_id=batch_response.error_file_id
        )
        
        if batch_response.completed_at:
            job.completed_at = datetime.fromtimestamp(batch_response.completed_at)
        
        # Update local tracking
        self.active_batches[batch_id] = job
        
        logger.debug(f"Batch {batch_id}: {job.status} ({job.completed_count}/{job.request_count} complete)")
        return job
    
    async def wait_for_completion(
        self,
        batch_id: str,
        poll_interval: float = 30.0,
        timeout: float = 3600.0  # 1 hour default
    ) -> BatchJob:
        """
        Wait for batch to complete with polling.
        
        Args:
            batch_id: The batch ID
            poll_interval: Seconds between status checks
            timeout: Max seconds to wait
            
        Returns:
            Completed BatchJob
            
        Raises:
            TimeoutError: If timeout exceeded
            RuntimeError: If batch failed
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            job = await self.get_batch_status(batch_id)
            
            if job.status == "completed":
                logger.info(f"Batch {batch_id} completed: {job.completed_count} succeeded, {job.failed_count} failed")
                return job
            
            if job.status in ("failed", "expired", "cancelled"):
                raise RuntimeError(f"Batch {batch_id} failed with status: {job.status}")
            
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(f"Batch {batch_id} timed out after {elapsed:.0f}s (status: {job.status})")
            
            # Log progress
            progress_pct = (job.completed_count / job.request_count * 100) if job.request_count > 0 else 0
            logger.info(f"Batch {batch_id}: {job.status} - {progress_pct:.1f}% ({job.completed_count}/{job.request_count})")
            
            await asyncio.sleep(poll_interval)
    
    async def get_batch_results(
        self,
        batch_id: str
    ) -> List[Dict[str, Any]]:
        """
        Download and parse batch results.
        
        Args:
            batch_id: The completed batch ID
            
        Returns:
            List of {id, scores, summary} for each requirement
        """
        if not self.client:
            raise RuntimeError("OpenAI client not initialized")
        
        # Get batch status to find output file
        job = await self.get_batch_status(batch_id)
        
        if job.status != "completed":
            raise RuntimeError(f"Batch {batch_id} not complete (status: {job.status})")
        
        if not job.output_file_id:
            raise RuntimeError(f"Batch {batch_id} has no output file")
        
        # Download output file
        file_content = await asyncio.to_thread(
            self.client.files.content,
            job.output_file_id
        )
        
        results = []
        
        # Parse JSONL output
        for line in file_content.text.split("\n"):
            if not line.strip():
                continue
            
            try:
                entry = json.loads(line)
                custom_id = entry.get("custom_id", "unknown")
                
                response = entry.get("response", {})
                body = response.get("body", {})
                
                if response.get("status_code") == 200:
                    # Parse the chat completion response
                    choices = body.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "{}")
                        try:
                            parsed = json.loads(content)
                            results.append({
                                "id": custom_id,
                                "scores": parsed.get("scores", {}),
                                "summary": parsed.get("summary", ""),
                                "success": True
                            })
                        except json.JSONDecodeError:
                            results.append({
                                "id": custom_id,
                                "scores": {},
                                "summary": "",
                                "success": False,
                                "error": "Failed to parse LLM response"
                            })
                else:
                    error_msg = body.get("error", {}).get("message", "Unknown error")
                    results.append({
                        "id": custom_id,
                        "scores": {},
                        "summary": "",
                        "success": False,
                        "error": error_msg
                    })
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse batch result line: {e}")
        
        logger.info(f"Parsed {len(results)} results from batch {batch_id}")
        return results
    
    async def process_requirements_batch(
        self,
        requirements: List[Dict[str, Any]],
        wait: bool = True,
        poll_interval: float = 30.0,
        timeout: float = 3600.0
    ) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
        """
        High-level method to process requirements via Batch API.
        
        Args:
            requirements: List of {id, text, context}
            wait: If True, wait for completion and return results
            poll_interval: Seconds between status checks
            timeout: Max wait time
            
        Returns:
            (batch_id, results) - results is None if wait=False
        """
        batch_id = await self.submit_batch(requirements)
        
        if not wait:
            return batch_id, None
        
        await self.wait_for_completion(
            batch_id,
            poll_interval=poll_interval,
            timeout=timeout
        )
        
        results = await self.get_batch_results(batch_id)
        return batch_id, results
    
    async def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a running batch job."""
        if not self.client:
            return False
        
        try:
            await asyncio.to_thread(
                self.client.batches.cancel,
                batch_id
            )
            logger.info(f"Cancelled batch {batch_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel batch {batch_id}: {e}")
            return False
    
    def get_active_batches(self) -> List[BatchJob]:
        """Get all actively tracked batch jobs."""
        return list(self.active_batches.values())


# Singleton instance
_processor_instance: Optional[OpenAIBatchProcessor] = None

def get_batch_processor() -> OpenAIBatchProcessor:
    """Get or create singleton OpenAIBatchProcessor instance."""
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = OpenAIBatchProcessor()
    return _processor_instance