# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

from . import settings

# OpenAI optional
try:
    import openai  # type: ignore
except Exception:
    openai = None  # type: ignore


def _heuristic_mock_evaluation(requirement_text: str, criteria_keys: List[str]) -> List[Dict[str, Any]]:
    text = (requirement_text or "").lower()
    contains_number = any(ch.isdigit() for ch in text)
    words = text.split()
    length = len(words)

    def clarity_score() -> float:
        return 0.9 if length <= 20 else 0.7 if length <= 40 else 0.5

    def testability_score() -> float:
        return 0.85 if contains_number else 0.55

    def measurability_score() -> float:
        indicators = ["ms", "s", "sekunde", "sekunden", "proz", "%", "durchsatz", "latenz"]
        has_unit = any(tok in text for tok in indicators)
        return 0.8 if has_unit or contains_number else 0.5

    mapping = {
        "clarity": (clarity_score(), "Formulierung ist überwiegend eindeutig."),
        "testability": (testability_score(), "Prüfkriterien sind teilweise ableitbar."),
        "measurability": (measurability_score(), "Messbare Aspekte sind erkennbar."),
    }
    details: List[Dict[str, Any]] = []
    for key in criteria_keys:
        sc, fb = mapping.get(key, (0.6, "Allgemeine Einschätzung"))
        details.append({"criterion": key, "score": sc, "passed": sc >= 0.7, "feedback": fb})
    return details


def _make_chat_args(system_prompt: str, user_payload: Dict[str, Any]) -> Dict[str, Any]:
    user_prompt = json.dumps(user_payload, ensure_ascii=False)
    chat_args: Dict[str, Any] = dict(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        temperature=getattr(settings, "LLM_TEMPERATURE", 0.0),
        top_p=getattr(settings, "LLM_TOP_P", 1.0),
        # Erzwinge JSON-only Modus, sofern vom Modell unterstützt
        response_format={"type": "json_object"},
    )
    max_tokens = getattr(settings, "LLM_MAX_TOKENS", 0)
    if isinstance(max_tokens, int) and max_tokens > 0:
        chat_args["max_tokens"] = max_tokens
    return chat_args


DEBUG_LLM_RAW = os.environ.get("DEBUG_LLM_RAW", "").lower() in ("1", "true", "yes")


def _extract_json_string(raw: str) -> str:
    """
    Entfernt ggf. Code-Fences und extrahiert das erste gültige JSON-Objekt/-Array.
    Wirft ValueError bei Misserfolg.
    """
    s = (raw or "").strip()
    # Entferne führende/trailing Code-Fences ```json ... ```
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s, flags=re.DOTALL)
        s = re.sub(r"\s*```$", "", s, flags=re.DOTALL)
        s = s.strip()
    # Direkter Versuch
    try:
        json.loads(s)
        return s
    except Exception:
        pass
    # Versuche erste JSON-Struktur zu extrahieren (Objekt/Array)
    start_obj = s.find("{")
    start_arr = s.find("[")
    starts = [x for x in [start_obj, start_arr] if x != -1]
    if not starts:
        raise ValueError("No JSON start found in LLM output")
    start = min(starts)
    # Suche passendes Ende heuristisch
    end_obj = s.rfind("}")
    end_arr = s.rfind("]")
    ends = [x for x in [end_obj, end_arr] if x != -1]
    if not ends:
        raise ValueError("No JSON end found in LLM output")
    end = max(ends)
    candidate = s[start : end + 1].strip()
    json.loads(candidate)  # validiert
    return candidate


