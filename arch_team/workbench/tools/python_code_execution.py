# -*- coding: utf-8 -*-
from __future__ import annotations

"""
PythonCodeExecutionTool

Sichere, offline-lauffähige Ausführung kleiner Python-Snippets in stark
eingeschränkter Umgebung. Keine externen Abhängigkeiten, keine Dateisystem-/
Netzwerkzugriffe. Docker-/Sandbox-Executor ist nur als Lazy-Import-Idee in
diesem Docstring erwähnt, wird hier aber bewusst NICHT verwendet.

Beispiel (JSON-Tool-Call):
{
  "tool": "python_exec",
  "args": { "code": "for i in range(3): print(i)" }
}
"""

import ast
import io
import threading
from typing import Any, Dict, Optional

from .base import BaseTool, ToolResult


class PythonCodeExecutionTool(BaseTool):
    """
    Führt Python-Code-Snippets (reiner Ausdrucks-/Anweisungs-Code) mit
    minimalen Builtins aus. Stdout wird abgefangen.

    Einschränkungen:
    - Verbotene Muster (z. B. __, import, exec(, eval(, os., subprocess)
      führen zu ToolResult.fail mit Hinweis.
    - Syntaxprüfung mit ast.parse() vor der Ausführung.
    - Builtins sind auf {print, range, len} beschränkt.
    - Einfacher Zeitwächter via threading.Timer. Bei Überschreitung wird ein
      Timeout-Flag gesetzt und ToolResult.timeout(meta={"reason": "time limit"})
      zurückgegeben (kein Kill, nur Safeguard).
    """

    name: str = "python_exec"
    description: str = "Ausführung kleiner Python-Snippets in stark eingeschränkter Umgebung (stdout-capture, Timeout-Safeguard)."
    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "maxLength": 5000},
        },
        "required": ["code"],
        "additionalProperties": False,
    }

    # Konstante Zeitbegrenzung (Sekunden)
    _TIME_LIMIT: float = 2.0

    _DISALLOWED_TOKENS = [
        "__",          # Dunder/Internals
        "import",      # jegliche Imports unterbinden
        "exec(",       # dynamische Ausführung verbieten
        "eval(",       # eval verbieten
        "os.",         # OS-Zugriffe
        "subprocess",  # Prozessstarts
    ]

    def validate(self, args: Dict[str, Any]) -> Optional[ToolResult]:
        # Schema-ähnliche Validierung
        if not isinstance(args, dict):
            return ToolResult.fail("Arguments must be a dict")
        code = args.get("code")
        if not isinstance(code, str):
            return ToolResult.fail("Field 'code' must be a string")
        if len(code) > 5000:
            return ToolResult.fail("Field 'code' exceeds maxLength 5000")

        lowered = code.lower()
        for tok in self._DISALLOWED_TOKENS:
            if tok in lowered:
                return ToolResult.fail(f"Disallowed pattern detected: '{tok}'")

        return None

    def run(self, args: Dict[str, Any]) -> ToolResult:
        # Vorvalidierung (zusätzlich zu Workbench.validate-Aufruf)
        val = self.validate(args)
        if isinstance(val, ToolResult):
            return val

        code = (args.get("code") or "").strip()

        # Syntax-Prüfung
        try:
            ast.parse(code)
        except SyntaxError as e:
            return ToolResult.fail(f"Syntax error: {e}")

        # Stdout abfangen, indem wir ein eigenes print bereitstellen
        stdout_buffer = io.StringIO()

        def _safe_print(*objects: Any, sep: str = " ", end: str = "\n") -> None:
            try:
                stdout_buffer.write(sep.join(str(o) for o in objects) + end)
            except Exception:
                # Im Fehlerfall nichts tun, um Ausführung nicht zu stoppen
                pass

        safe_builtins: Dict[str, Any] = {
            "print": _safe_print,
            "range": range,
            "len": len,
        }

        # Zeitwächter via Timer (kein Abbruch, nur Flag)
        timed_out = {"flag": False}

        def _on_timeout():
            timed_out["flag"] = True

        timer = threading.Timer(self._TIME_LIMIT, _on_timeout)
        timer.daemon = True
        timer.start()

        try:
            # Ausführung in stark eingeschränkter Umgebung
            globals_env = {"__builtins__": safe_builtins}
            locals_env: Dict[str, Any] = {}
            compiled = compile(code, filename="<workbench>", mode="exec")
            exec(compiled, globals_env, locals_env)  # noqa: S102 (bewusst, in sandboxed Globals)
        except Exception as e:
            return ToolResult.fail(f"Runtime error: {e}")
        finally:
            try:
                timer.cancel()
            except Exception:
                pass

        if timed_out["flag"]:
            return ToolResult.timeout(meta={"reason": "time limit"})

        captured = stdout_buffer.getvalue()
        return ToolResult.ok({"stdout": captured, "result": None})