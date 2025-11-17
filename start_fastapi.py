#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI Requirements Engineering System Startup Script
Startet das moderne AutoGen-powered Backend
"""

import os
import sys
import asyncio
import logging
import argparse
import signal
from pathlib import Path

# Projekt-Root zum Python Path hinzufügen
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import uvicorn
from fastapi import FastAPI
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.panel import Panel

console = Console()

def setup_logging(log_level: str = "INFO"):
    """Setup Rich Logging"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)]
    )

def check_dependencies():
    """Prüft alle Dependencies"""
    console.print("🔍 Prüfe Dependencies...", style="yellow")
    
    required_packages = [
        ("fastapi", "FastAPI Web Framework"),
        ("uvicorn", "ASGI Server"),
        ("autogen_core", "AutoGen Core"),
        ("autogen_ext", "AutoGen Extensions"),
        ("aiosqlite", "Async SQLite"),
        ("openai", "OpenAI API"),
        ("pydantic", "Data Validation")
    ]
    
    missing_packages = []
    
    for package, description in required_packages:
        try:
            __import__(package)
            console.print(f"✅ {package}: {description}", style="green")
        except ImportError:
            console.print(f"❌ {package}: {description}", style="red")
            missing_packages.append(package)
    
    if missing_packages:
        console.print(f"\n🚨 Fehlende Packages: {', '.join(missing_packages)}", style="red bold")
        console.print("Installation: pip install -r requirements_fastapi.txt", style="yellow")
        return False
    
    console.print("\n✅ Alle Dependencies verfügbar!", style="green bold")
    return True

def check_environment():
    """Prüft Environment Setup"""
    console.print("\n🔍 Prüfe Environment...", style="yellow")
    
    # .env File prüfen
    env_file = project_root / ".env"
    if not env_file.exists():
        console.print("⚠️  .env File nicht gefunden - erstelle Beispiel", style="yellow")
        create_example_env()
    else:
        console.print("✅ .env File gefunden", style="green")
    
    # Datenbank-Ordner prüfen
    data_dir = project_root / "data"
    if not data_dir.exists():
        console.print("📁 Erstelle data/ Ordner...", style="yellow")
        data_dir.mkdir(exist_ok=True)
    
    console.print("✅ Environment Setup OK", style="green")

def create_example_env():
    """Erstellt Beispiel .env File"""
    env_content = """# FastAPI Requirements Engineering System Configuration

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# System Configuration  
MOCK_MODE=true
MAX_PARALLEL=3
BATCH_SIZE=10

# Database Configuration
DATABASE_PATH=./data/app.db

# gRPC Configuration
GRPC_HOST=localhost
GRPC_PORT=50051

# FastAPI Configuration
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
FASTAPI_RELOAD=true

# Security
SECRET_KEY=your_secret_key_here

# Logging
LOG_LEVEL=INFO

# Development
DEBUG=true
"""
    
    env_file = project_root / ".env"
    with open(env_file, "w") as f:
        f.write(env_content)
    
    console.print(f"📝 Beispiel .env erstellt: {env_file}", style="green")

def show_startup_banner():
    """Zeigt Startup-Banner"""
    banner = Panel.fit(
        """[bold blue]🚀 FastAPI Requirements Engineering System[/bold blue]

[green]✨ Features:[/green]
• AutoGen gRPC Worker Runtime
• Async Requirements Processing  
• Real-time WebSocket Updates
• Modern FastAPI + Uvicorn Stack
• TextAnnotationGraphs Integration Ready

[yellow]📖 Endpoints:[/yellow]
• http://localhost:8000/docs - OpenAPI Documentation
• http://localhost:8000/health - Health Check
• ws://localhost:8000/ws/processing - WebSocket Updates
        """,
        title="🔧 Modern Requirements Engineering",
        border_style="blue"
    )
    console.print(banner)

