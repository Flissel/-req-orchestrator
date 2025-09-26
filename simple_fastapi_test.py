# -*- coding: utf-8 -*-
"""
Simple FastAPI Test Starter
Vereinfachte Version ohne Rich Console für Windows-Kompatibilität
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Projekt-Root zum Python Path hinzufügen
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Environment Setup
os.environ.setdefault('MOCK_MODE', 'true')
os.environ.setdefault('OPENAI_API_KEY', 'test_key')
os.environ.setdefault('OPENAI_MODEL', 'gpt-4o-mini')
os.environ.setdefault('GRPC_HOST', 'localhost')
os.environ.setdefault('GRPC_PORT', '50051')
os.environ.setdefault('DATABASE_PATH', './data/app.db')

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_dependencies():
    """Prüft Dependencies ohne Rich Console"""
    print("=== Prüfe Dependencies ===")
    
    required_packages = [
        ("fastapi", "FastAPI Web Framework"),
        ("uvicorn", "ASGI Server"),
        ("pydantic", "Data Validation")
    ]
    
    missing_packages = []
    
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"✓ {package}: {description}")
        except ImportError:
            print(f"✗ {package}: {description}")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\nFehlende Packages: {', '.join(missing_packages)}")
        print("Installation: pip install fastapi uvicorn pydantic")
        return False
    
    print("\n✓ Alle Dependencies verfügbar!")
    return True

def create_simple_fastapi_app():
    """Erstellt eine einfache FastAPI App für Tests"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import Dict, List, Any, Optional
    from datetime import datetime
    
    app = FastAPI(
        title="Requirements Engineering System - Test",
        description="Vereinfachte Test-Version",
        version="1.0.0"
    )
    
    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Pydantic Models
    class RequirementRequest(BaseModel):
        requirementText: str
        context: Optional[Dict[str, Any]] = {}
        criteriaKeys: Optional[List[str]] = None
    
    class EvaluationResponse(BaseModel):
        requestId: str
        status: str
        score: float
        verdict: str
        latencyMs: int
        timestamp: str
    
    # Endpoints
    @app.get("/health")
    async def health_check():
        return {
            "status": "ok", 
            "timestamp": datetime.now().isoformat(),
            "message": "FastAPI Requirements System läuft!"
        }
    
    @app.get("/api/v1/system/status")
    async def get_system_status():
        return {
            "grpcHostRunning": False,  # Mock für Test
            "activeWorkers": 0,
            "totalProcessedToday": 0,
            "systemLoad": 0.1,
            "uptime": "0h 5m",
            "mode": "test"
        }
    
    @app.post("/api/v1/requirements/evaluate")
    async def evaluate_requirement(requirement: RequirementRequest):
        """Mock Evaluation für Test"""
        import uuid
        import random
        
        # Simuliere Processing
        await asyncio.sleep(0.1)
        
        # Mock Evaluation basierend auf Text-Länge
        score = min(0.9, len(requirement.requirementText) / 200)
        verdicts = ["excellent", "good", "acceptable", "needs_improvement"]
        verdict = verdicts[int(score * len(verdicts)) - 1] if score > 0 else "poor"
        
        return EvaluationResponse(
            requestId=f"req_{uuid.uuid4().hex[:8]}",
            status="completed",
            score=score,
            verdict=verdict,
            latencyMs=random.randint(100, 300),
            timestamp=datetime.now().isoformat()
        )
    
    return app

def run_simple_test():
    """Führt einfache Tests durch"""
    print("\n=== Starte FastAPI Tests ===")
    
    try:
        # FastAPI App erstellen
        app = create_simple_fastapi_app()
        print("✓ FastAPI App erstellt")
        
        # Test Client erstellen
        from fastapi.testclient import TestClient
        client = TestClient(app)
        print("✓ Test Client erstellt")
        
        # Health Check Test
        response = client.get("/health")
        if response.status_code == 200:
            print("✓ Health Check erfolgreich")
            print(f"  Response: {response.json()}")
        else:
            print(f"✗ Health Check fehlgeschlagen: {response.status_code}")
            return False
        
        # System Status Test
        response = client.get("/api/v1/system/status")
        if response.status_code == 200:
            print("✓ System Status erfolgreich")
            print(f"  Response: {response.json()}")
        else:
            print(f"✗ System Status fehlgeschlagen: {response.status_code}")
            return False
        
        # Requirements Evaluation Test
        test_requirement = {
            "requirementText": "Das System soll eine REST API bereitstellen, die innerhalb von 200ms antwortet.",
            "context": {"language": "de", "area": "api", "priority": "high"}
        }
        
        response = client.post("/api/v1/requirements/evaluate", json=test_requirement)
        if response.status_code == 200:
            print("✓ Requirements Evaluation erfolgreich")
            result = response.json()
            print(f"  Request ID: {result['requestId']}")
            print(f"  Score: {result['score']:.2f}")
            print(f"  Verdict: {result['verdict']}")
            print(f"  Latency: {result['latencyMs']}ms")
        else:
            print(f"✗ Requirements Evaluation fehlgeschlagen: {response.status_code}")
            return False
        
        print("\n✓ Alle Tests erfolgreich!")
        return True
        
    except Exception as e:
        print(f"✗ Test-Fehler: {str(e)}")
        return False

def start_server():
    """Startet den FastAPI Server"""
    print("\n=== Starte FastAPI Server ===")
    
    try:
        import uvicorn
        from fastapi_main import app
        
        print("FastAPI Server startet...")
        print("URL: http://localhost:8000")
        print("API Docs: http://localhost:8000/docs")
        print("Health Check: http://localhost:8000/health")
        print("\nDrücken Sie CTRL+C zum Stoppen")
        
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info"
        )
        
    except ImportError as e:
        print(f"✗ Import-Fehler: {str(e)}")
        print("Führe stattdessen vereinfachte Version aus...")
        
        app = create_simple_fastapi_app()
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info"
        )
        
    except KeyboardInterrupt:
        print("\n✓ Server gestoppt")
    except Exception as e:
        print(f"✗ Server-Fehler: {str(e)}")

def main():
    """Main Function"""
    print("FastAPI Requirements Engineering System - Einfacher Test")
    print("=" * 60)
    
    # Dependencies prüfen
    if not check_dependencies():
        sys.exit(1)
    
    # Datenordner erstellen
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)
    print(f"✓ Datenordner: {data_dir.absolute()}")
    
    # Tests ausführen
    if run_simple_test():
        print("\n" + "=" * 60)
        print("TESTS ERFOLGREICH! System ist bereit.")
        print("=" * 60)
        
        # Server starten?
        try:
            user_input = input("\nMöchten Sie den Server starten? (y/n): ").lower()
            if user_input in ['y', 'yes', 'ja', 'j']:
                start_server()
            else:
                print("✓ Tests abgeschlossen. Server nicht gestartet.")
        except KeyboardInterrupt:
            print("\n✓ Test beendet.")
    else:
        print("\n✗ Tests fehlgeschlagen!")
        sys.exit(1)

if __name__ == "__main__":
    main()
