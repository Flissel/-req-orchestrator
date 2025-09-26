# -*- coding: utf-8 -*-
"""
Minimal FastAPI Requirements System - Live Test Version
Funktioniert ohne AutoGen Dependencies für sofortiges Testen
"""

import asyncio
import logging
import uuid
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# Pydantic Models
# =============================================================================

class RequirementRequest(BaseModel):
    requirementText: str = Field(..., min_length=1, max_length=5000)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    criteriaKeys: Optional[List[str]] = None

class EvaluationResponse(BaseModel):
    requestId: str
    requirementChecksum: str
    verdict: str
    score: float
    latencyMs: int
    model: str
    details: Dict[str, float]
    suggestions: Optional[List[str]] = None
    timestamp: str

class SystemStatusResponse(BaseModel):
    grpcHostRunning: bool
    activeWorkers: int
    totalProcessedToday: int
    systemLoad: float
    uptime: str
    mode: str

# =============================================================================
# Mock Services
# =============================================================================

class MockLLMService:
    """Mock LLM Service für Live Testing"""
    
    def __init__(self):
        self.request_count = 0
    
    async def evaluate_requirement(self, requirement_text: str, context: Dict) -> Dict:
        """Mock Requirements Evaluation"""
        self.request_count += 1
        
        # Simuliere Processing Zeit
        await asyncio.sleep(0.1)
        
        # Einfache Heuristik basierend auf Text
        text_length = len(requirement_text)
        
        # Score basierend auf Länge und Keywords
        score = min(0.95, text_length / 150)
        
        # Bonus für gute Keywords
        good_keywords = ['soll', 'muss', 'API', 'innerhalb', 'antwortet', 'bereitstellt']
        keyword_bonus = sum(0.1 for kw in good_keywords if kw.lower() in requirement_text.lower())
        score = min(0.95, score + keyword_bonus * 0.05)
        
        # Verdict basierend auf Score
        if score >= 0.8:
            verdict = "excellent"
        elif score >= 0.65:
            verdict = "good"
        elif score >= 0.5:
            verdict = "acceptable"
        elif score >= 0.3:
            verdict = "needs_improvement"
        else:
            verdict = "poor"
        
        # Details generieren
        details = {
            "clarity": min(0.95, score + 0.05),
            "testability": max(0.4, score - 0.1),
            "completeness": score
        }
        
        # Suggestions basierend auf Score
        suggestions = []
        if score < 0.7:
            suggestions.append("Fügen Sie spezifische Akzeptanzkriterien hinzu")
        if score < 0.6:
            suggestions.append("Definieren Sie messbare Erfolgskriterien")
        if score < 0.5:
            suggestions.append("Berücksichtigen Sie Fehlerbehandlung und Edge-Cases")
        
        return {
            "score": score,
            "verdict": verdict,
            "details": details,
            "suggestions": suggestions,
            "latency_ms": 120 + (self.request_count * 10),
            "model": "mock-gpt-4o-mini"
        }

# Global Services
llm_service = MockLLMService()
processing_stats = {
    "total_processed": 0,
    "successful_evaluations": 0,
    "start_time": datetime.now()
}

# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="Requirements Engineering System - Live Test",
    description="Functional Requirements Processing System",
    version="1.0.0-test"
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
# Endpoints
# =============================================================================

@app.get("/")
async def root():
    """Root Endpoint mit Links"""
    return {
        "message": "Requirements Engineering System - Live Test",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "system_status": "/api/v1/system/status",
            "evaluate": "/api/v1/requirements/evaluate",
            "frontend": "/frontend"
        },
        "stats": processing_stats
    }

