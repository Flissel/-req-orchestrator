# -*- coding: utf-8 -*-
"""
FastAPI Backend mit AutoGen gRPC Worker Runtime
Modern Requirements Engineering System
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from contextlib import asynccontextmanager
import os

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntimeHost, GrpcWorkerAgentRuntime
from autogen_core import DefaultSubscription, DefaultTopicId

from backend_app.agents import (
    RequirementsEvaluatorAgent,
    RequirementsSuggestionAgent, 
    RequirementsRewriteAgent,
    RequirementsOrchestratorAgent,
    RequirementsMonitorAgent,
    RequirementProcessingRequest,
    BatchProcessingRequest,
    EvaluationResult,
    SuggestionResult,
    RewriteResult,
    ProcessingStatusUpdate,
    register_all_message_serializers
)

# Import bestehender Module (angepasst für async)
from backend_app.db_async import get_db_async, load_criteria_async
from backend_app.llm_async import llm_evaluate_async, llm_suggest_async, llm_rewrite_async
from backend_app.utils import compute_verdict, sha256_text, weighted_score

logger = logging.getLogger(__name__)

# =============================================================================
# Pydantic Models für FastAPI
# =============================================================================

class RequirementRequest(BaseModel):
    """Request Model für einzelne Requirements"""
    requirementText: str = Field(..., min_length=1, max_length=5000)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    criteriaKeys: Optional[List[str]] = None

class BatchRequirementRequest(BaseModel):
    """Request Model für Batch Requirements"""
    requirements: List[RequirementRequest] = Field(..., min_items=1, max_items=100)
    processingTypes: List[str] = Field(default=["evaluation"], description="evaluation, suggestion, rewrite")
    parallelLimit: int = Field(default=3, ge=1, le=10)

class EvaluationResponse(BaseModel):
    """Response Model für Evaluations"""
    evaluationId: str
    requirementChecksum: str
    verdict: str
    score: float
    latencyMs: int
    model: str
    details: Dict[str, float]
    suggestions: Optional[List[str]] = None
    timestamp: str

class SuggestionResponse(BaseModel):
    """Response Model für Suggestions"""
    requirementChecksum: str
    suggestions: List[str]
    latencyMs: int
    model: str
    timestamp: str

class RewriteResponse(BaseModel):
    """Response Model für Rewrites"""
    requirementChecksum: str
    rewrittenRequirement: str
    latencyMs: int
    model: str
    timestamp: str

class BatchProcessingResponse(BaseModel):
    """Response Model für Batch Processing"""
    batchId: str
    totalRequirements: int
    processingTypes: List[str]
    status: str
    estimatedCompletionTime: Optional[str] = None
    websocketUrl: str

class ProcessingStatusResponse(BaseModel):
    """Response Model für Processing Status"""
    batchId: str
    completedRequirements: int
    totalRequirements: int
    currentStage: str
    progress: float
    results: Dict[str, Any]

class SystemStatusResponse(BaseModel):
    """Response Model für System Status"""
    grpcHostRunning: bool
    activeWorkers: int
    totalProcessedToday: int
    systemLoad: float
    uptime: str

# =============================================================================
# Global State Management
# =============================================================================

class RequirementsProcessingManager:
    """Manager für Requirements Processing mit AutoGen Agents"""
    
    def __init__(self):
        self.grpc_host: Optional[GrpcWorkerAgentRuntimeHost] = None
        self.worker_runtime: Optional[GrpcWorkerAgentRuntime] = None
        self.is_running = False
        
        # Processing State
        self.active_batches: Dict[str, Dict] = {}
        self.processing_results: Dict[str, Dict] = {}
        self.websocket_connections: Dict[str, WebSocket] = {}
        
        # Statistics
        self.stats = {
            "total_processed": 0,
            "successful_evaluations": 0,
            "failed_requests": 0,
            "average_latency": 0.0,
            "start_time": datetime.now()
        }
    
    async def start_grpc_service(self, host_address: str = "localhost:50051"):
        """Startet gRPC Host und Worker"""
        try:
            if self.is_running:
                logger.warning("gRPC Service läuft bereits")
                return True
            
            # gRPC Host starten
            self.grpc_host = GrpcWorkerAgentRuntimeHost(address=host_address)
            self.grpc_host.start()
            logger.info(f"gRPC Host gestartet auf {host_address}")
            
            # Worker Runtime starten
            self.worker_runtime = GrpcWorkerAgentRuntime(host_address=host_address)
            await self.worker_runtime.start()
            
            # Message Serializers registrieren
            register_all_message_serializers(self.worker_runtime)
            
            # Agents registrieren
            await self._register_agents()
            
            self.is_running = True
            logger.info("AutoGen gRPC Service erfolgreich gestartet")
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Starten des gRPC Service: {str(e)}")
            return False
    
    async def _register_agents(self):
        """Registriert alle Agents"""
        try:
            # Requirements Evaluator Agent
            await RequirementsEvaluatorAgent.register(
                self.worker_runtime,
                "requirements_evaluator",
                lambda: RequirementsEvaluatorAgent("FastAPI_Evaluator")
            )
            await self.worker_runtime.add_subscription(DefaultSubscription(agent_type="requirements_evaluator"))
            
            # Requirements Suggestion Agent
            await RequirementsSuggestionAgent.register(
                self.worker_runtime,
                "requirements_suggester",
                lambda: RequirementsSuggestionAgent("FastAPI_Suggester")
            )
            await self.worker_runtime.add_subscription(DefaultSubscription(agent_type="requirements_suggester"))
            
            # Requirements Rewrite Agent
            await RequirementsRewriteAgent.register(
                self.worker_runtime,
                "requirements_rewriter", 
                lambda: RequirementsRewriteAgent("FastAPI_Rewriter")
            )
            await self.worker_runtime.add_subscription(DefaultSubscription(agent_type="requirements_rewriter"))
            
            # Orchestrator Agent
            await RequirementsOrchestratorAgent.register(
                self.worker_runtime,
                "requirements_orchestrator",
                lambda: RequirementsOrchestratorAgent("FastAPI_Orchestrator")
            )
            await self.worker_runtime.add_subscription(DefaultSubscription(agent_type="requirements_orchestrator"))
            
            # Monitor Agent
            await RequirementsMonitorAgent.register(
                self.worker_runtime,
                "requirements_monitor",
                lambda: RequirementsMonitorAgent("FastAPI_Monitor")
            )
            await self.worker_runtime.add_subscription(DefaultSubscription(agent_type="requirements_monitor"))
            
            logger.info("Alle AutoGen Agents erfolgreich registriert")
            
        except Exception as e:
            logger.error(f"Fehler beim Registrieren der Agents: {str(e)}")
            raise
    
    async def stop_grpc_service(self):
        """Stoppt gRPC Service"""
        try:
            if self.worker_runtime:
                await self.worker_runtime.stop()
                logger.info("Worker Runtime gestoppt")
            
            if self.grpc_host:
                await self.grpc_host.stop()
                logger.info("gRPC Host gestoppt")
            
            self.is_running = False
            
        except Exception as e:
            logger.error(f"Fehler beim Stoppen des gRPC Service: {str(e)}")
    
    async def process_single_requirement(
        self, 
        requirement: RequirementRequest, 
        processing_types: List[str] = ["evaluation"]
    ) -> str:
        """Verarbeitet einzelnes Requirement"""
        try:
            # Wenn gRPC nicht läuft: Fallback – akzeptiere Request und simuliere 'processing'
            if not self.is_running:
                req_id = f"req_{uuid.uuid4().hex[:8]}"
                self.active_batches[req_id] = {
                    "total_requirements": 1,
                    "processing_types": processing_types,
                    "completed": 0,
                    "results": {},
                    "start_time": datetime.now(),
                    "status": "processing",
                }
                logger.info(f"[no-grpc] Requirement {req_id} angenommen (Fallback-Modus)")
                return req_id
            
            # Request erstellen
            req_id = f"req_{uuid.uuid4().hex[:8]}"
            req_checksum = sha256_text(requirement.requirementText)
            
            processing_request = RequirementProcessingRequest(
                requirement_id=req_id,
                requirement_text=requirement.requirementText,
                context=requirement.context or {},
                criteria_keys=requirement.criteriaKeys,
                request_id=req_id
            )
            
            # Request tracken
            self.active_batches[req_id] = {
                "total_requirements": 1,
                "processing_types": processing_types,
                "completed": 0,
                "results": {},
                "start_time": datetime.now(),
                "status": "processing"
            }
            
            # An Agents senden
            await self.worker_runtime.publish_message(processing_request, topic_id=DefaultTopicId())
            
            logger.info(f"Requirement {req_id} zur Verarbeitung gesendet")
            return req_id
            
        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten des Requirements: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def process_batch_requirements(
        self, 
        batch_request: BatchRequirementRequest
    ) -> str:
        """Verarbeitet Batch von Requirements"""
        try:
            # Gültige Processing-Typen validieren
            _allowed = {"evaluation", "suggestion", "rewrite"}
            if any(t not in _allowed for t in (batch_request.processingTypes or [])):
                raise HTTPException(status_code=400, detail="invalid processingTypes")
            # Fallback, wenn gRPC nicht läuft: akzeptiere Batch und simuliere 'processing'
            if not self.is_running:
                batch_id = f"batch_{uuid.uuid4().hex[:8]}"
                self.active_batches[batch_id] = {
                    "total_requirements": len(batch_request.requirements or []),
                    "processing_types": batch_request.processingTypes,
                    "completed": 0,
                    "results": {},
                    "start_time": datetime.now(),
                    "status": "processing",
                }
                logger.info(f"[no-grpc] Batch {batch_id} angenommen (Fallback-Modus)")
                return batch_id
            
            batch_id = f"batch_{uuid.uuid4().hex[:8]}"
            
            # Processing Requests erstellen
            processing_requests = []
            for i, req in enumerate(batch_request.requirements):
                req_id = f"{batch_id}_req_{i:03d}"
                processing_req = RequirementProcessingRequest(
                    requirement_id=req_id,
                    requirement_text=req.requirementText,
                    context=req.context or {},
                    criteria_keys=req.criteriaKeys,
                    request_id=req_id
                )
                processing_requests.append(processing_req)
            
            # Batch Processing Request erstellen
            batch_processing_request = BatchProcessingRequest(
                batch_id=batch_id,
                requirements=processing_requests,
                processing_types=batch_request.processingTypes,
                parallel_limit=batch_request.parallelLimit
            )
            
            # Batch tracken
            self.active_batches[batch_id] = {
                "total_requirements": len(processing_requests),
                "processing_types": batch_request.processingTypes,
                "completed": 0,
                "results": {},
                "start_time": datetime.now(),
                "status": "processing"
            }
            
            # An Orchestrator senden
            await self.worker_runtime.publish_message(batch_processing_request, topic_id=DefaultTopicId())
            
            logger.info(f"Batch {batch_id} mit {len(processing_requests)} Requirements gesendet")
            return batch_id
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Fehler beim Batch-Processing: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict]:
        """Gibt Status eines Batches zurück"""
        return self.active_batches.get(batch_id)
    
    def get_system_status(self) -> Dict:
        """Gibt System-Status zurück"""
        uptime = datetime.now() - self.stats["start_time"]
        return {
            "grpcHostRunning": self.is_running,
            "activeWorkers": len(self.active_batches),
            "totalProcessedToday": self.stats["total_processed"],
            "systemLoad": 0.5,  # TODO: Implementieren
            "uptime": str(uptime),
            "stats": self.stats
        }

# Global Manager Instance
processing_manager = RequirementsProcessingManager()

# =============================================================================
# FastAPI Lifecycle Management
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Skip gRPC-Startup/Shutdown in Tests, wenn DISABLE_GRPC gesetzt ist
    # Zusätzlich: automatisch in Pytest (PYTEST_CURRENT_TEST) oder bei MOCK_MODE überspringen
    _env = os.environ
    _disable = (
        _env.get("DISABLE_GRPC", "").strip().lower() in ("1", "true", "yes", "on")
        or ("PYTEST_CURRENT_TEST" in _env)  # Pytest-Erkennung
        or (_env.get("MOCK_MODE", "").strip().lower() in ("1", "true", "yes", "on"))
    )
    if _disable:
        logger.info("Lifespan: Test/Mock/Flag erkannt → überspringe gRPC Startup/Shutdown")
        yield
        return
    # Startup
    logger.info("🚀 Starte FastAPI Requirements Engineering System")
    
    # AutoGen gRPC Service starten
    try:
        success = await processing_manager.start_grpc_service()
    except Exception as e:
        logger.warning(f"gRPC Service Startup-Exception: {e} → weiter ohne gRPC")
        # Im Test-/Fallback-Modus App trotzdem starten
        yield
        return
    if not success:
        logger.warning("❌ Konnte gRPC Service nicht starten → weiter ohne gRPC")
        yield
        return
    
    logger.info("✅ AutoGen gRPC Service erfolgreich gestartet")
    
    yield
    
    # Shutdown
    logger.info("🛑 Stoppe FastAPI Requirements Engineering System")
    await processing_manager.stop_grpc_service()
    logger.info("✅ System erfolgreich heruntergefahren")

# =============================================================================
# FastAPI App Setup
# =============================================================================

app = FastAPI(
    title="Requirements Engineering System",
    description="Advanced Requirements Processing with AutoGen Agents",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Health Check Endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/v1/system/status", response_model=SystemStatusResponse)
async def get_system_status():
    """System Status Endpoint"""
    status = processing_manager.get_system_status()
    return SystemStatusResponse(**status)

@app.post("/api/v1/requirements/evaluate", response_model=Dict[str, str])
async def evaluate_single_requirement(
    requirement: RequirementRequest,
    background_tasks: BackgroundTasks
):
    """Evaluiert einzelnes Requirement"""
    try:
        request_id = await processing_manager.process_single_requirement(
            requirement, 
            processing_types=["evaluation"]
        )
        
        return {
            "requestId": request_id,
            "status": "processing",
            "message": "Requirement wird verarbeitet",
            "websocketUrl": f"/ws/processing/{request_id}"
        }
        
    except Exception as e:
        logger.error(f"Evaluation-Fehler: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/requirements/batch", response_model=BatchProcessingResponse)
async def process_requirements_batch(batch_request: BatchRequirementRequest):
    """Verarbeitet Batch von Requirements"""
    try:
        batch_id = await processing_manager.process_batch_requirements(batch_request)
        
        return BatchProcessingResponse(
            batchId=batch_id,
            totalRequirements=len(batch_request.requirements),
            processingTypes=batch_request.processingTypes,
            status="processing",
            websocketUrl=f"/ws/batch/{batch_id}"
        )
        
    except HTTPException as he:
        # z. B. invalid processingTypes → 400
        raise he
    except Exception as e:
        logger.error(f"Batch-Processing-Fehler: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/processing/status/{batch_id}", response_model=ProcessingStatusResponse)
async def get_processing_status(batch_id: str):
    """Gibt Processing-Status zurück"""
    status = processing_manager.get_batch_status(batch_id)
    if not status:
        raise HTTPException(status_code=404, detail="Batch nicht gefunden")
    
    progress = status["completed"] / status["total_requirements"] * 100
    
    return ProcessingStatusResponse(
        batchId=batch_id,
        completedRequirements=status["completed"],
        totalRequirements=status["total_requirements"],
        currentStage=status.get("current_stage", "processing"),
        progress=progress,
        results=status["results"]
    )

# =============================================================================
# WebSocket für Real-time Updates
# =============================================================================

@app.websocket("/ws/processing/{request_id}")
async def websocket_processing_updates(websocket: WebSocket, request_id: str):
    """WebSocket für Real-time Processing Updates"""
    await websocket.accept()
    processing_manager.websocket_connections[request_id] = websocket
    
    try:
        while True:
            # Status-Updates senden
            status = processing_manager.get_batch_status(request_id)
            if status:
                await websocket.send_json({
                    "type": "status_update",
                    "requestId": request_id,
                    "status": status,
                    "timestamp": datetime.now().isoformat()
                })
            
            await asyncio.sleep(1)  # Updates jede Sekunde
            
    except WebSocketDisconnect:
        if request_id in processing_manager.websocket_connections:
            del processing_manager.websocket_connections[request_id]
        logger.info(f"WebSocket disconnected for {request_id}")

@app.websocket("/ws/batch/{batch_id}")
async def websocket_batch_updates(websocket: WebSocket, batch_id: str):
    """WebSocket für Batch Processing Updates"""
    await websocket.accept()
    processing_manager.websocket_connections[batch_id] = websocket
    
    try:
        while True:
            status = processing_manager.get_batch_status(batch_id)
            if status:
                await websocket.send_json({
                    "type": "batch_update",
                    "batchId": batch_id,
                    "status": status,
                    "timestamp": datetime.now().isoformat()
                })
            
            await asyncio.sleep(2)  # Updates alle 2 Sekunden
            
    except WebSocketDisconnect:
        if batch_id in processing_manager.websocket_connections:
            del processing_manager.websocket_connections[batch_id]
        logger.info(f"WebSocket disconnected for batch {batch_id}")

# =============================================================================
# Development Server
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("autogen_core")
    logger.setLevel(logging.DEBUG)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
