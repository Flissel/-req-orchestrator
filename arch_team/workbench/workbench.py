# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Workbench: Zentrale Router/Abstraktion für Tools mit einheitlichem ToolResult.

Sicherheits-/Privacy-Hinweis:
- Diese Workbench verarbeitet ausschließlich toolseitige Nutzdaten (name, args) gemäß JSON-Tool-Call-Protokoll.
- KEINE THOUGHTS/EVIDENCE/CRITIQUE/DECISION-Inhalte verarbeiten, speichern oder ausgeben.
- Eingaben aus LLM-Ausgaben werden ausschließlich als strukturierte Tool-Aufrufe (tool/args) interpretiert.

JSON-Tool-Call-Protokoll (Beispiel):
{
  "tool": "python_exec",
  "args": { "code": "print(1)" }
}
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from .tools.base import BaseTool, ToolResult


class Workbench:
    """
    Workbench: Registrierung, Auflistung und Aufruf von Tools.

    - register(tool: BaseTool) -> None
    - list_tools() -> list[dict]  (name, description, input_schema)
    - call(name: str, args: dict) -> ToolResult
      - Lookup per name; validate() → run()
      - Exceptions werden abgefangen und als ToolResult.fail zurückgegeben
    - from_llm_output(text: str) -> tuple[name, args] | ToolResult.fail
      - Robust gegen Markdown-Codefences; extrahiert den ersten gültigen JSON-Block
        mit Feldern "tool" und "args".
    """

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if not isinstance(tool, BaseTool):
            raise TypeError("tool muss BaseTool sein")
        name = (tool.name or "").strip()
        if not name:
            raise ValueError("Tool.name darf nicht leer sein")
        self._tools[name] = tool

    def list_tools(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for name, tool in self._tools.items():
            out.append(
                {
                    "name": name,
                    "description": getattr(tool, "description", "") or "",
                    "input_schema": getattr(tool, "input_schema", {}) or {},
                }
            )
        return out

    def call(self, name: str, args: Dict[str, Any]) -> ToolResult:
        if not isinstance(args, dict):
            return ToolResult.fail("args must be a dict")
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult.fail(f"Unknown tool: {name}")

        try:
            validation = tool.validate(args)
            if isinstance(validation, ToolResult):
                return validation
        except Exception as e:
            return ToolResult.fail(f"Validation error in '{name}': {e}")

        try:
            result = tool.run(args)
            if not isinstance(result, ToolResult):
                return ToolResult.fail(f"Tool '{name}' returned invalid result type")
            return result
        except Exception as e:
            return ToolResult.fail(f"Tool error in '{name}': {e}")

    @staticmethod
    def from_llm_output(text: str) -> Union[Tuple[str, Dict[str, Any]], ToolResult]:
        """
        Extrahiert den ersten gültigen Tool-Call im JSON-Format aus einem LLM-Output.

        Akzeptiert sowohl reine JSON-Blöcke als auch Markdown-Codefences:
        ```json
        { "tool": "python_exec", "args": {"code": "print(1)"} }
        ```
        oder
        ```
        { "tool": "python_exec", "args": {"code": "print(1)"} }
        ```

        Rückgabe:
          - (tool_name, args_dict) bei Erfolg
          - ToolResult.fail(...) bei Fehlern
        """
        if not isinstance(text, str) or not text.strip():
            return ToolResult.fail("Empty LLM output")

        # 1) Versuche Codefences mit optionalem Sprachenlabel (json)
        fence_pattern = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)
        fenced_blocks = fence_pattern.findall(text)
        candidates: List[str] = []
        candidates.extend(fenced_blocks)

        # 2) Fallback: ersten JSON-Block heuristisch extrahieren (balancierte Klammern)
        if not candidates:
            extracted = Workbench._extract_first_json_object(text)
            if extracted is not None:
                candidates.append(extracted)

        # 3) Direktversuch: Gesamten Text parsen (falls keinerlei Fences existieren)
        candidates.append(text)

        for raw in candidates:
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            if isinstance(obj, dict):
                # Primär: neues Protokoll {"tool": "...", "args": {...}}
                if "tool" in obj and "args" in obj and isinstance(obj["args"], dict):
                    name = str(obj["tool"]).strip()
                    if not name:
                        continue
                    return name, obj["args"]
                # Fallback: altes Schema {"name": "...", "arguments": {...}}
                if "name" in obj and "arguments" in obj and isinstance(obj["arguments"], dict):
                    name = str(obj["name"]).strip()
                    if not name:
                        continue
                    return name, obj["arguments"]

        return ToolResult.fail("Kein gültiger Tool-Call (JSON mit 'tool' und 'args' bzw. 'name' und 'arguments') gefunden")

    @staticmethod
    def _extract_first_json_object(s: str) -> Optional[str]:
        """
        Einfache balancierte-Klammern-Extraktion für das erste JSON-Objekt.
        Ignoriert naive String-Kontexte nicht vollständig, ist aber robust genug
        für typische LLM-Ausgaben.
        """
        start = -1
        depth = 0
        in_str = False
        esc = False
        for i, ch in enumerate(s):
            if ch == '"' and not esc:
                in_str = not in_str
            esc = (ch == "\\") and not esc

            if in_str:
                continue

            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start != -1:
                        return s[start : i + 1]
        return None


def get_default_workbench() -> "Workbench":
    """
    Factory: Erzeugt eine vorkonfigurierte Workbench und registriert Standard-Tools.

    Sicherheit/Privacy:
    - Tool-Resultate sind ausschließlich für den internen Agentenkontext (EVIDENCE) bestimmt
      und dürfen nicht ungefiltert in das UI gelangen.
    - CoT-Filterung für UI-Ausgaben bleibt durch arch_team/runtime/cot_postprocessor.py gewährleistet.
    """
    wb = Workbench()
    # Lazy-Imports nur innerhalb des Workbench-Pfads
    try:
        from .tools.python_code_execution import PythonCodeExecutionTool  # noqa: WPS433 (intentional local import)
        wb.register(PythonCodeExecutionTool())
    except Exception:
        # Tool ggf. in Teilumgebungen nicht verfügbar – Workbench bleibt funktionsfähig
        pass

    try:
        from .tools.qdrant_search import QdrantSearchTool  # noqa: WPS433 (intentional local import)
        wb.register(QdrantSearchTool())
    except Exception:
        # Retrieval optional – bei fehlender Konfiguration sauber degradieren
        pass

    return wb
if __name__ == "__main__":
    # Minimale Offline-Demo (ohne Netzwerke/Externals):
    # Zeigt die Verwendung von get_default_workbench().
    wb = get_default_workbench()

    # Erfolgreicher JSON-Call (python_exec)
    txt_ok = """
    ```json
    { "tool": "python_exec", "args": { "code": "print('Hello Workbench')" } }
    ```
    """
    parsed = Workbench.from_llm_output(txt_ok)
    if isinstance(parsed, tuple):
        tool_name, tool_args = parsed
        res = wb.call(tool_name, tool_args)
        print("SUCCESS EXAMPLE:", res.status, res.content)
    else:
        print("Parsing failed for OK example:", parsed.error)

    # Fehlerbeispiel: unbekanntes Tool
    txt_fail = '{"tool":"unknown_tool","args":{"x":1}}'
    parsed2 = Workbench.from_llm_output(txt_fail)
    if isinstance(parsed2, tuple):
        tool_name2, tool_args2 = parsed2
        res2 = wb.call(tool_name2, tool_args2)
        print("FAILURE EXAMPLE:", res2.status, res2.error)
    else:
        print("Parsing failed for FAIL example:", parsed2.error)