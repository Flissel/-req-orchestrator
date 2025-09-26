# -*- coding: utf-8 -*-
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Literal


class ToolResult:
    """
    Einheitliches Tool-Ergebnisobjekt für die Workbench.

    Felder:
      - status: "success" | "error" | "timeout"
      - content: Beliebige Nutzdaten oder None
      - error: Fehlertext oder None
      - meta: optionale Metadaten (z. B. Rohwerte, Debug-Hinweise)

    Hilfs-Constructoren:
      - ToolResult.ok(content, meta=None)
      - ToolResult.fail(error, meta=None)
      - ToolResult.timeout(meta=None)
    """

    def __init__(self, status: Literal["success", "error", "timeout"], content: Any = None, error: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> None:
        self.status: Literal["success", "error", "timeout"] = status
        self.content: Any = content
        self.error: Optional[str] = error
        self.meta: Optional[Dict[str, Any]] = meta

    @classmethod
    def ok(cls, content: Any, meta: Optional[Dict[str, Any]] = None) -> "ToolResult":
        return cls(status="success", content=content, error=None, meta=meta)

    @classmethod
    def fail(cls, error: str, meta: Optional[Dict[str, Any]] = None) -> "ToolResult":
        return cls(status="error", content=None, error=str(error), meta=meta)

    @classmethod
    def timeout(cls, meta: Optional[Dict[str, Any]] = None) -> "ToolResult":
        return cls(status="timeout", content=None, error="timeout", meta=meta or {"reason": "timeout"})

    def is_success(self) -> bool:
        return self.status == "success"


class BaseTool(ABC):
    """
    Abstrakte Basis-Klasse für Workbench-Tools.

    Vorgaben:
      - name: str
      - description: str
      - input_schema: dict[str, Any] (leichtgewichtig, kein Pydantic)
      - validate(args) -> ToolResult | None (None bei ok; ToolResult.fail bei Fehlern)
      - run(args) -> ToolResult
    """

    name: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = {}

    def validate(self, args: Dict[str, Any]) -> Optional[ToolResult]:
        """
        Optionale Validierung. Rückgabe:
          - None bei Erfolg
          - ToolResult.fail(...) bei Validierungsfehlern
        """
        return None

    @abstractmethod
    def run(self, args: Dict[str, Any]) -> ToolResult:
        """
        Führt das Tool synchron aus und gibt ToolResult zurück.
        """
        raise NotImplementedError