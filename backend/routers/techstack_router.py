"""
TechStack Router - API endpoints for template management and project creation.
"""

import json
import os
import shutil
import re
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import httpx

from backend.core import db as _db
from backend.services.project_service import ProjectService, get_project_service
from backend.schemas import (
    ProjectMetadata,
    ProjectListResponse,
    CreateProjectResponse as ProjectCreateResponse,
    MergeProjectsRequest,
    MergedProjectPayload,
    ValidationSummary,
    SendToCodingEngineRequest,
    SendToCodingEngineResponse,
)

# Default Coding Engine URL from environment
# Note: Coding Engine Control Server uses /api/start endpoint (see control_server/server.py)
CODING_ENGINE_URL = os.environ.get("CODING_ENGINE_URL", "http://localhost:8090/api/start")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/techstack", tags=["techstack"])

# Base path for templates
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
PROJECTS_OUTPUT_DIR = Path(__file__).parent.parent.parent / "projects"


# ============================================
# Template Detection Configuration
# ============================================

TEMPLATE_KEYWORDS = {
    "01-web-app": {
        "keywords": [
            "web application", "website", "frontend", "ui", "user interface",
            "dashboard", "admin panel", "saas", "portal", "browser",
            "responsive", "spa", "single page", "react", "next.js", "nextjs"
        ],
        "tech_indicators": ["react", "typescript", "tailwind", "prisma", "postgresql"],
        "category_weight": {"web": 2.0, "frontend": 1.8, "fullstack": 1.5}
    },
    "02-api-service": {
        "keywords": [
            "api", "rest", "restful", "backend", "microservice", "service",
            "endpoint", "server", "http", "json-api", "data service",
            "authentication", "authorization", "crud"
        ],
        "tech_indicators": ["fastapi", "python", "sqlalchemy", "postgresql", "docker"],
        "category_weight": {"backend": 2.0, "api": 1.9, "service": 1.5}
    },
    "03-desktop-electron": {
        "keywords": [
            "desktop", "electron", "cross-platform", "native", "application",
            "offline", "file system", "local storage", "windows app", "mac app",
            "linux app", "system tray", "notifications"
        ],
        "tech_indicators": ["electron", "node", "typescript", "sqlite"],
        "category_weight": {"desktop": 2.0, "application": 1.5}
    },
    "04-mobile-expo": {
        "keywords": [
            "mobile", "app", "ios", "android", "smartphone", "tablet",
            "native", "expo", "react native", "touch", "push notifications"
        ],
        "tech_indicators": ["expo", "react native", "typescript"],
        "category_weight": {"mobile": 2.0, "app": 1.5}
    },
    "05-static-site": {
        "keywords": [
            "static", "blog", "documentation", "landing page", "portfolio",
            "simple website", "html", "markdown", "jamstack"
        ],
        "tech_indicators": ["astro", "markdown", "html", "css"],
        "category_weight": {"web": 1.5, "content": 1.8}
    },
    "06-web3-dapp": {
        "keywords": [
            "blockchain", "web3", "cryptocurrency", "ethereum", "smart contract",
            "dapp", "decentralized", "nft", "token", "wallet", "metamask"
        ],
        "tech_indicators": ["solidity", "ethers", "hardhat", "wagmi"],
        "category_weight": {"blockchain": 2.0, "web3": 2.0}
    },
    "07-data-ml": {
        "keywords": [
            "machine learning", "ml", "ai", "data science", "analytics",
            "prediction", "model", "training", "dataset", "tensorflow",
            "pytorch", "neural network", "classification", "regression"
        ],
        "tech_indicators": ["python", "jupyter", "pandas", "scikit-learn", "tensorflow"],
        "category_weight": {"ml": 2.0, "data": 1.8, "ai": 1.9}
    },
    "08-simulation-cpp": {
        "keywords": [
            "simulation", "physics", "scientific", "numerical", "c++", "cpp",
            "performance", "real-time", "visualization", "modeling",
            "computational", "algorithm"
        ],
        "tech_indicators": ["c++", "cmake", "opengl", "sdl"],
        "category_weight": {"simulation": 2.0, "scientific": 1.8}
    },
    "09-cli-tool": {
        "keywords": [
            "cli", "command line", "terminal", "console", "script", "automation",
            "tool", "utility", "batch", "shell"
        ],
        "tech_indicators": ["python", "typer", "click", "argparse"],
        "category_weight": {"cli": 2.0, "tool": 1.5}
    },
    "10-browser-extension": {
        "keywords": [
            "browser extension", "chrome extension", "firefox addon", "plugin",
            "addon", "content script", "popup"
        ],
        "tech_indicators": ["javascript", "manifest", "chrome api"],
        "category_weight": {"browser": 2.0, "extension": 2.0}
    },
    "11-chatbot": {
        "keywords": [
            "chatbot", "bot", "conversational", "nlp", "chat", "assistant",
            "dialogue", "intent", "response", "telegram", "discord", "slack"
        ],
        "tech_indicators": ["python", "langchain", "openai", "telegram api"],
        "category_weight": {"chatbot": 2.0, "ai": 1.5}
    },
    "12-realtime-socketio": {
        "keywords": [
            "realtime", "real-time", "websocket", "socket", "live", "streaming",
            "push", "notification", "chat", "collaborative", "sync"
        ],
        "tech_indicators": ["socket.io", "websocket", "redis", "pubsub"],
        "category_weight": {"realtime": 2.0, "streaming": 1.8}
    },
    "13-operating-system": {
        "keywords": [
            "operating system", "os", "kernel", "bootloader", "driver",
            "low-level", "assembly", "system programming"
        ],
        "tech_indicators": ["rust", "c", "assembly", "bootloader"],
        "category_weight": {"os": 2.0, "system": 1.8}
    },
    "14-vr-webxr": {
        "keywords": [
            "vr", "virtual reality", "ar", "augmented reality", "webxr",
            "3d", "immersive", "headset", "oculus", "quest"
        ],
        "tech_indicators": ["three.js", "webxr", "a-frame", "babylon"],
        "category_weight": {"vr": 2.0, "ar": 2.0, "3d": 1.5}
    },
    "15-iot-wokwi": {
        "keywords": [
            "iot", "internet of things", "embedded", "sensor", "arduino",
            "esp32", "raspberry pi", "hardware", "microcontroller", "wokwi"
        ],
        "tech_indicators": ["c++", "platformio", "mqtt", "esp32"],
        "category_weight": {"iot": 2.0, "embedded": 1.8}
    }
}


