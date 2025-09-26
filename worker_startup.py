#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoGen Worker Startup Script für Docker Container
Startet spezifische Worker basierend auf WORKER_TYPE Environment Variable
"""

import os
import sys
import asyncio
import logging
import signal
from pathlib import Path

# Projekt-Root zum Python Path hinzufügen
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from autogen_core import DefaultSubscription

from backend_app.agents import (
    RequirementsEvaluatorAgent,
    RequirementsSuggestionAgent,
    RequirementsRewriteAgent,
    RequirementsOrchestratorAgent,
    RequirementsMonitorAgent,
    register_all_message_serializers
)

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WorkerManager:
    """Manager für AutoGen Worker in Docker Container"""
    
    def __init__(self):
        # Environment Configuration
        self.grpc_host = os.getenv('GRPC_HOST', 'localhost')
        self.grpc_port = os.getenv('GRPC_PORT', '50051')
        self.worker_type = os.getenv('WORKER_TYPE', 'evaluator')
        self.worker_id = os.getenv('HOSTNAME', f'worker_{self.worker_type}')
        
        # Runtime Configuration
        self.host_address = f"{self.grpc_host}:{self.grpc_port}"
        self.runtime = None
        self.is_running = False
        
        logger.info(f"Worker Manager initialisiert:")
        logger.info(f"  Worker Type: {self.worker_type}")
        logger.info(f"  Worker ID: {self.worker_id}")
        logger.info(f"  gRPC Host: {self.host_address}")
    
    async def start_worker(self):
        """Startet den Worker basierend auf Typ"""
        try:
            # Runtime erstellen
            self.runtime = GrpcWorkerAgentRuntime(host_address=self.host_address)
            await self.runtime.start()
            logger.info(f"Worker Runtime gestartet für {self.host_address}")
            
            # Message Serializers registrieren
            register_all_message_serializers(self.runtime)
            logger.info("Message Serializers registriert")
            
            # Worker-spezifischen Agent registrieren
            await self._register_worker_agent()
            
            self.is_running = True
            logger.info(f"Worker {self.worker_type} erfolgreich gestartet")
            
        except Exception as e:
            logger.error(f"Fehler beim Starten des Workers: {str(e)}")
            raise
    
    async def _register_worker_agent(self):
        """Registriert den Worker-Agent basierend auf Typ"""
        
        if self.worker_type == 'evaluator':
            # Requirements Evaluator
            await RequirementsEvaluatorAgent.register(
                self.runtime,
                f"requirements_evaluator_{self.worker_id}",
                lambda: RequirementsEvaluatorAgent(f"Docker_Evaluator_{self.worker_id}")
            )
            await self.runtime.add_subscription(
                DefaultSubscription(agent_type=f"requirements_evaluator_{self.worker_id}")
            )
            logger.info("Requirements Evaluator Agent registriert")
            
        elif self.worker_type == 'suggester':
            # Requirements Suggester
            await RequirementsSuggestionAgent.register(
                self.runtime,
                f"requirements_suggester_{self.worker_id}",
                lambda: RequirementsSuggestionAgent(f"Docker_Suggester_{self.worker_id}")
            )
            await self.runtime.add_subscription(
                DefaultSubscription(agent_type=f"requirements_suggester_{self.worker_id}")
            )
            logger.info("Requirements Suggester Agent registriert")
            
        elif self.worker_type == 'rewriter':
            # Requirements Rewriter
            await RequirementsRewriteAgent.register(
                self.runtime,
                f"requirements_rewriter_{self.worker_id}",
                lambda: RequirementsRewriteAgent(f"Docker_Rewriter_{self.worker_id}")
            )
            await self.runtime.add_subscription(
                DefaultSubscription(agent_type=f"requirements_rewriter_{self.worker_id}")
            )
            logger.info("Requirements Rewriter Agent registriert")
            
        elif self.worker_type == 'orchestrator':
            # Orchestrator Agent
            await RequirementsOrchestratorAgent.register(
                self.runtime,
                f"requirements_orchestrator_{self.worker_id}",
                lambda: RequirementsOrchestratorAgent(f"Docker_Orchestrator_{self.worker_id}")
            )
            await self.runtime.add_subscription(
                DefaultSubscription(agent_type=f"requirements_orchestrator_{self.worker_id}")
            )
            logger.info("Requirements Orchestrator Agent registriert")
            
        elif self.worker_type == 'monitor':
            # Monitor Agent
            await RequirementsMonitorAgent.register(
                self.runtime,
                f"requirements_monitor_{self.worker_id}",
                lambda: RequirementsMonitorAgent(f"Docker_Monitor_{self.worker_id}")
            )
            await self.runtime.add_subscription(
                DefaultSubscription(agent_type=f"requirements_monitor_{self.worker_id}")
            )
            logger.info("Requirements Monitor Agent registriert")
            
        else:
            raise ValueError(f"Unbekannter Worker-Typ: {self.worker_type}")
    
    async def stop_worker(self):
        """Stoppt den Worker"""
        try:
            if self.runtime:
                await self.runtime.stop()
                logger.info(f"Worker {self.worker_type} gestoppt")
            
            self.is_running = False
            
        except Exception as e:
            logger.error(f"Fehler beim Stoppen des Workers: {str(e)}")
    
    async def run_until_signal(self):
        """Läuft bis Signal empfangen wird"""
        try:
            logger.info(f"Worker {self.worker_type} läuft... (CTRL+C zum Stoppen)")
            
            # Signal Handler für graceful shutdown
            def signal_handler():
                logger.info("Shutdown-Signal empfangen")
                self.is_running = False
            
            # Event Loop für Signal Handling
            loop = asyncio.get_event_loop()
            for sig in [signal.SIGTERM, signal.SIGINT]:
                loop.add_signal_handler(sig, signal_handler)
            
            # Warten bis Signal empfangen
            while self.is_running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Keyboard Interrupt empfangen")
        except Exception as e:
            logger.error(f"Fehler im Worker-Loop: {str(e)}")
        finally:
            await self.stop_worker()

async def main():
    """Main Function"""
    worker_manager = WorkerManager()
    
    try:
        # Worker starten
        await worker_manager.start_worker()
        
        # Bis Signal warten
        await worker_manager.run_until_signal()
        
    except Exception as e:
        logger.error(f"Kritischer Fehler: {str(e)}")
        sys.exit(1)
    
    logger.info("Worker beendet")

if __name__ == "__main__":
    # Environment Validation
    required_env_vars = ['WORKER_TYPE', 'GRPC_HOST', 'GRPC_PORT']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Fehlende Environment-Variablen: {missing_vars}")
        sys.exit(1)
    
    # Graceful Shutdown Setup
    def signal_handler(signum, frame):
        logger.info(f"Signal {signum} empfangen - beende Worker...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Worker starten
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker durch Benutzer gestoppt")
    except Exception as e:
        logger.error(f"Unbehandelter Fehler: {str(e)}")
        sys.exit(1)