def llm_evaluate(requirement_text: str, criteria_keys: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Bewertung einer Anforderung je Kriterium. Fällt auf Heuristik zurück, wenn kein LLM verfügbar.
    """
    if not settings.OPENAI_API_KEY or openai is None:
        return _heuristic_mock_evaluation(requirement_text, criteria_keys)

    try:
        openai.api_key = settings.OPENAI_API_KEY  # Legacy SDK
        system_prompt = settings.get_system_prompt("evaluate") or (
            "Du bist ein Qualitätsprüfer für Software-Requirements. "
            "Bewerte die Anforderung entlang vorgegebener Kriterien mit Scores 0.0 bis 1.0. "
            "Gib NUR JSON zurück mit: {details: [{criterion, score, passed, feedback}]}"
        )
        user_payload = {
            "requirementText": requirement_text,
            "criteriaKeys": criteria_keys,
            "context": context or {},
            "outputSchema": {
                "details": [
                    {"criterion": "string", "score": "float 0..1", "passed": "bool", "feedback": "string"}
                ]
            },
        }
        chat_args = _make_chat_args(system_prompt, user_payload)
        resp = openai.ChatCompletion.create(**chat_args)
        content_raw = resp["choices"][0]["message"]["content"]  # type: ignore[index]
        if DEBUG_LLM_RAW:
            print("[LLM][evaluate][RAW]", content_raw)
        content = _extract_json_string(content_raw)
        parsed = json.loads(content)
        if DEBUG_LLM_RAW:
            print("[LLM][evaluate][PARSED]", json.dumps(parsed, ensure_ascii=False))
        details = parsed.get("details", [])
        norm_details: List[Dict[str, Any]] = []
        for d in details:
            crit = d.get("criterion")
            if crit in criteria_keys:
                sc = float(d.get("score", 0.0))
                norm_details.append(
                    {
                        "criterion": crit,
                        "score": max(0.0, min(1.0, sc)),
                        "passed": bool(d.get("passed", sc >= 0.7)),
                        "feedback": str(d.get("feedback", "")),
                    }
                )
        if not norm_details:
            raise ValueError("LLM evaluate returned no valid details")
        return norm_details
    except Exception as e:
        if DEBUG_LLM_RAW:
            print("[LLM][evaluate][ERROR]", str(e))
        return _heuristic_mock_evaluation(requirement_text, criteria_keys)


def llm_suggest(requirement_text: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Liefert atomare Verbesserungsvorschläge ("Atoms") als Liste von Dicts.
    Rückgabe: List[Dict[str, Any]] mit mind. "correction" und "acceptance_criteria".
    In MOCK_MODE deterministisch, sonst LLM mit Blockformat (<<<REQ_ATOM>>>...<<<END_ATOM>>>).
    """
    # MOCK_MODE: deterministische Blöcke generieren (keine LLM-Abhängigkeit)
    if getattr(settings, "MOCK_MODE", False):
        base = requirement_text.strip()
        atoms_raw: List[str] = []

        def make_atom(original_fragment: str, correction: str, ac: List[str], metrics: List[Dict[str, Any]], notes: str = "") -> str:
            obj = {
                "original_fragment": original_fragment,
                "correction": correction,
                "acceptance_criteria": ac,
                "metrics": metrics,
                "criteria": {
                    "atomic": True, "clarity": True, "concise": True, "consistent_language": True,
                    "design_independent": True, "follows_template": True, "measurability": True,
                    "purpose_independent": True, "testability": True, "unambiguous": True
                },
                "notes": notes or ""
            }
            return f"{SUGGEST_BLOCK_START}\n{json.dumps(obj, ensure_ascii=False)}\n{SUGGEST_BLOCK_END}\n"

        n = 1 + (len(base.split()) % 3)  # 1–3 deterministisch
        for i in range(n):
            ac = [
                "Given ein System im Normalbetrieb",
                f"When ein typischer Nutzeraktion-{i+1} ausgeführt wird",
                "Then wird das definierte Ergebnis innerhalb der Schwellwerte erreicht",
            ]
            metrics = [
                {"name": "response_time_ms", "op": "<=", "value": 200, "context": "Ref-Env 30RPS, p95"}
            ]
            corr = "Das System soll die Funktion innerhalb von ≤200 ms (p95) unter 30 RPS liefern."
            atoms_raw.append(make_atom(base, corr, ac, metrics))
        atoms = parse_suggestion_blocks("".join(atoms_raw))
        return atoms

    # LLM-Mode
    if not settings.OPENAI_API_KEY or openai is None:
        # Keine API verfügbar und kein Mock → leere Liste
        return []

    try:
        openai.api_key = settings.OPENAI_API_KEY
        system_prompt = (
            "Du bist ein erfahrener Requirements Engineer.\n"
            "Gib ausschließlich 1–3 Blöcke aus, jeder exakt so:\n"
            f"{SUGGEST_BLOCK_START}\n"
            "{JSON gemäß Schema}\n"
            f"{SUGGEST_BLOCK_END}\n"
            "Kein zusätzlicher Text, keine Code-Fences. Jeder JSON-Block folgt diesem Schema:\n"
            + SUGGEST_ATOM_JSON_SCHEMA_DOC
        )
        user_content = {
            "requirementText": requirement_text,
            "context": context or {},
            "constraints": {
                "atomsPerRequirement": 3,
                "designIndependent": True,
                "measurable": True,
                "testable": True,
            },
        }
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
        ]
        chat_args: Dict[str, Any] = dict(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=getattr(settings, "LLM_TEMPERATURE", 0.0),
            top_p=getattr(settings, "LLM_TOP_P", 1.0),
        )
        max_tokens = getattr(settings, "LLM_MAX_TOKENS", 0)
        if isinstance(max_tokens, int) and max_tokens > 0:
            chat_args["max_tokens"] = max_tokens

        resp = openai.ChatCompletion.create(**chat_args)
        content_raw = resp["choices"][0]["message"]["content"]  # type: ignore[index]
        if DEBUG_LLM_RAW:
            print("[LLM][suggest][RAW]", content_raw)
        atoms = parse_suggestion_blocks(content_raw)
        if DEBUG_LLM_RAW:
            print("[LLM][suggest][ATOMS]", json.dumps(atoms, ensure_ascii=False))
        return atoms
    except Exception as e:
        if DEBUG_LLM_RAW:
            print("[LLM][suggest][ERROR]", str(e))
        return []