class TemplateInfo(BaseModel):
    """Template metadata model."""
    id: str
    name: str
    description: str
    category: str
    tags: List[str]
    difficulty: str
    estimated_setup_time: str
    tech_stack: dict
    features: List[str]
    prerequisites: List[str]
    placeholders: dict


class CreateProjectRequest(BaseModel):
    """Request model for project creation."""
    template_id: str
    project_name: str
    requirements: Optional[List[dict]] = None
    output_path: Optional[str] = None


class CreateProjectResponse(BaseModel):
    """Response model for project creation."""
    success: bool
    path: Optional[str] = None
    error: Optional[str] = None
    files_created: int = 0


class DetectRequest(BaseModel):
    """Request model for tech stack detection."""
    requirements: List[dict]
    prefer_category: Optional[str] = None
    min_confidence: float = 0.3


class DetectResponse(BaseModel):
    """Response model for tech stack detection."""
    recommended_template: str
    confidence: float
    scores: dict
    reasons: List[str]
    alternative_templates: List[dict]


class MatchRequest(BaseModel):
    """Request model for semantic matching."""
    requirement_text: str
    top_k: int = 5


def load_template_meta(template_dir: Path) -> Optional[dict]:
    """Load meta.json from a template directory."""
    meta_path = template_dir / "meta.json"
    if not meta_path.exists():
        return None

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {meta_path}: {e}")
        return None


def get_all_templates() -> List[dict]:
    """Get all available templates from the templates directory."""
    templates = []

    if not TEMPLATES_DIR.exists():
        return templates

    for item in sorted(TEMPLATES_DIR.iterdir()):
        # Skip base directory and tools
        if item.name.startswith("_") or item.name == "tools" or item.name == "requirements":
            continue

        if item.is_dir():
            meta = load_template_meta(item)
            if meta:
                # Normalize the template data structure
                normalized = {
                    "id": meta.get("id", item.name),
                    "name": meta.get("name", item.name),
                    "description": meta.get("description", ""),
                    "category": meta.get("category", "general"),
                    "tags": meta.get("stack", []),  # stack -> tags for display
                    "difficulty": meta.get("difficulty", "intermediate"),
                    "estimated_setup_time": meta.get("estimated_setup_time", "10 minutes"),
                    "tech_stack": {
                        "stack": meta.get("stack", []),
                        "commands": meta.get("commands", {}),
                        "ports": meta.get("ports", {})
                    },
                    "features": meta.get("features", []),
                    "prerequisites": meta.get("pc_requirements", []),
                    "use_cases": meta.get("use_cases", []),
                    "placeholders": meta.get("placeholders", {}),
                    "version": meta.get("version", "1.0.0")
                }
                templates.append(normalized)

    return templates


