# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from arch_team.runtime.cot_postprocessor import extract_blocks, ui_payload


def _norm(s: str) -> str:
    return " ".join(str(s).split())


def test_extract_blocks_basic():
    text = """
THOUGHTS:
  Wir überlegen die beste Lösung.
  Mehrzeilige   Inhalte   mit   Whitespace.

EVIDENCE:
```
Zeile 1
Zeile 2
```

FINAL ANSWER:
   Das finale Ergebnis ist: Erfolg.

CRITIQUE:
  Kürzer schreiben.

Decision -
  APPROVED
"""
    blocks = extract_blocks(text)

    # Erwartete Keys vorhanden
    assert "THOUGHTS" in blocks
    assert "EVIDENCE" in blocks
    assert "FINAL_ANSWER" in blocks
    assert "CRITIQUE" in blocks
    assert "DECISION" in blocks

    # Inhalte (mit Whitespace-Normalisierung) korrekt
    assert "beste Lösung" in _norm(blocks["THOUGHTS"])
    assert blocks["EVIDENCE"] == "Zeile 1\nZeile 2"  # Fences entfernt, Zeilen beibehalten
    assert _norm(blocks["FINAL_ANSWER"]).startswith("Das finale Ergebnis ist: Erfolg")
    assert "Kürzer schreiben" in blocks["CRITIQUE"]
    assert _norm(blocks["DECISION"]) == "APPROVED"


def test_filter_ui_only_final():
    # Einzelnes Dict
    blocks = {
        "THOUGHTS": "geheime Überlegungen",
        "EVIDENCE": "daten ...",
        "FINAL_ANSWER": "Nur dies soll in die UI.",
        "CRITIQUE": "könnte präziser sein",
        "DECISION": "OK",
    }
    ui_text = ui_payload(blocks)
    assert ui_text == "Nur dies soll in die UI."
    # Sicherstellen, dass keine internen Inhalte in der UI landen
    assert "geheime" not in ui_text
    assert "CRITIQUE" not in ui_text

    # Liste von Dicts: letzter FINAL_ANSWER gewinnt
    seq = [
        {"FINAL_ANSWER": "Erste Antwort"},
        {"DECISION": "OK"},
        {"FINAL_ANSWER": "Letzte gültige Antwort"},
    ]
    ui_text2 = ui_payload(seq)
    assert ui_text2 == "Letzte gültige Antwort"


def test_missing_blocks_resilience():
    # Kein CRITIQUE/DECISION vorhanden, FINAL_ANSWER muss robust extrahiert werden.
    text = """
THOUGHTS:
  Nur kurz.

FINAL ANSWER:
  Ergebnis A
"""
    blocks = extract_blocks(text)
    assert blocks.get("FINAL_ANSWER", "").strip() == "Ergebnis A"
    # Fehlende Keys verursachen keine Exceptions
    assert "CRITIQUE" not in blocks or blocks.get("CRITIQUE", "") == ""
    assert "DECISION" not in blocks or blocks.get("DECISION", "") == ""