def llm_rewrite(requirement_text: str, context: Dict[str, Any]) -> str:
    """
    Formuliert die Anforderung präzise, testbar, messbar um. Fällt auf Heuristik zurück.
    """
    if not settings.OPENAI_API_KEY or openai is None:
        return requirement_text

    try:
        openai.api_key = settings.OPENAI_API_KEY
        system_prompt = settings.get_system_prompt("rewrite") or (
            "Du bist ein erfahrener Requirements Engineer. "
            "Formuliere die folgende Anforderung präzise, testbar und messbar um. "
            "Gib NUR JSON zurück: {redefinedRequirement: string}"
        )
        user_payload = {
            "requirementText": requirement_text,
            "context": context or {},
            "style": {"clarity": True, "measurable": True, "testable": True},
        }
        chat_args = _make_chat_args(system_prompt, user_payload)
        resp = openai.ChatCompletion.create(**chat_args)
        content = resp["choices"][0]["message"]["content"]  # type: ignore[index]
        parsed = json.loads(content)
        text = str(parsed.get("redefinedRequirement", "")).strip()
        return text or requirement_text
    except Exception as e:
        if DEBUG_LLM_RAW:
            print("[LLM][rewrite][ERROR]", str(e))
        return requirement_text

# --- Suggestion-Block-Parser und Konstanten ---

SUGGEST_BLOCK_START = "<<<REQ_ATOM>>>"
SUGGEST_BLOCK_END = "<<<END_ATOM>>>"
SUGGEST_REGEX = re.compile(r"(?s)<<<REQ_ATOM>>>(.*?)<<<END_ATOM>>>")

SUGGEST_ATOM_JSON_SCHEMA_DOC = """
{
  "original_fragment": "...",
  "correction": "Das System soll ...",
  "acceptance_criteria": ["Given ...", "When ...", "Then ..."],
  "metrics": [
    {"name": "...", "op": "<=|==|match", "value": 200, "context": "Ref-Env 30RPS ..."}
  ],
  "criteria": {
    "atomic": true, "clarity": true, "concise": true, "consistent_language": true,
    "design_independent": true, "follows_template": true, "measurability": true,
    "purpose_independent": true, "testability": true, "unambiguous": true
  },
  "notes": "optional"
}
""".strip()


def parse_suggestion_blocks(text: str) -> List[Dict[str, Any]]:
    """
    Extrahiert via Regex alle Blöcke (<<<REQ_ATOM>>>...<<<END_ATOM>>>), parst JSON
    und validiert Minimalfelder: "correction" (string) und "acceptance_criteria" (Liste).
    Ungültige Blöcke werden übersprungen. Fehler werden minimal geloggt.
    """
    atoms: List[Dict[str, Any]] = []
    if not text:
        return atoms
    try:
        for m in SUGGEST_REGEX.finditer(text):
            raw = (m.group(1) or "").strip()
            try:
                obj = json.loads(raw)
                if not isinstance(obj, dict):
                    raise ValueError("atom is not a JSON object")
                correction = obj.get("correction")
                ac = obj.get("acceptance_criteria")
                if isinstance(correction, str) and correction.strip() and isinstance(ac, list):
                    atoms.append(obj)
                else:
                    if DEBUG_LLM_RAW:
                        print("[SUGGEST][parse] invalid atom (missing required fields)")
            except Exception as ie:
                if DEBUG_LLM_RAW:
                    print("[SUGGEST][parse] error:", str(ie))
    except Exception as e:
        if DEBUG_LLM_RAW:
            print("[SUGGEST][parse] regex error:", str(e))
    return atoms
# --- Apply with Suggestions (merge/split) ---

