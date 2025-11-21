# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import uuid
from typing import Optional

from ..runtime.logging import get_logger

# Import centralized port configuration
try:
    from backend.core.ports import get_ports
    _ports = get_ports()
except ImportError:
    _ports = None

logger = get_logger("memory.qdrant_trace_sink")


class QdrantTraceSink:
    """
    Minimaler Trace-Sink für CoT-Artefakte in Qdrant.
    - Lazy-Import von qdrant_client und sentence_transformers
    - Einfache Collection mit Sentence-Transformer Vektor (Standard: all-MiniLM-L6-v2, dim=384)
    """

    def __init__(
        self,
        qdrant_url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection: str = "arch_trace",
        st_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        # Use centralized port configuration with legacy fallback
        self.qdrant_url = qdrant_url or (_ports.QDRANT_FULL_URL if _ports else os.environ.get("QDRANT_URL", "http://localhost:6333"))
        self.api_key = api_key or os.environ.get("QDRANT_API_KEY") or None
        self.collection = collection
        self.st_model_name = st_model_name

        self._qdrant = None  # type: ignore
        self._st_model = None  # type: ignore
        self._dim = 384  # default for MiniLM-L6-v2

    def _lazy_imports(self):
        try:
            from qdrant_client import QdrantClient  # type: ignore
            from qdrant_client import models as qmodels  # type: ignore
        except Exception:
            raise RuntimeError(
                "qdrant-client nicht installiert. Bitte 'pip install qdrant-client' ausführen."
            )
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception:
            raise RuntimeError(
                "sentence-transformers nicht installiert. Bitte 'pip install sentence-transformers' ausführen."
            )
        return QdrantClient, qmodels, SentenceTransformer

    def _client(self):
        if self._qdrant is None:
            QdrantClient, _, _ = self._lazy_imports()
            # qdrant_url kann http://host:port oder http(s)://host sein; QdrantClient akzeptiert 'url'
            self._qdrant = QdrantClient(url=self.qdrant_url, api_key=self.api_key)
        return self._qdrant

    def _model(self):
        if self._st_model is None:
            _, _, SentenceTransformer = self._lazy_imports()
            self._st_model = SentenceTransformer(self.st_model_name)
            # Versuche Dimension aus Modell zu lesen
            try:
                emb = self._st_model.encode(["dim-probe"])
                if emb is not None and len(emb) == 1:
                    self._dim = len(emb[0])
            except Exception:
                self._dim = 384
        return self._st_model

    def ensure(self) -> None:
        """
        Stellt sicher, dass die Collection existiert.
        """
        client = self._client()
        _, qmodels, _ = self._lazy_imports()
        try:
            collections = client.get_collections()
            names = [c.name for c in (collections.collections or [])]
            if self.collection not in names:
                logger.info("QdrantTraceSink: create collection %s (dim=%d)", self.collection, self._dim)
                client.recreate_collection(
                    collection_name=self.collection,
                    vectors_config=qmodels.VectorParams(size=self._dim, distance=qmodels.Distance.COSINE),
                )
        except Exception as e:
            raise RuntimeError(f"QdrantTraceSink.ensure() fehlgeschlagen: {e}")

    def save(
        self,
        thoughts: str = "",
        evidence: str = "",
        final: str = "",
        decision: str = "",
        task: str = "",
        req_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        session_id: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> str:
        """
        Persistiert einen Trace-Eintrag und gibt die Point-ID zurück.
        """
        client = self._client()
        _, qmodels, _ = self._lazy_imports()
        self._model()  # ensure model/dim
        self.ensure()

        text = "\n".join(
            [
                ("THOUGHTS: " + thoughts.strip()) if thoughts else "",
                ("EVIDENCE: " + evidence.strip()) if evidence else "",
                ("FINAL: " + final.strip()) if final else "",
                ("DECISION: " + decision.strip()) if decision else "",
                ("TASK: " + task.strip()) if task else "",
            ]
        ).strip()
        try:
            vec = self._st_model.encode([text])[0]  # type: ignore
        except Exception as e:
            raise RuntimeError(f"Trace-Embedding fehlgeschlagen: {e}")

        pid = str(uuid.uuid4())
        payload = {
            "reqId": req_id,
            "agentType": agent_type,
            "sessionId": session_id,
            "task": task,
            "thoughts": thoughts,
            "evidence": evidence,
            "final": final,
            "decision": decision,
            "meta": meta or {},
        }
        try:
            client.upsert(
                collection_name=self.collection,
                points=[
                    qmodels.PointStruct(id=pid, vector=vec, payload=payload),
                ],
            )
            return pid
        except Exception as e:
            raise RuntimeError(f"QdrantTraceSink.save() fehlgeschlagen: {e}")