@app.get("/health")
async def health_check():
    """Health Check Endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "uptime": str(datetime.now() - processing_stats["start_time"]),
        "processed": processing_stats["total_processed"]
    }

@app.get("/api/v1/system/status", response_model=SystemStatusResponse)
async def get_system_status():
    """System Status Endpoint"""
    uptime = datetime.now() - processing_stats["start_time"]
    
    return SystemStatusResponse(
        grpcHostRunning=False,  # Mock für Test
        activeWorkers=1,
        totalProcessedToday=processing_stats["total_processed"],
        systemLoad=0.1,
        uptime=str(uptime),
        mode="test"
    )

@app.post("/api/v1/requirements/evaluate", response_model=EvaluationResponse)
async def evaluate_requirement(requirement: RequirementRequest):
    """Requirements Evaluation Endpoint"""
    try:
        start_time = asyncio.get_event_loop().time()
        
        # Request ID generieren
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        
        # Requirement Checksum (simuliert)
        import hashlib
        requirement_checksum = hashlib.sha256(
            requirement.requirementText.encode()
        ).hexdigest()[:16]
        
        logger.info(f"Evaluating requirement: {request_id}")
        
        # Mock LLM Evaluation
        evaluation_result = await llm_service.evaluate_requirement(
            requirement.requirementText,
            requirement.context or {}
        )
        
        # Response erstellen
        response = EvaluationResponse(
            requestId=request_id,
            requirementChecksum=requirement_checksum,
            verdict=evaluation_result["verdict"],
            score=evaluation_result["score"],
            latencyMs=evaluation_result["latency_ms"],
            model=evaluation_result["model"],
            details=evaluation_result["details"],
            suggestions=evaluation_result.get("suggestions"),
            timestamp=datetime.now().isoformat()
        )
        
        # Stats aktualisieren
        processing_stats["total_processed"] += 1
        processing_stats["successful_evaluations"] += 1
        
        logger.info(f"Evaluation completed: {request_id} - Score: {response.score:.2f}")
        
        return response
        
    except Exception as e:
        logger.error(f"Evaluation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/frontend", response_class=HTMLResponse)
async def get_frontend():
    """Minimal Frontend für Live Testing"""
    html_content = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Requirements Engineering - Live Test</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
        .container { background: #f5f5f5; padding: 20px; border-radius: 8px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        textarea, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        .result { margin-top: 20px; padding: 15px; background: white; border-radius: 4px; border-left: 4px solid #28a745; }
        .error { border-left-color: #dc3545; }
        .score { font-size: 24px; font-weight: bold; color: #28a745; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Requirements Engineering - Live Test</h1>
        
        <form id="requirementForm">
            <div class="form-group">
                <label for="requirementText">Requirement Text:</label>
                <textarea id="requirementText" rows="4" placeholder="Das System soll eine REST API bereitstellen..." required></textarea>
            </div>
            
            <div class="form-group">
                <label for="area">Bereich:</label>
                <select id="area">
                    <option value="api">API</option>
                    <option value="security">Security</option>
                    <option value="performance">Performance</option>
                    <option value="ops">Operations</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="priority">Priorität:</label>
                <select id="priority">
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                </select>
            </div>
            
            <button type="submit">🔍 Requirement evaluieren</button>
        </form>
        
        <div id="result" style="display: none;"></div>
    </div>
    
    <script>
        document.getElementById('requirementForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const requirementText = document.getElementById('requirementText').value;
            const area = document.getElementById('area').value;
            const priority = document.getElementById('priority').value;
            
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = '<p>⏳ Evaluating...</p>';
            resultDiv.style.display = 'block';
            resultDiv.className = 'result';
            
            try {
                const response = await fetch('/api/v1/requirements/evaluate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        requirementText: requirementText,
                        context: { area: area, priority: priority, language: 'de' }
                    })
                });
                
                if (response.ok) {
                    const result = await response.json();
                    
                    resultDiv.innerHTML = `
                        <h3>✅ Evaluation erfolgreich!</h3>
                        <p><strong>Request ID:</strong> ${result.requestId}</p>
                        <p><strong>Score:</strong> <span class="score">${(result.score * 100).toFixed(1)}%</span></p>
                        <p><strong>Verdict:</strong> ${result.verdict}</p>
                        <p><strong>Latency:</strong> ${result.latencyMs}ms</p>
                        <p><strong>Model:</strong> ${result.model}</p>
                        
                        <h4>Details:</h4>
                        <ul>
                            <li>Clarity: ${(result.details.clarity * 100).toFixed(1)}%</li>
                            <li>Testability: ${(result.details.testability * 100).toFixed(1)}%</li>
                            <li>Completeness: ${(result.details.completeness * 100).toFixed(1)}%</li>
                        </ul>
                        
                        ${result.suggestions && result.suggestions.length > 0 ? `
                            <h4>💡 Suggestions:</h4>
                            <ul>${result.suggestions.map(s => `<li>${s}</li>`).join('')}</ul>
                        ` : ''}
                    `;
                } else {
                    throw new Error(`HTTP ${response.status}`);
                }
                
            } catch (error) {
                resultDiv.className = 'result error';
                resultDiv.innerHTML = `<h3>❌ Fehler:</h3><p>${error.message}</p>`;
            }
        });
        
        // Beispiel-Text laden
        document.getElementById('requirementText').value = 
            'Das Backend stellt einen Health-Endpoint unter GET /health bereit, der innerhalb von 200 ms mit {"status":"ok"} antwortet.';
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    print("Starting FastAPI Requirements Engineering System...")
    print("Frontend: http://127.0.0.1:8000/frontend")
    print("API Docs: http://127.0.0.1:8000/docs")
    print("Health: http://127.0.0.1:8000/health")
    
    uvicorn.run(app, host="127.0.0.1", port=8000)
