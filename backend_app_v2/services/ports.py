# -*- coding: utf-8 -*-
"""
Service-Layer Ports (Framework-frei)

Zweck
- Definiert die Schnittstellen (Ports) für externe Systeme und Cross-Cutting Concerns
  als Python Protocols, um Implementierungen (Adapter) leicht austauschbar zu machen.
- Dient als gemeinsame Basis für Services (evaluation/batch/corrections/vector/rag/lx).

Design-Prinzipien
- Keine HTTP/Framework-Kopplung (keine FastAPI/Flask-Imports)
- Reine Typen/Protokolle; Adapter kapseln konkrete Bibliotheken/Module
- Optionale RequestContext zur Durchreichung von z. B. request_id (Observability)

Nutzung
- Services hängen gegen diese Ports (Dependency Injection)
- Default-Adapter können die bestehenden Funktionen aus backend_app.* nutzen
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple


# -----------------------
# Fehler-/Resultattypen
# -----------------------

class ServiceError(Exception):
    """Basisfehler für Services mit standardisiertem Code/Message."""

    def __init__(self, code: str, message: str, *, details: Optional[Mapping[str, Any]] = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = dict(details or {})


@dataclass(frozen=True)
class RequestContext:
    """Transport für kontextuelle Infos (z. B. request_id) ohne Framework-Kopplung."""
    request_id: Optional[str] = None
    # Platz für weitere Felder: user_id, tenant_id, feature_flags, etc.


# -----------------------
# Embeddings-Port
# -----------------------

class EmbeddingsPort(Protocol):
    """Abstraktion eines Embeddings-Providers."""

    def build_embeddings(self, texts: Sequence[str], *, model: Optional[str] = None, ctx: Optional[RequestContext] = None) -> List[List[float]]:
        """Erzeuge Embeddings für gegebene Texte.
        Rückgabe: Liste von Vektoren gleicher Dimension (len == get_dim()).
        Fehlerfälle: ServiceError(code="embeddings_failed", ...)
        """
        ...

    def get_dim(self, *, ctx: Optional[RequestContext] = None) -> int:
        """Liefert die Vektordimension des aktuellen Embeddings-Modells."""
        ...


# -----------------------
# VectorStore-Port (z. B. Qdrant)
# -----------------------

class VectorStorePort(Protocol):
    """Abstraktion eines Vector-Stores (List/Search/Upsert/Reset/Health/Fetch)."""

    def list_collections(self, *, ctx: Optional[RequestContext] = None) -> List[str]:
        ...

    def health(self, *, ctx: Optional[RequestContext] = None) -> Mapping[str, Any]:
        ...

    def reset_collection(self, collection_name: str, dim: int, *, ctx: Optional[RequestContext] = None) -> Mapping[str, Any]:
        """Droppt/initialisiert eine Collection mit gegebener Dim."""
        ...

    def upsert_points(
        self,
        items: Sequence[Dict[str, Any]],
        *,
        collection_name: str,
        dim: int,
        ctx: Optional[RequestContext] = None,
    ) -> Mapping[str, Any]:
        """Upsert der Punkte (vector + payload). Items-Form wird vom Adapter dokumentiert."""
        ...

    def search(
        self,
        vector: Sequence[float],
        *,
        top_k: int,
        collection_name: str,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        """Suche TopK ähnlichste Vektoren. Rückgabe: Treffer inkl. payload/score."""
        ...

    def fetch_window_by_source_and_index(
        self,
        source: str,
        start: int,
        end: int,
        *,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        """Fenster (start..end) aus einer Quelle lesen, typ. für Dokument-Preview."""
        ...


# -----------------------
# Persistence-Port (DB)
# -----------------------

class PersistencePort(Protocol):
    """Abstraktion minimaler Persistenzfunktionen (SQLite/DB)."""

    def ensure_schema(self, *, ctx: Optional[RequestContext] = None) -> None:
        """Optional: Schema/DDL sicherstellen (No-Op im Default)."""
        ...

    def get_latest_rewrite_row_for_eval(self, evaluation_id: str, *, ctx: Optional[RequestContext] = None) -> Optional[Mapping[str, Any]]:
        ...

    def get_latest_evaluation_by_checksum(self, checksum: str, *, ctx: Optional[RequestContext] = None) -> Optional[Mapping[str, Any]]:
        ...

    def load_criteria(self, *, ctx: Optional[RequestContext] = None) -> List[Mapping[str, Any]]:
        ...


# -----------------------
# Hilfsfunktionen
# -----------------------

def safe_request_id(ctx: Optional[RequestContext]) -> Optional[str]:
    """Kleine Hilfe, um request_id sicher auszulesen."""
    return getattr(ctx, "request_id", None)


# -----------------------
# LLM-Port (Evaluate/Suggest/Rewrite/Apply)
# -----------------------

class LLMPort(Protocol):
    """Abstraktion eines LLM-Clients für Evaluate/Suggest/Rewrite/Apply.
    Adapter binden bestehende Implementierungen aus backend_app.llm an.
    """

    def evaluate(
        self,
        requirement_text: str,
        criteria_keys: Sequence[str],
        *,
        context: Optional[Mapping[str, Any]] = None,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        """Bewertet requirement_text entlang criteria_keys.
        Rückgabe: List[{"criterion": str, "score": float, "passed": bool, "feedback": str}]
        Fehlerfälle: ServiceError(code="llm_evaluate_failed", ...)
        """
        ...

    def suggest(
        self,
        requirement_text: str,
        *,
        context: Optional[Mapping[str, Any]] = None,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        """Erzeugt Verbesserungsvorschläge („Atoms“)."""
        ...

    def rewrite(
        self,
        requirement_text: str,
        *,
        context: Optional[Mapping[str, Any]] = None,
        ctx: Optional[RequestContext] = None,
    ) -> str:
        """Gibt eine umgeschriebene Fassung zurück."""
        ...

    def apply_with_suggestions(
        self,
        requirement_text: str,
        *,
        context: Optional[Mapping[str, Any]] = None,
        selected_atoms: Sequence[Mapping[str, Any]] = (),
        mode: str = "merge",
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        """Erzeugt 1..N Requirements aus originalText + ausgewählten Atoms (merge|split)."""
        ...