# -*- coding: utf-8 -*-
"""
Tech Stack Agent
================

Agent responsible for:
1. Analyzing requirements and recommending tech stack templates
2. Maintaining Knowledge Graph integration
3. Transforming requirements based on selected tech stack
4. Rebuilding KG on initial run and updating after processing

Pipeline Position: FINAL STEP after Requirements → Enhancement → Validation

Usage:
    agent = TechStackAgent()
    recommendation = agent.recommend(requirements)
    transformed = agent.transform_requirements(requirements, template_id)
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..runtime.logging import get_logger

logger = get_logger("agents.techstack")

# Template keywords configuration
TEMPLATE_KEYWORDS = {
    "01-web-app": {
        "keywords": ["web", "website", "frontend", "ui", "dashboard", "browser", "responsive", "react"],
        "tech_indicators": ["react", "typescript", "nextjs", "tailwind"],
        "categories": ["web", "frontend", "fullstack"],
    },
    "02-api-service": {
        "keywords": ["api", "rest", "backend", "microservice", "endpoint", "server", "crud"],
        "tech_indicators": ["fastapi", "python", "sqlalchemy", "postgresql"],
        "categories": ["backend", "api", "service"],
    },
    "03-desktop-electron": {
        "keywords": ["desktop", "electron", "native", "offline", "windows", "mac", "linux"],
        "tech_indicators": ["electron", "node", "typescript", "sqlite"],
        "categories": ["desktop", "application"],
    },
    "04-mobile-expo": {
        "keywords": ["mobile", "app", "ios", "android", "smartphone", "tablet"],
        "tech_indicators": ["expo", "react native", "typescript"],
        "categories": ["mobile", "app"],
    },
    "05-static-site": {
        "keywords": ["static", "blog", "documentation", "landing", "portfolio"],
        "tech_indicators": ["astro", "markdown", "html"],
        "categories": ["web", "content"],
    },
    "06-web3-dapp": {
        "keywords": ["blockchain", "web3", "ethereum", "smart contract", "dapp", "nft"],
        "tech_indicators": ["solidity", "ethers", "hardhat"],
        "categories": ["blockchain", "web3"],
    },
    "07-data-ml": {
        "keywords": ["machine learning", "ml", "ai", "data science", "analytics", "model"],
        "tech_indicators": ["python", "jupyter", "pandas", "tensorflow"],
        "categories": ["ml", "data", "ai"],
    },
    "08-simulation-cpp": {
        "keywords": ["simulation", "physics", "scientific", "c++", "performance"],
        "tech_indicators": ["c++", "cmake", "opengl"],
        "categories": ["simulation", "scientific"],
    },
    "09-cli-tool": {
        "keywords": ["cli", "command line", "terminal", "script", "automation"],
        "tech_indicators": ["python", "typer", "click"],
        "categories": ["cli", "tool"],
    },
    "10-browser-extension": {
        "keywords": ["browser extension", "chrome", "firefox", "addon"],
        "tech_indicators": ["javascript", "manifest"],
        "categories": ["browser", "extension"],
    },
    "11-chatbot": {
        "keywords": ["chatbot", "bot", "nlp", "assistant", "dialogue"],
        "tech_indicators": ["python", "langchain", "openai"],
        "categories": ["chatbot", "ai"],
    },
    "12-realtime-socketio": {
        "keywords": ["realtime", "websocket", "live", "streaming", "push"],
        "tech_indicators": ["socket.io", "websocket", "redis"],
        "categories": ["realtime", "streaming"],
    },
    "13-operating-system": {
        "keywords": ["operating system", "kernel", "bootloader", "driver"],
        "tech_indicators": ["rust", "c", "assembly"],
        "categories": ["os", "system"],
    },
    "14-vr-webxr": {
        "keywords": ["vr", "virtual reality", "ar", "webxr", "3d"],
        "tech_indicators": ["three.js", "webxr", "a-frame"],
        "categories": ["vr", "ar", "3d"],
    },
    "15-iot-wokwi": {
        "keywords": ["iot", "embedded", "sensor", "arduino", "esp32"],
        "tech_indicators": ["c++", "platformio", "mqtt"],
        "categories": ["iot", "embedded"],
    },
}


class TechStackAgent:
    """
    Agent for tech stack recommendations and KG integration.
    
    Responsibilities:
    - Analyze requirements for tech stack recommendation
    - Maintain traceability between requirements and templates
    - Transform requirements based on selected template
    - Update Knowledge Graph after processing runs
    """
    
    TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
    
    def __init__(self, qdrant_url: Optional[str] = None, api_key: Optional[str] = None):
        self.qdrant_url = qdrant_url or os.environ.get("QDRANT_URL", "http://localhost")
        self.qdrant_port = os.environ.get("QDRANT_PORT", "6401")
        self.api_key = api_key or os.environ.get("QDRANT_API_KEY")
        self._qdrant = None
        self._kg_collection = "techstack_kg"
        
    def _lazy_client(self):
        """Lazy load Qdrant client."""
        if self._qdrant is None:
            try:
                from qdrant_client import QdrantClient
                url = f"{self.qdrant_url}:{self.qdrant_port}"
                self._qdrant = QdrantClient(url=url, api_key=self.api_key)
            except Exception as e:
                logger.error(f"Qdrant client init failed: {e}")
                raise
        return self._qdrant
    
    # ================================================================
    # Knowledge Graph Management
    # ================================================================
    
    def rebuild_kg(self, force: bool = False) -> Dict[str, Any]:
        """
        Rebuild the Knowledge Graph from templates.
        
        This should be called on initial run to build the KG,
        and can be called with force=True to completely rebuild.
        
        Args:
            force: If True, deletes existing KG and rebuilds from scratch
        
        Returns:
            {"success": True, "templates_indexed": int, "nodes_created": int}
        """
        try:
            client = self._lazy_client()
            from qdrant_client import models as qmodels
            
            # Check if collection exists
            collections = client.get_collections()
            exists = any(c.name == self._kg_collection for c in collections.collections)
            
            if exists and force:
                client.delete_collection(self._kg_collection)
                logger.info(f"Deleted existing KG collection {self._kg_collection}")
                exists = False
            
            if not exists:
                # Create collection with 384 dimensions (for template descriptions)
                client.create_collection(
                    collection_name=self._kg_collection,
                    vectors_config=qmodels.VectorParams(
                        size=384,
                        distance=qmodels.Distance.COSINE
                    )
                )
                logger.info(f"Created KG collection {self._kg_collection}")
            
            # Index templates
            templates_indexed = 0
            nodes_created = 0
            
            for template_dir in sorted(self.TEMPLATES_DIR.iterdir()):
                if template_dir.name.startswith("_") or template_dir.name in ["tools", "requirements"]:
                    continue
                
                if template_dir.is_dir():
                    meta_path = template_dir / "meta.json"
                    if meta_path.exists():
                        try:
                            meta = json.loads(meta_path.read_text())
                            
                            # Create template node
                            template_id = meta.get("id", template_dir.name)
                            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"template:{template_id}"))
                            
                            # Create simple vector from keywords
                            keywords = TEMPLATE_KEYWORDS.get(template_id, {}).get("keywords", [])
                            tech_indicators = TEMPLATE_KEYWORDS.get(template_id, {}).get("tech_indicators", [])
                            
                            # Simple bag-of-words vector (normalized)
                            vector = self._create_simple_vector(
                                keywords + tech_indicators + meta.get("features", [])
                            )
                            
                            payload = {
                                "node_type": "template",
                                "template_id": template_id,
                                "name": meta.get("name", template_id),
                                "description": meta.get("description", ""),
                                "category": meta.get("category", "general"),
                                "stack": meta.get("stack", []),
                                "features": meta.get("features", []),
                                "keywords": keywords,
                                "tech_indicators": tech_indicators,
                                "indexed_at": datetime.utcnow().isoformat() + "Z"
                            }
                            
                            client.upsert(
                                collection_name=self._kg_collection,
                                points=[qmodels.PointStruct(id=point_id, vector=vector, payload=payload)]
                            )
                            
                            templates_indexed += 1
                            nodes_created += 1
                            
                        except Exception as e:
                            logger.warning(f"Failed to index template {template_dir.name}: {e}")
            
            logger.info(f"KG rebuilt: {templates_indexed} templates, {nodes_created} nodes")
            
            return {
                "success": True,
                "templates_indexed": templates_indexed,
                "nodes_created": nodes_created,
                "collection": self._kg_collection
            }
            
        except Exception as e:
            logger.error(f"KG rebuild failed: {e}")
            return {"success": False, "error": str(e)}
    
    def update_kg_with_requirements(
        self,
        requirements: List[Dict[str, Any]],
        version: str,
        template_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update KG with requirement traces after a processing run.
        
        Creates nodes for requirements and edges to matched templates.
        
        Args:
            requirements: List of processed requirements
            version: Requirements version (e.g., "v1", "v2")
            template_id: Optional selected template to create strong trace
        
        Returns:
            {"success": True, "requirements_added": int, "traces_created": int}
        """
        try:
            client = self._lazy_client()
            from qdrant_client import models as qmodels
            
            requirements_added = 0
            traces_created = 0
            
            for req in requirements:
                req_id = req.get("req_id") or req.get("id") or ""
                if not req_id:
                    continue
                
                # Create requirement node
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"req:{req_id}:{version}"))
                
                title = req.get("title") or req.get("text") or ""
                tags = req.get("tags") or []
                
                # Create vector from requirement text
                vector = self._create_simple_vector([title] + tags)
                
                payload = {
                    "node_type": "requirement",
                    "req_id": req_id,
                    "version": version,
                    "title": title,
                    "tag": req.get("tag") or req.get("category") or "",
                    "tags": tags,
                    "selected_template": template_id,
                    "indexed_at": datetime.utcnow().isoformat() + "Z"
                }
                
                # Add trace to selected template if specified
                if template_id:
                    payload["trace_to"] = template_id
                    traces_created += 1
                
                client.upsert(
                    collection_name=self._kg_collection,
                    points=[qmodels.PointStruct(id=point_id, vector=vector, payload=payload)]
                )
                
                requirements_added += 1
            
            logger.info(f"KG updated: {requirements_added} requirements, {traces_created} traces")
            
            return {
                "success": True,
                "requirements_added": requirements_added,
                "traces_created": traces_created,
                "version": version
            }
            
        except Exception as e:
            logger.error(f"KG update failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _create_simple_vector(self, terms: List[str]) -> List[float]:
        """Create a simple normalized vector from terms (for demo/fallback)."""
        # Simple hash-based projection to 384 dimensions
        vector = [0.0] * 384
        
        for term in terms:
            if not term:
                continue
            term_lower = term.lower()
            for i, char in enumerate(term_lower):
                idx = (ord(char) + i * 7) % 384
                vector[idx] += 0.1
        
        # Normalize
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        
        return vector
    
    # ================================================================
    # Template Recommendation
    # ================================================================
    
    def recommend(self, requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze requirements and recommend the best tech stack template.
        
        This is the main entry point for template recommendation.
        
        Args:
            requirements: List of requirement dicts
        
        Returns:
            {
                "recommended_template": "01-web-app",
                "confidence": 0.85,
                "reasons": [...],
                "alternatives": [...]
            }
        """
        if not requirements:
            return {
                "recommended_template": "01-web-app",
                "confidence": 0.3,
                "reasons": ["No requirements provided, defaulting to web application"],
                "alternatives": []
            }
        
        # Build text corpus from requirements
        text_corpus = self._build_corpus(requirements)
        
        # Score each template
        scores = {}
        for template_id, config in TEMPLATE_KEYWORDS.items():
            score = 0.0
            keyword_matches = []
            tech_matches = []
            
            for kw in config["keywords"]:
                if kw.lower() in text_corpus:
                    score += 1.0
                    keyword_matches.append(kw)
            
            for tech in config["tech_indicators"]:
                if tech.lower() in text_corpus:
                    score += 1.5
                    tech_matches.append(tech)
            
            max_possible = len(config["keywords"]) + len(config["tech_indicators"]) * 1.5
            normalized = score / max_possible if max_possible > 0 else 0
            
            scores[template_id] = {
                "score": normalized,
                "keyword_matches": keyword_matches,
                "tech_matches": tech_matches
            }
        
        # Sort by score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
        
        if not sorted_scores or sorted_scores[0][1]["score"] < 0.1:
            return {
                "recommended_template": "01-web-app",
                "confidence": 0.3,
                "reasons": ["No clear template match, defaulting to web application"],
                "alternatives": []
            }
        
        best = sorted_scores[0]
        template_id = best[0]
        data = best[1]
        
        reasons = []
        if data["keyword_matches"]:
            reasons.append(f"Keywords: {', '.join(data['keyword_matches'][:5])}")
        if data["tech_matches"]:
            reasons.append(f"Technologies: {', '.join(data['tech_matches'])}")
        
        alternatives = [
            {"template_id": t[0], "confidence": round(t[1]["score"], 3)}
            for t in sorted_scores[1:4]
            if t[1]["score"] >= 0.2
        ]
        
        return {
            "recommended_template": template_id,
            "confidence": round(data["score"], 3),
            "reasons": reasons,
            "alternatives": alternatives
        }
    
    def _build_corpus(self, requirements: List[Dict[str, Any]]) -> str:
        """Build text corpus from requirements for keyword matching."""
        corpus = ""
        for req in requirements:
            corpus += f" {(req.get('title') or req.get('text') or '').lower()} "
            for ac in (req.get('acceptance_criteria') or []):
                corpus += f" {ac.lower()} "
            for tag in (req.get('tags') or []):
                corpus += f" {tag.lower()} "
        return corpus
    
    # ================================================================
    # Requirements Transformation
    # ================================================================
    
    def transform_requirements(
        self,
        requirements: List[Dict[str, Any]],
        template_id: str
    ) -> Dict[str, Any]:
        """
        Transform requirements based on selected tech stack template.
        
        Adds template-specific metadata, implementation hints, and
        tech stack context to each requirement.
        
        Args:
            requirements: List of validated requirements
            template_id: Selected template ID (e.g., "01-web-app")
        
        Returns:
            {
                "requirements": [...transformed...],
                "template": {...template_meta...},
                "transformation_applied": True
            }
        """
        # Load template meta
        template_meta = self._load_template_meta(template_id)
        if not template_meta:
            return {
                "requirements": requirements,
                "template": None,
                "transformation_applied": False,
                "error": f"Template {template_id} not found"
            }
        
        template_config = TEMPLATE_KEYWORDS.get(template_id, {})
        
        transformed = []
        for req in requirements:
            req_copy = dict(req)
            
            # Add template context
            req_copy["template_context"] = {
                "template_id": template_id,
                "template_name": template_meta.get("name", template_id),
                "categories": template_config.get("categories", [])
            }
            
            # Add implementation hints based on template
            hints = self._generate_implementation_hints(req, template_id, template_meta)
            if hints:
                req_copy["implementation_hints"] = hints
            
            # Add tech stack reference
            req_copy["tech_stack"] = {
                "stack": template_meta.get("stack", []),
                "commands": template_meta.get("commands", {})
            }
            
            transformed.append(req_copy)
        
        return {
            "requirements": transformed,
            "template": {
                "id": template_id,
                "name": template_meta.get("name", template_id),
                "stack": template_meta.get("stack", []),
                "features": template_meta.get("features", [])
            },
            "transformation_applied": True,
            "transformed_count": len(transformed)
        }
    
    def _load_template_meta(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Load template meta.json."""
        for template_dir in self.TEMPLATES_DIR.iterdir():
            if template_dir.is_dir():
                meta_path = template_dir / "meta.json"
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text())
                        if meta.get("id") == template_id:
                            return meta
                    except Exception:
                        pass
        return None
    
    def _generate_implementation_hints(
        self,
        requirement: Dict[str, Any],
        template_id: str,
        template_meta: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate implementation hints based on requirement and template."""
        hints = {
            "files": [],
            "patterns": [],
            "libraries": []
        }
        
        title = (requirement.get("title") or requirement.get("text") or "").lower()
        tag = (requirement.get("tag") or "").lower()
        
        # Web app hints
        if template_id in ["01-web-app", "05-static-site"]:
            if "ui" in title or "interface" in title or "display" in title:
                hints["files"].append("app/components/")
                hints["patterns"].append("React Component")
            if "api" in title or "data" in title:
                hints["files"].append("app/api/")
                hints["patterns"].append("API Route Handler")
            if "database" in title or "store" in title:
                hints["files"].append("prisma/schema.prisma")
                hints["libraries"].append("Prisma ORM")
        
        # API service hints
        elif template_id == "02-api-service":
            if "endpoint" in title or "api" in title:
                hints["files"].append("app/api/v1/endpoints/")
                hints["patterns"].append("FastAPI Router")
            if "database" in title or "model" in title:
                hints["files"].append("app/models/")
                hints["libraries"].append("SQLAlchemy")
        
        # Desktop/Electron hints
        elif template_id == "03-desktop-electron":
            if "file" in title or "local" in title:
                hints["files"].append("electron/ipc/fileHandlers.ts")
                hints["patterns"].append("IPC Handler")
            if "database" in title:
                hints["files"].append("electron/services/database.ts")
                hints["libraries"].append("better-sqlite3")
        
        # Remove empty hints
        hints = {k: v for k, v in hints.items() if v}
        
        return hints if hints else None
    
    # ================================================================
    # Pipeline Integration
    # ================================================================
    
    def process_pipeline_final_step(
        self,
        validated_requirements: List[Dict[str, Any]],
        version: str,
        selected_template: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute tech stack selection as the final pipeline step.
        
        Pipeline: Extract → Enhance → Validate → **Tech Stack Select**
        
        Args:
            validated_requirements: Requirements after validation step
            version: Version string for KG storage
            selected_template: Pre-selected template or None for auto-detect
        
        Returns:
            Complete transformed requirements with tech stack applied
        """
        # Step 1: Recommend template if not selected
        if not selected_template:
            recommendation = self.recommend(validated_requirements)
            selected_template = recommendation["recommended_template"]
            confidence = recommendation["confidence"]
        else:
            confidence = 1.0  # User-selected
        
        # Step 2: Transform requirements
        transformation = self.transform_requirements(validated_requirements, selected_template)
        
        # Step 3: Update KG with traces
        kg_result = self.update_kg_with_requirements(
            validated_requirements,
            version,
            selected_template
        )
        
        return {
            "pipeline_step": "tech_stack_selection",
            "template_id": selected_template,
            "confidence": confidence,
            "requirements": transformation["requirements"],
            "template_meta": transformation.get("template"),
            "transformation_applied": transformation["transformation_applied"],
            "kg_updated": kg_result.get("success", False),
            "kg_traces": kg_result.get("traces_created", 0),
            "processed_at": datetime.utcnow().isoformat() + "Z"
        }