def replace_placeholders(content: str, replacements: dict) -> str:
    """Replace placeholders in content."""
    for key, value in replacements.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))
    return content


def generate_project_name_variants(name: str) -> dict:
    """Generate different case variants of the project name."""
    # Clean the name
    clean_name = re.sub(r'[^a-zA-Z0-9\s-]', '', name)

    # Generate variants
    kebab = re.sub(r'[\s_]+', '-', clean_name.lower())
    snake = re.sub(r'[\s-]+', '_', clean_name.lower())
    pascal = ''.join(word.capitalize() for word in re.split(r'[\s_-]+', clean_name))

    return {
        "PROJECT_NAME": name,
        "PROJECT_NAME_KEBAB": kebab,
        "PROJECT_NAME_SNAKE": snake,
        "PROJECT_NAME_PASCAL": pascal,
        "PROJECT_NAME_LOWER": clean_name.lower(),
        "CREATED_AT": datetime.now().isoformat(),
        "YEAR": str(datetime.now().year)
    }


def _analyze_requirements_for_template(requirements: List[dict]) -> dict:
    """
    Analyze requirements and score each template based on keyword matching.
    
    Returns:
        {
            "template_id": {
                "score": float,
                "keyword_matches": [...],
                "tech_matches": [...]
            }
        }
    """
    # Combine all requirement text
    text_corpus = ""
    for req in requirements:
        text = req.get("text") or req.get("title") or ""
        text_corpus += f" {text.lower()} "

        # Include acceptance criteria
        criteria = req.get("acceptance_criteria") or []
        for c in criteria:
            text_corpus += f" {c.lower()} "

        # Include tags
        tags = req.get("tags") or []
        text_corpus += f" {' '.join(tags).lower()} "

    # Score each template
    results = {}

    for template_id, config in TEMPLATE_KEYWORDS.items():
        score = 0.0
        keyword_matches = []
        tech_matches = []

        # Keyword matching
        for keyword in config["keywords"]:
            if keyword.lower() in text_corpus:
                score += 1.0
                keyword_matches.append(keyword)

        # Tech indicator matching (higher weight)
        for tech in config["tech_indicators"]:
            if tech.lower() in text_corpus:
                score += 1.5
                tech_matches.append(tech)

        # Normalize score
        max_possible = len(config["keywords"]) + (len(config["tech_indicators"]) * 1.5)
        normalized_score = score / max_possible if max_possible > 0 else 0

        results[template_id] = {
            "score": normalized_score,
            "raw_score": score,
            "keyword_matches": keyword_matches,
            "tech_matches": tech_matches
        }

    return results


# ============================================
# API Endpoints
# ============================================

@router.post("/detect", response_model=DetectResponse)
async def detect_tech_stack(request: DetectRequest):
    """
    Automatically detect and recommend the best template based on requirements.
    
    Analyzes requirement text for keywords and tech indicators to determine
    the most suitable project template.
    """
    if not request.requirements:
        raise HTTPException(status_code=400, detail="No requirements provided")

    # Analyze requirements
    analysis = _analyze_requirements_for_template(request.requirements)

    # Sort by score
    sorted_templates = sorted(
        analysis.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )

    if not sorted_templates or sorted_templates[0][1]["score"] < request.min_confidence:
        # Default to web-app if no clear match
        return DetectResponse(
            recommended_template="01-web-app",
            confidence=0.3,
            scores={k: v["score"] for k, v in analysis.items()},
            reasons=["No strong template match found, defaulting to web application"],
            alternative_templates=[]
        )

    best_template = sorted_templates[0]
    template_id = best_template[0]
    template_data = best_template[1]

    # Build reasons
    reasons = []
    if template_data["keyword_matches"]:
        reasons.append(f"Matched keywords: {', '.join(template_data['keyword_matches'][:5])}")
    if template_data["tech_matches"]:
        reasons.append(f"Technology indicators: {', '.join(template_data['tech_matches'])}")

    # Get alternatives (top 3 excluding winner)
    alternatives = []
    for t_id, t_data in sorted_templates[1:4]:
        if t_data["score"] >= request.min_confidence:
            alternatives.append({
                "template_id": t_id,
                "confidence": round(t_data["score"], 3),
                "matches": t_data["keyword_matches"][:3]
            })

    return DetectResponse(
        recommended_template=template_id,
        confidence=round(template_data["score"], 3),
        scores={k: round(v["score"], 3) for k, v in analysis.items()},
        reasons=reasons,
        alternative_templates=alternatives
    )


