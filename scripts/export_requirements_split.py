#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export Requirements to separate JSON files:
1. requirements.json - Core requirements with evidence_ref_ids (not full refs)
2. evidence_refs.json - All evidence references by sha1
3. requirements_with_techstack.json - Full requirements + tech stack at the end
"""
import json
import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List, Set


def generate_evidence_id(ref: Dict[str, Any]) -> str:
    """Generate a unique ID for an evidence reference."""
    key = f"{ref.get('sourceFile', '')}:{ref.get('sha1', '')}:{ref.get('chunkIndex', 0)}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def extract_evidence_refs(requirements: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Extract all unique evidence references from requirements."""
    evidence_map: Dict[str, Dict[str, Any]] = {}
    
    for req in requirements:
        refs = req.get("evidence_refs") or []
        for ref in refs:
            ev_id = generate_evidence_id(ref)
            if ev_id not in evidence_map:
                evidence_map[ev_id] = {
                    "id": ev_id,
                    "sourceFile": ref.get("sourceFile", ""),
                    "sha1": ref.get("sha1", ""),
                    "chunkIndex": ref.get("chunkIndex", 0),
                    "referenced_by": []
                }
            # Track which requirements reference this evidence
            req_id = req.get("req_id", "")
            if req_id and req_id not in evidence_map[ev_id]["referenced_by"]:
                evidence_map[ev_id]["referenced_by"].append(req_id)
    
    return evidence_map