def show_system_info():
    """Zeigt System-Information"""
    table = Table(title="🖥️  System Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    # Environment Variables laden
    from dotenv import load_dotenv
    load_dotenv()
    
    table.add_row("FastAPI Host", os.getenv("FASTAPI_HOST", "0.0.0.0"))
    table.add_row("FastAPI Port", os.getenv("FASTAPI_PORT", "8000"))
    table.add_row("gRPC Host", os.getenv("GRPC_HOST", "localhost"))
    table.add_row("gRPC Port", os.getenv("GRPC_PORT", "50051"))
    table.add_row("OpenAI Model", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    table.add_row("Mock Mode", os.getenv("MOCK_MODE", "true"))
    table.add_row("Database", os.getenv("DATABASE_PATH", "./data/app.db"))
    table.add_row("Log Level", os.getenv("LOG_LEVEL", "INFO"))
    
    console.print(table)

async def startup_checks():
    """Führt Startup-Checks durch"""
    console.print("\n🔄 Startup-Checks...", style="yellow")
    
    try:
        # AutoGen Import testen
        from backend.core.agents import RequirementsEvaluatorAgent
        console.print("✅ AutoGen Agents verfügbar", style="green")
        
        # Database Check
        from backend.core.db_async import get_db_async
        db = await get_db_async()
        console.print("✅ Database-Verbindung OK", style="green")
        
        # LLM Check
        from backend.core.llm_async import test_llm_connection_async
        llm_ok = await test_llm_connection_async()
        if llm_ok:
            console.print("✅ LLM-Verbindung OK", style="green")
        else:
            console.print("⚠️  LLM-Verbindung fehlgeschlagen (Mock-Mode aktiv)", style="yellow")
            
    except Exception as e:
        console.print(f"❌ Startup-Check fehlgeschlagen: {str(e)}", style="red")
        return False
    
    console.print("✅ Alle Startup-Checks erfolgreich!", style="green bold")
    return True

def run_development_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = True):
    """Startet Development Server"""
    console.print(f"\n🚀 Starte FastAPI Development Server...", style="blue bold")
    console.print(f"📍 URL: http://{host}:{port}", style="cyan")
    console.print(f"📚 Docs: http://{host}:{port}/docs", style="cyan")
    console.print(f"🔄 Reload: {'Aktiviert' if reload else 'Deaktiviert'}", style="cyan")
    
    try:
        uvicorn.run(
            "fastapi_main:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        console.print("\n🛑 Server durch Benutzer gestoppt", style="yellow")
    except Exception as e:
        console.print(f"\n❌ Server-Fehler: {str(e)}", style="red")

def run_production_server(host: str = "0.0.0.0", port: int = 8000, workers: int = 4):
    """Startet Production Server"""
    console.print(f"\n🏭 Starte FastAPI Production Server...", style="blue bold")
    console.print(f"📍 URL: http://{host}:{port}", style="cyan")
    console.print(f"👥 Workers: {workers}", style="cyan")
    
    try:
        uvicorn.run(
            "fastapi_main:app",
            host=host,
            port=port,
            workers=workers,
            log_level="warning",
            access_log=False
        )
    except KeyboardInterrupt:
        console.print("\n🛑 Server durch Benutzer gestoppt", style="yellow")
    except Exception as e:
        console.print(f"\n❌ Server-Fehler: {str(e)}", style="red")

async def main():
    """Main Function"""
    parser = argparse.ArgumentParser(description="FastAPI Requirements Engineering System")
    parser.add_argument("--host", default="0.0.0.0", help="Host address")
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers (production)")
    parser.add_argument("--production", action="store_true", help="Run in production mode")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    parser.add_argument("--check-only", action="store_true", help="Only run checks, don't start server")
    
    args = parser.parse_args()
    
    # Logging setup
    setup_logging(args.log_level)
    
    # Banner anzeigen
    show_startup_banner()
    
    # Dependencies prüfen
    if not check_dependencies():
        sys.exit(1)
    
    # Environment prüfen
    check_environment()
    
    # System Info
    show_system_info()
    
    # Startup Checks
    checks_ok = await startup_checks()
    if not checks_ok:
        console.print("❌ Startup-Checks fehlgeschlagen!", style="red bold")
        sys.exit(1)
    
    # Nur Checks ausführen?
    if args.check_only:
        console.print("✅ Alle Checks erfolgreich! System bereit.", style="green bold")
        return
    
    # Server starten
    if args.production:
        run_production_server(args.host, args.port, args.workers)
    else:
        reload = not args.no_reload
        run_development_server(args.host, args.port, reload)

if __name__ == "__main__":
    # Graceful Shutdown Setup
    def signal_handler(signum, frame):
        console.print("\n🛑 Shutdown-Signal empfangen...", style="yellow")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run Main
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n👋 Auf Wiedersehen!", style="blue")
