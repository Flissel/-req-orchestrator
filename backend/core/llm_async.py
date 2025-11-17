# -*- coding: utf-8 -*-
"""
Async LLM Operations für FastAPI + AutoGen Integration
"""

import asyncio
import openai
import logging
import time
from typing import Dict, List, Any, Optional
import json
import os
from dataclasses import dataclass

from .settings import (
    OPENAI_MODEL,
    OPENAI_API_KEY,
    MOCK_MODE,
    MAX_PARALLEL,
    BATCH_SIZE
)
from .db_async import load_criteria_async

logger = logging.getLogger(__name__)

# OpenAI Client Configuration
if OPENAI_API_KEY and not MOCK_MODE:
    openai.api_key = OPENAI_API_KEY
else:
    logger.warning("MOCK_MODE aktiviert oder OpenAI API Key fehlt")

@dataclass
class LLMResult:
    """Standardisiertes LLM-Ergebnis"""
    success: bool
    data: Dict[str, Any]
    latency_ms: int
    model: str
    error: Optional[str] = None

class AsyncLLMService:
    """Async LLM Service für Requirements Processing"""
    
    def __init__(self):
        self.model = OPENAI_MODEL
        # Ohne API-Key stets Mock-Modus aktivieren (deterministische Tests)
        self.mock_mode = MOCK_MODE or (not OPENAI_API_KEY)
        self.request_count = 0
        
    async def _make_async_llm_call(
        self, 
        prompt: str, 
        system_prompt: str = "",
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> LLMResult:
        """Macht async LLM-Call"""
        start_time = time.time()
        
        try:
            if self.mock_mode:
                # Mock-Response für Testing
                await asyncio.sleep(0.1)  # Simuliere Latenz
                return await self._generate_mock_response(prompt)
            
            # Echter OpenAI Call (async)
            response = await asyncio.to_thread(
                self._sync_openai_call,
                prompt,
                system_prompt,
                max_tokens,
                temperature
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            self.request_count += 1
            
            return LLMResult(
                success=True,
                data={"content": response},
                latency_ms=latency_ms,
                model=self.model
            )
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"LLM-Call fehlgeschlagen: {str(e)}")
            
            return LLMResult(
                success=False,
                data={},
                latency_ms=latency_ms,
                model=self.model,
                error=str(e)
            )
    
    def _sync_openai_call(
        self, 
        prompt: str, 
        system_prompt: str,
        max_tokens: int,
        temperature: float
    ) -> str:
        """Synchroner OpenAI Call (wird in thread ausgeführt)"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return response.choices[0].message.content.strip()
    
    async def _generate_mock_response(self, prompt: str) -> LLMResult:
        """Generiert Mock-Response für Testing"""
        # Einfache Heuristik basierend auf Prompt
        pl = prompt.lower()
        if ("evaluate" in pl) or ("bewerten" in pl) or ("evaluiere" in pl):
            mock_data = {
                "verdict": "good" if len(prompt) > 100 else "acceptable",
                "score": 0.85 if len(prompt) > 100 else 0.65,
                "details": {
                    "clarity": 0.9,
                    "testability": 0.8,
                    "completeness": 0.85
                }
            }
        # WICHTIG: Rewrite vor Suggest prüfen, da Rewrite-Prompts häufig „Verbesserungen:“ enthalten
        elif (
            ("rewrite" in pl)
            or ("umschreib" in pl)
            or ("umformul" in pl)
            or (("schreibe" in pl) and (" um" in pl))  # "Schreibe ... um"
            or ("neu formulier" in pl)
            or ("überarbeit" in pl)
            or ("präzis" in pl)
            or ("klarer formulier" in pl)
        ):
            mock_data = {
                "rewritten_requirement": f"Verbesserte Version: {prompt[:100]}... [umgeschrieben]"
            }
        elif ("suggest" in pl) or ("verbesser" in pl):
            mock_data = {
                "suggestions": [
                    "Fügen Sie spezifische Akzeptanzkriterien hinzu",
                    "Definieren Sie messbare Erfolgskriterien",
                    "Erwägen Sie Edge-Cases und Fehlerbehandlung"
                ]
            }
        else:
            mock_data = {"response": "Mock-Antwort für unbekannten Prompt-Typ"}
        
        # WICHTIG: Immer im 'content'-Feld JSON-String zurückgeben, damit json.loads(...) in den Callern funktioniert
        return LLMResult(
            success=True,
            data={"content": json.dumps(mock_data, ensure_ascii=False)},
            latency_ms=150,  # Mock-Latenz
            model="mock-" + self.model
        )

# Global LLM Service Instance
llm_service = AsyncLLMService()

async def llm_evaluate_async(
    requirement_text: str,
    context: Dict[str, Any] = None,
    criteria_keys: List[str] = None
) -> Dict[str, Any]:
    """Async Requirements Evaluation"""
    try:
        # Kriterien laden falls nicht spezifiziert
        if not criteria_keys:
            criteria = await load_criteria_async()
            criteria_keys = [c["key"] for c in criteria]
        
        # Evaluation-Prompt erstellen
        prompt = f"""
Evaluiere das folgende Requirement anhand der Kriterien: {', '.join(criteria_keys)}

Requirement: "{requirement_text}"

Kontext: {json.dumps(context or {}, ensure_ascii=False)}

Bewerte das Requirement auf einer Skala von 0.0 bis 1.0 für jedes Kriterium:
- clarity: Wie klar und verständlich ist das Requirement?
- testability: Wie gut lässt sich das Requirement testen?
- completeness: Wie vollständig ist die Spezifikation?

Antworte im folgenden JSON-Format:
{{
    "score": <overall_score>,
    "verdict": "<excellent|good|acceptable|needs_improvement|poor>",
    "details": {{
        "clarity": <score>,
        "testability": <score>, 
        "completeness": <score>
    }}
}}
"""
        
        system_prompt = """Du bist ein Experte für Requirements Engineering. 
Bewerte Requirements objektiv und konstruktiv. Gib detailliertes Feedback."""
        
        result = await llm_service._make_async_llm_call(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=500,
            temperature=0.3
        )
        
        if not result.success:
            raise Exception(f"LLM-Call fehlgeschlagen: {result.error}")
        
        # JSON-Response parsen
        try:
            response_data = json.loads(result.data["content"])
        except json.JSONDecodeError:
            # Fallback bei Parse-Fehler
            response_data = {
                "score": 0.5,
                "verdict": "acceptable",
                "details": {"clarity": 0.5, "testability": 0.5, "completeness": 0.5}
            }
        
        # Erwartete Felder absichern
        if not isinstance(response_data.get("details"), dict):
            response_data["details"] = {"clarity": 0.5, "testability": 0.5, "completeness": 0.5}
        if "score" not in response_data:
            try:
                d = response_data.get("details", {})
                vals = [float(d.get(k, 0.5)) for k in ("clarity", "testability", "completeness")]
                response_data["score"] = sum(vals) / max(1, len(vals))
            except Exception:
                response_data["score"] = 0.5
        if str(response_data.get("verdict") or "").strip() == "":
            response_data["verdict"] = "acceptable"
        
        # Zusätzliche Metadaten hinzufügen
        response_data.update({
            "latency_ms": result.latency_ms,
            "model": result.model
        })
        
        logger.info(f"Evaluation abgeschlossen: Score {response_data.get('score', 0):.2f}")
        return response_data
        
    except Exception as e:
        logger.error(f"Fehler bei LLM-Evaluation: {str(e)}")
        return {
            "score": 0.0,
            "verdict": "error",
            "details": {},
            "latency_ms": 0,
            "model": llm_service.model,
            "error": str(e)
        }

async def llm_suggest_async(
    requirement_text: str,
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Async Requirements Suggestion Generation"""
    try:
        prompt = f"""
Analysiere das folgende Requirement und generiere bis zu 3 konkrete Verbesserungsvorschläge:

Requirement: "{requirement_text}"

Kontext: {json.dumps(context or {}, ensure_ascii=False)}

Fokussiere auf:
1. Klarheit und Verständlichkeit
2. Testbarkeit und Messbarkeit  
3. Vollständigkeit und Details
4. Technische Präzision

Antworte im folgenden JSON-Format:
{{
    "suggestions": [
        "Verbesserungsvorschlag 1",
        "Verbesserungsvorschlag 2", 
        "Verbesserungsvorschlag 3"
    ]
}}
"""
        
        system_prompt = """Du bist ein Experte für Requirements Engineering.
Generiere präzise, umsetzbare Verbesserungsvorschläge für Requirements."""
        
        result = await llm_service._make_async_llm_call(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=800,
            temperature=0.7
        )
        
        if not result.success:
            raise Exception(f"LLM-Call fehlgeschlagen: {result.error}")
        
        # JSON-Response parsen
        try:
            response_data = json.loads(result.data["content"])
        except json.JSONDecodeError:
            # Fallback bei Parse-Fehler
            response_data = {
                "suggestions": [
                    "Fügen Sie spezifische Akzeptanzkriterien hinzu",
                    "Definieren Sie messbare Erfolgskriterien",
                    "Berücksichtigen Sie Fehlerbehandlung und Edge-Cases"
                ]
            }
        
        # Erwartete Felder absichern
        if not isinstance(response_data.get("suggestions"), list) or not response_data.get("suggestions"):
            response_data["suggestions"] = [
                "Fügen Sie spezifische Akzeptanzkriterien hinzu",
                "Definieren Sie messbare Erfolgskriterien",
                "Erwägen Sie Edge-Cases und Fehlerbehandlung"
            ]
        
        # Metadaten hinzufügen
        response_data.update({
            "latency_ms": result.latency_ms,
            "model": result.model
        })
        
        logger.info(f"Suggestions generiert: {len(response_data.get('suggestions', []))} Vorschläge")
        return response_data
        
    except Exception as e:
        logger.error(f"Fehler bei LLM-Suggestions: {str(e)}")
        return {
            "suggestions": [],
            "latency_ms": 0,
            "model": llm_service.model,
            "error": str(e)
        }

async def llm_rewrite_async(
    requirement_text: str,
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Async Requirements Rewriting"""
    try:
        prompt = f"""
Schreibe das folgende Requirement um, um es klarer, präziser und testbarer zu machen:

Original Requirement: "{requirement_text}"

Kontext: {json.dumps(context or {}, ensure_ascii=False)}

Verbesserungen:
1. Verwende präzise, eindeutige Sprache
2. Füge messbare Kriterien hinzu  
3. Strukturiere logisch und klar
4. Berücksichtige technische Details
5. Behalte die ursprüngliche Intention bei

Antworte im folgenden JSON-Format:
{{
    "rewritten_requirement": "Das verbesserte Requirement..."
}}
"""
        
        system_prompt = """Du bist ein Experte für Requirements Engineering.
Schreibe Requirements präzise und professionell um, ohne die ursprüngliche Bedeutung zu ändern."""
        
        result = await llm_service._make_async_llm_call(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=1000,
            temperature=0.5
        )
        
        if not result.success:
            raise Exception(f"LLM-Call fehlgeschlagen: {result.error}")
        
        # JSON-Response parsen
        try:
            response_data = json.loads(result.data["content"])
        except json.JSONDecodeError:
            # Fallback bei Parse-Fehler
            response_data = {
                "rewritten_requirement": f"Verbesserte Version: {requirement_text}"
            }
        
        # Erwartete Felder absichern
        if not isinstance(response_data.get("rewritten_requirement"), str) or not response_data.get("rewritten_requirement"):
            response_data["rewritten_requirement"] = f"Verbesserte Version: {requirement_text}"
        
        # Metadaten hinzufügen
        response_data.update({
            "latency_ms": result.latency_ms,
            "model": result.model
        })
        
        logger.info(f"Requirement umgeschrieben: {len(response_data.get('rewritten_requirement', ''))} Zeichen")
        return response_data
        
    except Exception as e:
        logger.error(f"Fehler bei LLM-Rewrite: {str(e)}")
        return {
            "rewritten_requirement": requirement_text,  # Original zurückgeben
            "latency_ms": 0,
            "model": llm_service.model,
            "error": str(e)
        }

async def llm_batch_process_async(
    requirements: List[Dict[str, Any]],
    processing_type: str = "evaluation",
    parallel_limit: int = 3
) -> List[Dict[str, Any]]:
    """Async Batch-Processing von Requirements"""
    try:
        results = []
        
        # Semaphore für Parallelitätsbegrenzung
        semaphore = asyncio.Semaphore(parallel_limit)
        
        async def process_single_requirement(req_data):
            async with semaphore:
                req_text = req_data.get("requirement_text", "")
                context = req_data.get("context", {})
                
                if processing_type == "evaluation":
                    return await llm_evaluate_async(req_text, context)
                elif processing_type == "suggestion":
                    return await llm_suggest_async(req_text, context)
                elif processing_type == "rewrite":
                    return await llm_rewrite_async(req_text, context)
                else:
                    raise ValueError(f"Unbekannter Processing-Type: {processing_type}")
        
        # Alle Requirements parallel verarbeiten
        tasks = [process_single_requirement(req) for req in requirements]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Exceptions behandeln
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Fehler bei Requirement {i}: {str(result)}")
                processed_results.append({
                    "error": str(result),
                    "requirement_index": i
                })
            else:
                processed_results.append(result)
        
        logger.info(f"Batch-Processing abgeschlossen: {len(processed_results)} Requirements")
        return processed_results
        
    except Exception as e:
        logger.error(f"Fehler beim Batch-Processing: {str(e)}")
        return []

# Utility Functions für LLM Management

async def get_llm_stats_async() -> Dict[str, Any]:
    """Gibt LLM-Statistiken zurück"""
    return {
        "model": llm_service.model,
        "mock_mode": llm_service.mock_mode,
        "total_requests": llm_service.request_count,
        "status": "healthy" if not llm_service.mock_mode else "mock"
    }

async def test_llm_connection_async() -> bool:
    """Testet LLM-Verbindung"""
    try:
        result = await llm_service._make_async_llm_call("Test prompt", max_tokens=10)
        return result.success
    except Exception as e:
        logger.error(f"LLM-Verbindungstest fehlgeschlagen: {str(e)}")
        return False
