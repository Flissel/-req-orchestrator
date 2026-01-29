# -*- coding: utf-8 -*-
"""
Versionierter Requirements-Store für Qdrant.

Speichert enhanced validated requirements in Collections mit Versionierung:
  - requirements_v1, requirements_v2, etc.

Usage:
  store = RequirementsStore()
  result = store.store_requirements(requirements, version="auto")  # auto = nächste Version
  versions = store.list_versions()
  reqs = store.get_requirements(version="v2")
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Force reload environment variables
from dotenv import load_dotenv
load_dotenv(override=True)

from ..runtime.logging import get_logger
from backend.core.embeddings import build_embeddings, get_embeddings_dim

# Import centralized port configuration
try:
    from backend.core.ports import get_ports
    _ports = get_ports()
except ImportError:
    _ports = None

logger = get_logger("memory.requirements_store")


class RequirementsStore:
    """
    Qdrant-gestützter Requirements-Store mit Versionierung.
    
    Collections naming: requirements_v{n} (z.B. requirements_v1, requirements_v2)
    
    Jedes Requirement wird als Point gespeichert mit:
    - id: UUID basierend auf req_id
    - vector: Embedding von title
    - payload: req_id, title, tag, evidence_refs, version, stored_at
    """
    
    COLLECTION_PREFIX = "requirements_v"
    
    def __init__(
        self,
        qdrant_url: Optional[str] = None,
        api_key: Optional[str] = None,
        dim: Optional[int] = None,
    ) -> None:
        # URL/Port configuration - read fresh from env
        if qdrant_url:
            self.qdrant_url = qdrant_url
        else:
            # Read environment directly to get latest values
            env_url = os.environ.get("QDRANT_URL", "http://localhost")
            env_port = os.environ.get("QDRANT_PORT", "6401")
            
            # Build URL with port
            if "://" in env_url:
                hostpart = env_url.split("://", 1)[-1]
                if ":" not in hostpart:
                    self.qdrant_url = f"{env_url}:{env_port}"
                else:
                    self.qdrant_url = env_url
            else:
                self.qdrant_url = f"http://localhost:{env_port}"
        
        self.api_key = api_key or os.environ.get("QDRANT_API_KEY") or None
        self.dim = int(dim or get_embeddings_dim())
        self.batch_size = int(os.environ.get("QDRANT_UPSERT_BATCH", "500"))
        self._embed_cache: Dict[str, List[float]] = {}
        self._qdrant = None
    
    def _lazy_import(self):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client import models as qmodels
            return QdrantClient, qmodels
        except Exception:
            raise RuntimeError("qdrant-client nicht installiert. Bitte 'pip install qdrant-client' ausführen.")
    
    def _client(self):
        if self._qdrant is None:
            QdrantClient, _ = self._lazy_import()
            self._qdrant = QdrantClient(url=self.qdrant_url, api_key=self.api_key)
        return self._qdrant
    
    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Batch embed texts with caching."""
        if not texts:
            return []
        
        out: List[Optional[List[float]]] = [None] * len(texts)
        missing: List[str] = []
        missing_idx: List[int] = []
        
        for i, t in enumerate(texts):
            v = self._embed_cache.get(t)
            if v is not None:
                out[i] = v
            else:
                missing.append(t)
                missing_idx.append(i)
        
        if missing:
            uniq: List[str] = []
            idx_map: Dict[str, int] = {}
            for t in missing:
                if t not in idx_map:
                    idx_map[t] = len(uniq)
                    uniq.append(t)
            vecs = build_embeddings(uniq)
            for t, vec in zip(uniq, vecs):
                self._embed_cache[t] = vec
            for pos, i in enumerate(missing_idx):
                t = texts[i]
                out[i] = self._embed_cache[t]
        
        return out  # type: ignore
    
    def list_versions(self) -> List[Dict[str, Any]]:
        """
        List all requirement versions.
        Returns: [{"version": "v1", "collection": "requirements_v1", "count": 42}, ...]
        """
        client = self._client()
        try:
            cols = client.get_collections()
            versions = []
            
            for c in (cols.collections or []):
                name = c.name
                if name.startswith(self.COLLECTION_PREFIX):
                    version_str = name[len(self.COLLECTION_PREFIX):]
                    try:
                        # Get collection info for count
                        info = client.get_collection(name)
                        count = info.points_count if hasattr(info, 'points_count') else 0
                        versions.append({
                            "version": f"v{version_str}",
                            "collection": name,
                            "count": count,
                            "vectors_count": info.vectors_count if hasattr(info, 'vectors_count') else 0
                        })
                    except Exception as e:
                        logger.warning(f"Could not get info for collection {name}: {e}")
                        versions.append({
                            "version": f"v{version_str}",
                            "collection": name,
                            "count": 0
                        })
            
            # Sort by version number
            versions.sort(key=lambda x: int(x["version"][1:]) if x["version"][1:].isdigit() else 0)
            return versions
            
        except Exception as e:
            logger.error(f"List versions failed: {e}")
            return []
    
    def get_next_version(self) -> str:
        """Get the next version number (e.g., 'v3' if v1, v2 exist)."""
        versions = self.list_versions()
        if not versions:
            return "v1"
        
        max_version = 0
        for v in versions:
            version_str = v["version"][1:]  # Remove 'v' prefix
            if version_str.isdigit():
                max_version = max(max_version, int(version_str))
        
        return f"v{max_version + 1}"
    
    def _collection_name(self, version: str) -> str:
        """Convert version string to collection name."""
        # Remove 'v' prefix if present
        v = version.lstrip("vV")
        return f"{self.COLLECTION_PREFIX}{v}"
    
    def create_collection(self, version: str) -> str:
        """Create a new requirements collection for the given version."""
        client = self._client()
        _, qmodels = self._lazy_import()
        
        collection_name = self._collection_name(version)
        
        try:
            # Check if exists
            cols = client.get_collections()
            names = [c.name for c in (cols.collections or [])]
            
            if collection_name not in names:
                logger.info(f"Creating requirements collection {collection_name} (dim={self.dim})")
                client.recreate_collection(
                    collection_name=collection_name,
                    vectors_config=qmodels.VectorParams(size=self.dim, distance=qmodels.Distance.COSINE),
                )
            
            return collection_name
            
        except Exception as e:
            raise RuntimeError(f"Create collection failed: {e}")
    
    def store_requirements(
        self,
        requirements: List[Dict[str, Any]],
        version: str = "auto",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store requirements to a versioned collection.
        
        Args:
            requirements: List of requirement dicts with req_id, title, tag, evidence_refs
            version: "auto" for next version, or specific version like "v1", "v2"
            metadata: Optional metadata to store with each requirement
        
        Returns:
            {
                "success": True,
                "version": "v2",
                "collection": "requirements_v2",
                "count": 97,
                "stored_at": "2024-01-15T10:30:00Z"
            }
        """
        if not requirements:
            return {"success": False, "error": "No requirements provided", "count": 0}
        
        # Determine version
        if version == "auto":
            version = self.get_next_version()
        
        # Ensure 'v' prefix
        if not version.startswith("v"):
            version = f"v{version}"
        
        # Create collection
        collection_name = self.create_collection(version)
        
        client = self._client()
        _, qmodels = self._lazy_import()
        
        # Prepare points
        ids: List[str] = []
        texts: List[str] = []
        payloads: List[Dict[str, Any]] = []
        stored_at = datetime.utcnow().isoformat() + "Z"
        
        for req in requirements:
            req_id = str(req.get("req_id") or req.get("id") or "")
            if not req_id:
                continue
            
            ids.append(req_id)
            
            title = str(req.get("title") or req.get("text") or "")
            texts.append(title if title else req_id)
            
            # Build payload with only essential fields
            payload = {
                "req_id": req_id,
                "title": title,
                "tag": str(req.get("tag") or req.get("category") or ""),
                "evidence_refs": req.get("evidence_refs") or req.get("evidenceRefs") or [],
                "version": version,
                "stored_at": stored_at
            }
            
            # Add optional metadata
            if metadata:
                payload["metadata"] = metadata
            
            payloads.append(payload)
        
        if not ids:
            return {"success": False, "error": "No valid requirements found", "count": 0}
        
        # Create embeddings
        try:
            vecs = self._embed_texts(texts)
        except Exception as e:
            return {"success": False, "error": f"Embedding failed: {e}", "count": 0}
        
        # Generate deterministic UUIDs from req_id
        point_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, str(rid))) for rid in ids]
        
        # Batch upsert
        total = 0
        try:
            for start in range(0, len(point_ids), max(1, self.batch_size)):
                end = min(len(point_ids), start + max(1, self.batch_size))
                points = []
                for pid, vec, pld in zip(point_ids[start:end], vecs[start:end], payloads[start:end]):
                    points.append(qmodels.PointStruct(id=pid, vector=vec, payload=pld))
                
                if points:
                    client.upsert(collection_name=collection_name, points=points)
                    total += len(points)
        except Exception as e:
            return {"success": False, "error": f"Upsert failed: {e}", "count": total}
        
        logger.info(f"Stored {total} requirements to {collection_name}")
        
        return {
            "success": True,
            "version": version,
            "collection": collection_name,
            "count": total,
            "stored_at": stored_at
        }
    
    def get_requirements(
        self,
        version: str,
        limit: int = 10000
    ) -> List[Dict[str, Any]]:
        """
        Get all requirements from a specific version.
        
        Args:
            version: Version string like "v1", "v2"
            limit: Maximum number of requirements to return
        
        Returns:
            List of requirement dicts
        """
        client = self._client()
        collection_name = self._collection_name(version)
        
        requirements: List[Dict[str, Any]] = []
        
        try:
            offset = None
            while True:
                result = client.scroll(
                    collection_name=collection_name,
                    limit=min(100, limit - len(requirements)),
                    with_payload=True,
                    offset=offset
                )
                points, next_offset = result if isinstance(result, tuple) else (result, None)
                
                for p in (points or []):
                    payload = dict(getattr(p, "payload", {}) or {})
                    requirements.append(payload)
                
                if not next_offset or len(requirements) >= limit:
                    break
                offset = next_offset
                
        except Exception as e:
            logger.error(f"Get requirements failed for {version}: {e}")
        
        return requirements
    
    def search_requirements(
        self,
        query: str,
        version: str,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Semantic search in a specific version.
        
        Args:
            query: Search query
            version: Version string like "v1", "v2"
            top_k: Number of results
        
        Returns:
            List of {id, score, payload} dicts
        """
        if not query or not query.strip():
            return []
        
        client = self._client()
        collection_name = self._collection_name(version)
        
        try:
            vec = self._embed_texts([query])[0]
        except Exception as e:
            logger.error(f"Search embedding failed: {e}")
            return []
        
        try:
            res = client.search(
                collection_name=collection_name,
                query_vector=vec,
                with_payload=True,
                limit=max(1, int(top_k or 10))
            )
            
            out: List[Dict[str, Any]] = []
            for p in res:
                out.append({
                    "id": str(getattr(p, "id", "")),
                    "score": float(getattr(p, "score", 0.0) or 0.0),
                    "payload": dict(getattr(p, "payload", {}) or {})
                })
            return out
            
        except Exception as e:
            logger.error(f"Search failed for {version}: {e}")
            return []
    
    def delete_version(self, version: str) -> bool:
        """Delete a requirements version collection."""
        client = self._client()
        collection_name = self._collection_name(version)
        
        try:
            client.delete_collection(collection_name)
            logger.info(f"Deleted collection {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Delete collection failed: {e}")
            return False