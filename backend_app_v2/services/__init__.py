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

# Services
from .vector_service import VectorService
from .batch_service import BatchService
from .evaluation_service import EvaluationService
from .corrections_service import CorrectionsService

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
    # Services
    "VectorService",
    "BatchService",
    "EvaluationService",
    "CorrectionsService",
]