@router.post("/match")
async def match_requirement_to_templates(request: MatchRequest):
    """
    Match a single requirement text to templates using keyword analysis.
    
    Useful for real-time suggestions as requirements are being written.
    """
    # Create a single-requirement analysis
    single_req = [{"text": request.requirement_text}]
    analysis = _analyze_requirements_for_template(single_req)

    # Sort and return top K
    sorted_templates = sorted(
        analysis.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )[:request.top_k]

    matches = []
    for template_id, data in sorted_templates:
        meta = None
        template_dir = TEMPLATES_DIR / template_id
        if template_dir.exists():
            meta = load_template_meta(template_dir)

        matches.append({
            "template_id": template_id,
            "template_name": meta.get("name", template_id) if meta else template_id,
            "confidence": round(data["score"], 3),
            "keyword_matches": data["keyword_matches"],
            "tech_matches": data["tech_matches"]
        })

    return {
        "query": request.requirement_text,
        "matches": matches
    }


@router.get("/templates")
async def list_templates():
    """List all available templates."""
    templates = get_all_templates()
    return {
        "templates": templates,
        "count": len(templates)
    }


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    """Get details for a specific template."""
    templates = get_all_templates()

    for template in templates:
        if template.get("id") == template_id:
            return template

    raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")


@router.post("/create", response_model=CreateProjectResponse)
async def create_project(request: CreateProjectRequest):
    """Create a new project from a template."""
    try:
        # Find the template directory
        template_dir = None
        for item in TEMPLATES_DIR.iterdir():
            if item.is_dir() and item.name.startswith(request.template_id.split("-")[0]):
                meta = load_template_meta(item)
                if meta and meta.get("id") == request.template_id:
                    template_dir = item
                    break

        if not template_dir:
            raise HTTPException(status_code=404, detail=f"Template '{request.template_id}' not found")

        # Load template meta
        meta = load_template_meta(template_dir)
        if not meta:
            raise HTTPException(status_code=500, detail="Failed to load template metadata")

        # Determine output path
        if request.output_path:
            output_dir = Path(request.output_path)
        else:
            output_dir = PROJECTS_OUTPUT_DIR

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate project name variants for placeholders
        placeholders = generate_project_name_variants(request.project_name)

        # Merge with template placeholders
        if meta.get("placeholders"):
            for key, default in meta["placeholders"].items():
                if key not in placeholders:
                    placeholders[key] = default

        # Project destination
        project_name_clean = placeholders["PROJECT_NAME_KEBAB"]
        project_path = output_dir / project_name_clean

        # Check if project already exists
        if project_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Project '{project_name_clean}' already exists at {project_path}"
            )

        # Copy template files
        template_source = template_dir / "template"
        files_created = 0

        if template_source.exists():
            # Copy and process template files
            for src_path in template_source.rglob("*"):
                if src_path.is_file():
                    # Calculate relative path
                    rel_path = src_path.relative_to(template_source)
                    dst_path = project_path / rel_path

                    # Create parent directories
                    dst_path.parent.mkdir(parents=True, exist_ok=True)

                    # Process file content
                    try:
                        content = src_path.read_text(encoding="utf-8")
                        processed_content = replace_placeholders(content, placeholders)
                        dst_path.write_text(processed_content, encoding="utf-8")
                    except UnicodeDecodeError:
                        # Binary file, just copy
                        shutil.copy2(src_path, dst_path)

                    files_created += 1

        # Copy base files
        base_dir = TEMPLATES_DIR / "_base"
        if base_dir.exists():
            for base_file in base_dir.iterdir():
                if base_file.is_file() and base_file.suffix in [".base", ".template"]:
                    # Determine target filename
                    target_name = base_file.stem
                    if target_name.startswith("."):
                        target_name = base_file.name.replace(".base", "").replace(".template", "")

                    dst_path = project_path / target_name
                    if not dst_path.exists():
                        content = base_file.read_text(encoding="utf-8")
                        processed_content = replace_placeholders(content, placeholders)
                        dst_path.write_text(processed_content, encoding="utf-8")
                        files_created += 1

        # Create README with project info
        readme_path = project_path / "README.md"
        if not readme_path.exists():
            readme_content = f"""# {request.project_name}

Generated from template: **{meta['name']}**

## Description

{meta.get('description', 'A new project.')}

## Getting Started

See the [FOLLOW.md](./FOLLOW.md) guide for setup instructions.

## Tech Stack

{json.dumps(meta.get('stack', []), indent=2)}

---

Generated by TechStack Agent on {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
            readme_path.write_text(readme_content, encoding="utf-8")
            files_created += 1

        # Copy FOLLOW.md and CODING_RULES.md if they exist
        for doc_file in ["FOLLOW.md", "CODING_RULES.md"]:
            src_doc = template_dir / doc_file
            if src_doc.exists():
                content = src_doc.read_text(encoding="utf-8")
                processed_content = replace_placeholders(content, placeholders)
                (project_path / doc_file).write_text(processed_content, encoding="utf-8")
                files_created += 1

        # Save requirements if provided
        if request.requirements:
            reqs_dir = project_path / "docs" / "requirements"
            reqs_dir.mkdir(parents=True, exist_ok=True)

            reqs_file = reqs_dir / "imported_requirements.json"
            reqs_file.write_text(json.dumps({
                "imported_at": datetime.now().isoformat(),
                "requirements": request.requirements
            }, indent=2))
            files_created += 1

        # ============================================
        # Persist project metadata to database
        # ============================================
        project_id = None
        requirements_linked = 0
        try:
            conn = _db.get_db()
            try:
                project_service = get_project_service()

                # Extract source file and requirement IDs from requirements
                source_file = None
                requirement_ids = []
                if request.requirements:
                    for req in request.requirements:
                        if req.get("source_file") and not source_file:
                            source_file = req.get("source_file")
                        # Extract requirement ID (try common field names)
                        req_id = req.get("requirement_id") or req.get("id") or req.get("req_id")
                        if req_id:
                            requirement_ids.append(req_id)

                # Create project record
                db_response = project_service.create_project_record(
                    conn=conn,
                    project_name=request.project_name,
                    project_path=str(project_path.absolute()),
                    template_id=request.template_id,
                    template_name=meta.get("name"),
                    template_category=meta.get("category"),
                    tech_stack=meta.get("stack", []),
                    requirements=request.requirements,
                    requirement_ids=requirement_ids,
                    source_file=source_file,
                    metadata={
                        "placeholders": placeholders,
                        "template_version": meta.get("version", "1.0.0"),
                    }
                )
                project_id = db_response.project_id
                requirements_linked = db_response.requirements_linked
                logger.info(f"Project metadata saved to DB: {project_id}")
            finally:
                conn.close()
        except Exception as db_err:
            # Log but don't fail - project was created successfully on filesystem
            logger.warning(f"Failed to persist project metadata to DB: {db_err}")

        return CreateProjectResponse(
            success=True,
            path=str(project_path.absolute()),
            files_created=files_created
        )

    except HTTPException:
        raise
    except Exception as e:
        return CreateProjectResponse(
            success=False,
            error=str(e)
        )


@router.get("/categories")
async def list_categories():
    """List all template categories."""
    templates = get_all_templates()
    categories = set()
    
    for template in templates:
        if "category" in template:
            categories.add(template["category"])
    
    return {
        "categories": sorted(list(categories))
    }

# ============================================
# Knowledge Graph Endpoints
# ============================================

class KGRebuildRequest(BaseModel):
    """Request model for KG rebuild."""
    force: bool = False


class KGUpdateRequest(BaseModel):
    """Request model for KG update with requirements."""
    requirements: List[dict]
    version: str
    template_id: Optional[str] = None


class PipelineProcessRequest(BaseModel):
    """Request model for final pipeline step."""
    validated_requirements: List[dict]
    version: str
    selected_template: Optional[str] = None


class TransformRequest(BaseModel):
    """Request model for requirements transformation."""
    requirements: List[dict]
    template_id: str


@router.post("/kg/rebuild")
async def rebuild_knowledge_graph(request: KGRebuildRequest):
    """
    Rebuild the Knowledge Graph from templates.
    
    Should be called on initial run to build the KG.
    Use force=True to completely rebuild from scratch.
    """
    try:
        from arch_team.agents.techstack_agent import TechStackAgent
        
        agent = TechStackAgent()
        result = agent.rebuild_kg(force=request.force)
        
        return result
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"TechStackAgent not available: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kg/update")
async def update_knowledge_graph(request: KGUpdateRequest):
    """
    Update KG with requirement traces after a processing run.
    
    Creates nodes for requirements and edges to matched templates.
    """
    try:
        from arch_team.agents.techstack_agent import TechStackAgent
        
        agent = TechStackAgent()
        result = agent.update_kg_with_requirements(
            requirements=request.requirements,
            version=request.version,
            template_id=request.template_id
        )
        
        return result
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"TechStackAgent not available: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kg/status")
async def get_kg_status():
    """
    Get Knowledge Graph status and statistics.
    """
    try:
        from arch_team.agents.techstack_agent import TechStackAgent
        
        agent = TechStackAgent()
        client = agent._lazy_client()
        
        # Check if collection exists
        collections = client.get_collections()
        kg_collection = None
        
        for c in collections.collections:
            if c.name == agent._kg_collection:
                kg_collection = client.get_collection(c.name)
                break
        
        if kg_collection:
            return {
                "status": "active",
                "collection": agent._kg_collection,
                "points_count": kg_collection.points_count,
                "vectors_count": kg_collection.vectors_count
            }
        else:
            return {
                "status": "not_initialized",
                "collection": agent._kg_collection,
                "message": "Run /kg/rebuild to initialize the Knowledge Graph"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# ============================================
# Pipeline Integration Endpoints
# ============================================

@router.post("/pipeline/process")
async def process_pipeline_final_step(request: PipelineProcessRequest):
    """
    Execute tech stack selection as the final pipeline step.
    
    Pipeline order: Requirements Extraction → Enhancement → Validation → **Tech Stack Selection**
    
    This endpoint:
    1. Recommends a template if not provided
    2. Transforms requirements with tech stack context
    3. Updates the Knowledge Graph with traces
    """
    try:
        from arch_team.agents.techstack_agent import TechStackAgent
        
        agent = TechStackAgent()
        result = agent.process_pipeline_final_step(
            validated_requirements=request.validated_requirements,
            version=request.version,
            selected_template=request.selected_template
        )
        
        return result
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"TechStackAgent not available: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transform")
async def transform_requirements(request: TransformRequest):
    """
    Transform requirements based on selected tech stack template.
    
    Adds template-specific metadata, implementation hints, and
    tech stack context to each requirement.
    """
    try:
        from arch_team.agents.techstack_agent import TechStackAgent
        
        agent = TechStackAgent()
        result = agent.transform_requirements(
            requirements=request.requirements,
            template_id=request.template_id
        )
        
        return result
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"TechStackAgent not available: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommend")
async def recommend_template(request: DetectRequest):
    """
    Get template recommendation using the TechStackAgent.
    
    Alternative to /detect that uses the agent's recommendation logic.
    """
    try:
        from arch_team.agents.techstack_agent import TechStackAgent
        
        agent = TechStackAgent()
        result = agent.recommend(request.requirements)
        
        return result
    except ImportError as e:
        # Fallback to local detection
        analysis = _analyze_requirements_for_template(request.requirements)
        sorted_templates = sorted(
            analysis.items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )
        
        if sorted_templates:
            best = sorted_templates[0]
            return {
                "recommended_template": best[0],
                "confidence": round(best[1]["score"], 3),
                "reasons": [f"Keywords: {', '.join(best[1]['keyword_matches'][:5])}"],
                "alternatives": [
                    {"template_id": t[0], "confidence": round(t[1]["score"], 3)}
                    for t in sorted_templates[1:4]
                ]
            }
        
        return {
            "recommended_template": "01-web-app",
            "confidence": 0.3,
            "reasons": ["Fallback to default web application"],
            "alternatives": []
        }


# ============================================
# Project Metadata Endpoints
# ============================================

@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Skip N results"),
    template_id: Optional[str] = Query(None, description="Filter by template ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """
    List all generated projects with metadata.

    Returns project records from database with filtering and pagination.
    """
    try:
        conn = _db.get_db()
        try:
            project_service = get_project_service()
            result = project_service.list_projects(
                conn=conn,
                limit=limit,
                offset=offset,
                template_id=template_id,
                category=category,
            )
            return result
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}", response_model=ProjectMetadata)
async def get_project(
    project_id: str,
    include_requirements: bool = Query(False, description="Include linked requirement IDs"),
):
    """
    Get project metadata by ID.

    Returns full project details including validation summary and tech stack.
    """
    try:
        conn = _db.get_db()
        try:
            project_service = get_project_service()
            project = project_service.get_project(
                conn=conn,
                project_id=project_id,
                include_requirements=include_requirements,
            )
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project '{project_id}' not found"
                )
            return project
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/requirements")
async def get_project_requirements(project_id: str):
    """
    Get all requirements linked to a project.

    Returns requirement manifests that were imported when the project was created.
    """
    try:
        conn = _db.get_db()
        try:
            project_service = get_project_service()

            # First check if project exists
            project = project_service.get_project(conn, project_id)
            if not project:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project '{project_id}' not found"
                )

            requirements = project_service.get_project_requirements(conn, project_id)
            return {
                "project_id": project_id,
                "requirements": requirements,
                "count": len(requirements)
            }
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get requirements for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """
    Delete a project metadata record.

    Note: This only deletes the database record, NOT the project files on disk.
    """
    try:
        conn = _db.get_db()
        try:
            project_service = get_project_service()
            deleted = project_service.delete_project(conn, project_id)
            if not deleted:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project '{project_id}' not found"
                )
            return {
                "success": True,
                "message": f"Project '{project_id}' deleted",
                "note": "Project files on disk were NOT deleted"
            }
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Project Merge & Coding Engine Endpoints
# ============================================

def _load_requirements_from_json(project_path: str) -> List[dict]:
    """
    Load requirements from project's JSON file on disk.

    Fallback for projects where requirements were not linked in DB.
    """
    try:
        json_path = Path(project_path) / "docs" / "requirements" / "imported_requirements.json"
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("requirements", [])
    except Exception as e:
        logger.warning(f"Failed to load requirements from {project_path}: {e}")
    return []


def _transform_for_coding_engine(merged: MergedProjectPayload, output_dir: Optional[str] = None) -> dict:
    """
    Transform merged payload to Coding Engine StartRequest format.

    The Coding Engine Control Server (POST /api/start) expects:
    - requirements_json: dict (NOT string) containing requirements
    - output_dir: str (optional, for generated code)
    - run_mode: "hybrid" | "society_hybrid"
    - max_concurrent: int (1-10, default 2)
    - slice_size: int (1-100, default 3)

    The requirements_json structure:
    {
        "meta": {generated_at, source_file, version},
        "requirements": [{req_id, title, tag, evidence_refs}],
        "tech_stack": {...}  # Optional
    }
    """
    # Transform requirements: id→req_id, category→tag
    transformed_reqs = []
    for req in merged.requirements:
        transformed_reqs.append({
            "req_id": req.get("id") or req.get("req_id", ""),
            "title": req.get("title", ""),
            "tag": req.get("category") or req.get("tag", "functional"),
            "evidence_refs": req.get("evidence_refs", [])
        })

    # Build requirements_json structure (as dict, not string)
    requirements_payload = {
        "meta": {
            "generated_at": merged.merged_at,
            "source_file": ", ".join(merged.projects),
            "version": "v1"
        },
        "requirements": transformed_reqs
    }

    # Add tech_stack if available
    if merged.tech_stack:
        # Convert list to structured object if needed
        requirements_payload["tech_stack"] = {
            "id": "merged_stack",
            "name": "Merged TechStack",
            "technologies": merged.tech_stack
        }

    # Generate output_dir from first project ID if not provided
    if not output_dir and merged.projects:
        output_dir = f"project_{merged.projects[0][:8]}"

    # Return StartRequest-compatible payload
    return {
        "requirements_json": requirements_payload,  # Dict, not string
        "output_dir": output_dir,
        "run_mode": "hybrid",
        "max_concurrent": 2,
        "slice_size": 3,
        "enable_preview": True,
        "no_timeout": True
    }


@router.post("/merge", response_model=MergedProjectPayload)
async def merge_projects(request: MergeProjectsRequest):
    """
    Merge requirements from multiple projects into a single payload.

    Combines requirements and tech stacks from selected projects.
    Use include_failed=true to include non-validated requirements.
    """
    if not request.project_ids:
        raise HTTPException(status_code=400, detail="No project IDs provided")

    try:
        conn = _db.get_db()
        try:
            project_service = get_project_service()
            merged_requirements = []
            tech_stacks = set()
            total_passed = 0
            total_failed = 0
            total_score = 0.0

            for project_id in request.project_ids:
                # Get project metadata
                project = project_service.get_project(conn, project_id)
                if not project:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Project '{project_id}' not found"
                    )

                # Get project requirements (try DB first, then JSON fallback)
                requirements = project_service.get_project_requirements(conn, project_id)

                # Fallback: load from JSON file if DB has no linked requirements
                if not requirements and project.project_path:
                    logger.info(f"Loading requirements from JSON for project {project_id}")
                    requirements = _load_requirements_from_json(project.project_path)

                # Filter based on include_failed flag
                for req in requirements:
                    # Handle both dict and Row objects
                    if hasattr(req, 'keys'):
                        req = dict(req)

                    passed = req.get('validation_passed', False)
                    score = req.get('validation_score', 0.0)

                    if passed:
                        total_passed += 1
                    else:
                        total_failed += 1

                    total_score += score if score else 0.0

                    # Include requirement if passed OR include_failed is True
                    if passed or request.include_failed:
                        # Add project context to requirement
                        req['source_project_id'] = project_id
                        req['source_project_name'] = project.project_name
                        merged_requirements.append(req)

                # Merge tech stacks
                if project.tech_stack:
                    tech_stacks.update(project.tech_stack)

            # Calculate validation summary
            total_count = total_passed + total_failed
            avg_score = total_score / total_count if total_count > 0 else 0.0

            return MergedProjectPayload(
                projects=request.project_ids,
                requirements=merged_requirements,
                tech_stack=list(tech_stacks),
                validation_summary=ValidationSummary(
                    total=total_count,
                    passed=total_passed,
                    failed=total_failed,
                    avg_score=round(avg_score, 3)
                ),
                merged_at=datetime.now().isoformat()
            )
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to merge projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-to-engine", response_model=SendToCodingEngineResponse)
async def send_to_coding_engine(request: SendToCodingEngineRequest):
    """
    Merge projects and send to Coding Engine.

    1. Merges requirements from selected projects
    2. Sends merged payload to Coding Engine API
    3. Returns engine response

    Configure default URL via CODING_ENGINE_URL environment variable.
    """
    if not request.project_ids:
        raise HTTPException(status_code=400, detail="No project IDs provided")

    try:
        # 1. Merge projects
        merged = await merge_projects(MergeProjectsRequest(
            project_ids=request.project_ids,
            include_failed=request.include_failed
        ))

        # 2. Determine target URL
        target_url = request.coding_engine_url or CODING_ENGINE_URL
        logger.info(f"Sending {len(merged.requirements)} requirements to Coding Engine at {target_url}")

        # 3. Transform payload for Coding Engine format
        transformed_payload = _transform_for_coding_engine(merged)
        logger.debug(f"Transformed payload: project_id={transformed_payload['project_id']}, "
                     f"requirements_count={len(merged.requirements)}")

        # 4. Send to Coding Engine
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    target_url,
                    json=transformed_payload,
                    timeout=30.0
                )

                # Parse engine response
                engine_response = None
                try:
                    engine_response = response.json()
                except Exception:
                    engine_response = {"raw": response.text[:500]}

                if response.status_code in (200, 201):  # 201 = Created
                    logger.info(f"Successfully sent to Coding Engine: {len(merged.requirements)} requirements")
                    return SendToCodingEngineResponse(
                        success=True,
                        projects_sent=len(request.project_ids),
                        requirements_sent=len(merged.requirements),
                        engine_response=engine_response
                    )
                else:
                    logger.warning(f"Coding Engine returned {response.status_code}: {response.text[:200]}")
                    return SendToCodingEngineResponse(
                        success=False,
                        projects_sent=len(request.project_ids),
                        requirements_sent=0,
                        engine_response=engine_response,
                        error=f"Coding Engine returned status {response.status_code}"
                    )

            except httpx.TimeoutException:
                logger.error(f"Timeout connecting to Coding Engine at {target_url}")
                return SendToCodingEngineResponse(
                    success=False,
                    projects_sent=len(request.project_ids),
                    requirements_sent=0,
                    error=f"Timeout connecting to Coding Engine at {target_url}"
                )
            except httpx.ConnectError as e:
                logger.error(f"Cannot connect to Coding Engine at {target_url}: {e}")
                return SendToCodingEngineResponse(
                    success=False,
                    projects_sent=len(request.project_ids),
                    requirements_sent=0,
                    error=f"Cannot connect to Coding Engine at {target_url}"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send to Coding Engine: {e}")
        return SendToCodingEngineResponse(
            success=False,
            projects_sent=len(request.project_ids) if request.project_ids else 0,
            requirements_sent=0,
            error=str(e)
        )