def llm_apply_with_suggestions(
    requirement_text: str,
    context: Dict[str, Any],
    selected_atoms: List[Dict[str, Any]],
    mode: str = "merge",
) -> List[Dict[str, Any]]:
    """
    Erzeugt 1..N umgeschriebene Requirement(s) basierend auf:
      - originalem requirement_text
      - optionalem context
      - ausgewählten Suggestion-Atoms (selected_atoms)
      - mode: "merge" (eine konsolidierte Fassung) | "split" (mehrere atomare Fassungen)

    Rückgabeformat:
      [ { "redefinedRequirement": "..." }, ... ]
    """
    # Hilfsfunktionen
    def _norm_correction(a: Dict[str, Any]) -> str:
        # bevorzugt das Feld 'correction' aus Atom-JSON; Fallbacks erlauben robuste Nutzung
        val = a.get("correction")
        if isinstance(val, str) and val.strip():
            return val.strip()
        # Fallback: reiner Text oder generischer Hinweis
        t = a.get("text")
        if isinstance(t, str) and t.strip():
            return t.strip()
        return requirement_text.strip()

    def _mock_merge(atoms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not atoms:
            # keine Auswahl → gib original zurück (nicht persistiert gespeichert; nur Rückgabe)
            return [{"redefinedRequirement": requirement_text.strip()}]
        merged = " ".join([_norm_correction(a) for a in atoms]).strip()
        merged = merged or requirement_text.strip()
        return [{"redefinedRequirement": merged}]

    def _mock_split(atoms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for a in atoms:
            corr = _norm_correction(a)
            if corr:
                items.append({"redefinedRequirement": corr})
        if not items:
            items.append({"redefinedRequirement": requirement_text.strip()})
        return items

    # MOCK_MODE: deterministisch, ohne LLM-Abhängigkeit
    if getattr(settings, "MOCK_MODE", False):
        return _mock_split(selected_atoms) if str(mode).lower() == "split" else _mock_merge(selected_atoms)

    # LLM-Mode: Falls kein Key/SDK → Fallback wie Mock
    if not settings.OPENAI_API_KEY or openai is None:
        return _mock_split(selected_atoms) if str(mode).lower() == "split" else _mock_merge(selected_atoms)

    # LLM-Mode: System-Prompt und Nutzlast
    try:
        openai.api_key = settings.OPENAI_API_KEY
        sys_prompt = (
            "Du bist ein erfahrener Requirements Engineer.\n"
            "Aufgabe: Formuliere basierend auf dem originalText und den ausgewählten Verbesserungsvorschlägen (Atoms)\n"
            "präzise, testbare und messbare Requirements neu.\n"
            "Modus:\n"
            "- merge: Erzeuge genau 1 konsolidierte Fassung aus allen Atoms.\n"
            "- split: Erzeuge 1..N atomare Requirements (je Atom in der Regel 1 Fassung).\n"
            "Gib ausschließlich JSON im Format zurück:\n"
            "{ \"items\": [ { \"redefinedRequirement\": \"...\" }, ... ] }\n"
            "Keine Code-Fences, keine Erklärungen außerhalb des JSON."
        )
        # Reduziere die Atoms auf relevante Felder, um Halluzinationen zu vermeiden
        atoms_min: List[Dict[str, Any]] = []
        for a in selected_atoms or []:
            atoms_min.append(
                {
                    "correction": str(a.get("correction", "")),
                    "acceptance_criteria": a.get("acceptance_criteria", []),
                    "metrics": a.get("metrics", []),
                }
            )

        user_payload = {
            "originalText": requirement_text,
            "context": context or {},
            "mode": str(mode).lower(),
            "selectedAtoms": atoms_min,
            "constraints": {
                "style": {"clarity": True, "measurable": True, "testable": True},
                "language": "de",
                # Optionales Limit – kann später an settings.SUGGEST_MAX gekoppelt werden
                "maxItems": max(1, min(len(atoms_min) if atoms_min else 1, getattr(settings, "SUGGEST_MAX", 3))),
            },
            "outputSchema": {"items": [{"redefinedRequirement": "string"}]},
        }

        chat_args = _make_chat_args(sys_prompt, user_payload)
        resp = openai.ChatCompletion.create(**chat_args)
        content_raw = resp["choices"][0]["message"]["content"]  # type: ignore[index]
        if DEBUG_LLM_RAW:
            print("[LLM][apply][RAW]", content_raw)
        content = _extract_json_string(content_raw)
        parsed = json.loads(content)
        if DEBUG_LLM_RAW:
            print("[LLM][apply][PARSED]", json.dumps(parsed, ensure_ascii=False))
        items = parsed.get("items", [])
        out: List[Dict[str, Any]] = []
        for it in items:
            txt = str(it.get("redefinedRequirement", "")).strip()
            if txt:
                out.append({"redefinedRequirement": txt})
        if not out:
            # Fallback, falls LLM kein valides Ergebnis liefert
            return _mock_split(selected_atoms) if str(mode).lower() == "split" else _mock_merge(selected_atoms)
        return out
    except Exception as e:
        if DEBUG_LLM_RAW:
            print("[LLM][apply][ERROR]", str(e))
        return _mock_split(selected_atoms) if str(mode).lower() == "split" else _mock_merge(selected_atoms)