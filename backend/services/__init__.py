# -*- coding: utf-8 -*-

# Ports / Fehler / Context
from .ports import (
    EmbeddingsPort,
    VectorStorePort,
    PersistencePort,
    RequestContext,
    ServiceError,
    LLMPort,
)

# Adapter (Default-Implementierungen auf Basis backend_app.*)
from .adapters import (
    EmbeddingsAdapter,
    VectorStoreAdapter,
    PersistenceAdapter,
    LLMAdapter,
)

# Services - Lazy imports to avoid circular dependencies (PEP 562)
def __getattr__(name):
    """Lazy import services to avoid circular imports"""
    if name == "VectorService":
        from .vector_service import VectorService
        return VectorService
    elif name == "BatchService":
        from .batch_service import BatchService
        return BatchService
    elif name == "EvaluationService":
        from .evaluation_service import EvaluationService
        return EvaluationService
    elif name == "CorrectionsService":
        from .corrections_service import CorrectionsService
        return CorrectionsService
    elif name == "ManifestService":
        from .manifest_service import ManifestService
        return ManifestService
    elif name == "ProjectService":
        from .project_service import ProjectService
        return ProjectService
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    # Ports
    "EmbeddingsPort",
    "VectorStorePort",
    "PersistencePort",
    "RequestContext",
    "ServiceError",
    "LLMPort",
    # Adapter
    "EmbeddingsAdapter",
    "VectorStoreAdapter",
    "PersistenceAdapter",
    "LLMAdapter",
    # Services (lazy loaded)
    "VectorService",
    "BatchService",
    "EvaluationService",
    "CorrectionsService",
    "ManifestService",
    "ProjectService",
]