def transform_requirements(requirements: List[Dict[str, Any]], evidence_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform requirements to use evidence_ref_ids instead of full refs."""
    transformed = []
    
    for req in requirements:
        new_req = {
            "req_id": req.get("req_id", ""),
            "title": req.get("title", ""),
            "tag": req.get("tag", ""),
            "evidence_ref_ids": []  # Just IDs, not full refs
        }
        
        # Convert evidence_refs to IDs
        refs = req.get("evidence_refs") or []
        for ref in refs:
            ev_id = generate_evidence_id(ref)
            if ev_id not in new_req["evidence_ref_ids"]:
                new_req["evidence_ref_ids"].append(ev_id)
        
        transformed.append(new_req)
    
    return transformed


def load_tech_stack_template(template_id: str = "web_app_react") -> Dict[str, Any]:
    """Load a tech stack template."""
    template_path = f"config/techstack_templates/{template_id}.json"
    
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # Default tech stack if template not found
    return {
        "id": template_id,
        "name": "Default Stack",
        "frontend": {"framework": "React", "language": "TypeScript"},
        "backend": {"framework": "FastAPI", "language": "Python"},
        "database": {"type": "PostgreSQL"},
        "deployment": {"platform": "Docker"}
    }


def detect_tech_stack_from_requirements(requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze requirements and detect recommended tech stack."""
    # Analyze requirements text for keywords
    all_text = " ".join([r.get("title", "").lower() for r in requirements])
    
    recommendations = {
        "detected_requirements": [],
        "recommended_template": "web_app_react",
        "confidence": 0.0,
        "reasons": []
    }
    
    # Check for web-related keywords
    if any(w in all_text for w in ["web", "browser", "http", "api", "rest"]):
        recommendations["detected_requirements"].append("web_application")
        recommendations["reasons"].append("Requirements mention web/browser/API functionality")
        recommendations["confidence"] += 0.3
    
    # Check for real-time features
    if any(w in all_text for w in ["real-time", "realtime", "live", "websocket", "stream"]):
        recommendations["detected_requirements"].append("real_time")
        recommendations["reasons"].append("Real-time data streaming mentioned")
        recommendations["confidence"] += 0.2
    
    # Check for monitoring
    if any(w in all_text for w in ["monitor", "dashboard", "visualization", "chart", "graph"]):
        recommendations["detected_requirements"].append("monitoring")
        recommendations["reasons"].append("Monitoring/visualization requirements detected")
        recommendations["confidence"] += 0.2
    
    # Check for database needs
    if any(w in all_text for w in ["store", "database", "persist", "save", "history"]):
        recommendations["detected_requirements"].append("data_persistence")
        recommendations["reasons"].append("Data persistence requirements detected")
        recommendations["confidence"] += 0.15
    
    # Check for port/process management specific
    if any(w in all_text for w in ["port", "process", "pid", "system"]):
        recommendations["detected_requirements"].append("system_management")
        recommendations["reasons"].append("System/process management functionality")
        recommendations["recommended_template"] = "web_app_react"  # Web app with system backend
        recommendations["confidence"] += 0.15
    
    return recommendations


def main():
    """Main export function."""
    input_file = "debug/requirements_20251128_161731.json"
    output_dir = "data/exported"
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Load source data
    print(f"Loading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    requirements = data.get("requirements", [])
    print(f"Loaded {len(requirements)} requirements")
    
    # 1. Extract evidence refs to separate file
    print("\n1. Extracting evidence references...")
    evidence_map = extract_evidence_refs(requirements)
    evidence_list = list(evidence_map.values())
    
    evidence_output = {
        "meta": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "source_file": input_file,
            "total_evidence_refs": len(evidence_list)
        },
        "evidence_refs": evidence_list
    }
    
    evidence_path = os.path.join(output_dir, "evidence_refs.json")
    with open(evidence_path, 'w', encoding='utf-8') as f:
        json.dump(evidence_output, f, indent=2, ensure_ascii=False)
    print(f"   Saved {len(evidence_list)} evidence refs to {evidence_path}")
    
    # 2. Transform requirements (without full evidence_refs)
    print("\n2. Transforming requirements...")
    transformed_reqs = transform_requirements(requirements, evidence_map)
    
    requirements_output = {
        "meta": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "source_file": input_file,
            "version": "v1",
            "total_requirements": len(transformed_reqs),
            "evidence_refs_file": "evidence_refs.json"
        },
        "requirements": transformed_reqs
    }
    
    reqs_path = os.path.join(output_dir, "requirements.json")
    with open(reqs_path, 'w', encoding='utf-8') as f:
        json.dump(requirements_output, f, indent=2, ensure_ascii=False)
    print(f"   Saved {len(transformed_reqs)} requirements to {reqs_path}")
    
    # 3. Detect and add tech stack
    print("\n3. Detecting tech stack from requirements...")
    tech_stack_recommendation = detect_tech_stack_from_requirements(requirements)
    
    # Load recommended template
    template_id = tech_stack_recommendation["recommended_template"]
    tech_stack = load_tech_stack_template(template_id)
    
    # Save tech stack separately
    tech_stack_output = {
        "meta": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "based_on_requirements": input_file,
            "detection": tech_stack_recommendation
        },
        "tech_stack": tech_stack
    }
    
    tech_path = os.path.join(output_dir, "tech_stack.json")
    with open(tech_path, 'w', encoding='utf-8') as f:
        json.dump(tech_stack_output, f, indent=2, ensure_ascii=False)
    print(f"   Saved tech stack to {tech_path}")
    print(f"   Recommended template: {template_id}")
    print(f"   Confidence: {tech_stack_recommendation['confidence']:.0%}")
    print(f"   Reasons: {', '.join(tech_stack_recommendation['reasons'])}")
    
    # 4. Create full export with tech stack at the end
    print("\n4. Creating full export with tech stack...")
    full_output = {
        "meta": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "source_file": input_file,
            "version": "v1"
        },
        "requirements": requirements,  # Full requirements with evidence_refs
        "tech_stack": tech_stack,
        "tech_stack_recommendation": tech_stack_recommendation
    }
    
    full_path = os.path.join(output_dir, "requirements_with_techstack.json")
    with open(full_path, 'w', encoding='utf-8') as f:
        json.dump(full_output, f, indent=2, ensure_ascii=False)
    print(f"   Saved full export to {full_path}")
    
    print("\n" + "="*60)
    print("EXPORT COMPLETE")
    print("="*60)
    print(f"\nOutput files in {output_dir}/:")
    print(f"  - requirements.json        ({len(transformed_reqs)} reqs, refs as IDs)")
    print(f"  - evidence_refs.json       ({len(evidence_list)} evidence refs)")
    print(f"  - tech_stack.json          (recommended: {template_id})")
    print(f"  - requirements_with_techstack.json (full export)")


if __name__ == "__main__":
    main()