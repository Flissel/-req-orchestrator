# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import logging
from typing import Any, Dict, List

from . import settings

# OpenAI optional
try:
    import openai  # type: ignore
except Exception:
    openai = None  # type: ignore

# Neu: v1 Client-Unterstützung (OpenAI>=1.x)
try:
    from openai import OpenAI as _OpenAIClient  # type: ignore
    OPENAI_V1 = True
except Exception:
    _OpenAIClient = None  # type: ignore
    OPENAI_V1 = False

# Zentraler Logger für LLM-Debug
LOGGER = logging.getLogger("app.llm")
DEBUG_LLM = os.environ.get("DEBUG_LLM", "").lower() in ("1", "true", "yes", "on")
OPENAI_IMPORT_OK = openai is not None
OPENAI_VERSION = getattr(openai, "__version__", None) if openai else None

def _parse_version_tuple(ver: str) -> tuple:
    parts: List[int] = []
    for p in str(ver or "").split("."):
        m = re.match(r"(\d+)", p)
        parts.append(int(m.group(1)) if m else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


OPENAI_IS_V1_RUNTIME = False
try:
    if OPENAI_VERSION:
        OPENAI_IS_V1_RUNTIME = _parse_version_tuple(OPENAI_VERSION) >= (1, 0, 0)
    else:
        OPENAI_IS_V1_RUNTIME = bool(_OpenAIClient)
except Exception:
    OPENAI_IS_V1_RUNTIME = bool(_OpenAIClient)

if DEBUG_LLM:
    try:
        LOGGER.info(json.dumps({
            "event": "llm.init",
            "openai_import_ok": OPENAI_IMPORT_OK,
            "openai_version": OPENAI_VERSION,
            "openai_v1_client_available": bool(_OpenAIClient),
            "openai_is_v1_runtime": OPENAI_IS_V1_RUNTIME,
            "api_key_present": bool(os.environ.get("OPENAI_API_KEY") or ""),
            "model": os.environ.get("OPENAI_MODEL"),
            "mock_mode": os.environ.get("MOCK_MODE")
        }))
    except Exception:
        pass


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
    # Entferne führende/trailing Code-Fences ```json ...
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
    if DEBUG_LLM:
        try:
            LOGGER.info(json.dumps({
                "event": "llm.evaluate.start",
                "api_key_present": bool(settings.OPENAI_API_KEY),
                "openai_import_ok": OPENAI_IMPORT_OK,
                "openai_v1_client_available": bool(_OpenAIClient),
                "openai_is_v1_runtime": OPENAI_IS_V1_RUNTIME,
                "mock_mode": getattr(settings, "MOCK_MODE", False),
                "model": getattr(settings, "OPENAI_MODEL", ""),
                "criteria_keys": criteria_keys
            }))
        except Exception:
            pass

    if not settings.OPENAI_API_KEY:
        if DEBUG_LLM:
            LOGGER.warning(json.dumps({"event": "llm.evaluate.fallback", "reason": "no_api_key"}))
        return _heuristic_mock_evaluation(requirement_text, criteria_keys)
    if not OPENAI_IMPORT_OK and not _OpenAIClient:
        if DEBUG_LLM:
            LOGGER.warning(json.dumps({"event": "llm.evaluate.fallback", "reason": "openai_module_missing"}))
        return _heuristic_mock_evaluation(requirement_text, criteria_keys)

    try:
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

        # v1.x Client-Pfad erzwungen bei v1-Runtime
        if OPENAI_IS_V1_RUNTIME and _OpenAIClient is not None:
            client = _OpenAIClient(api_key=settings.OPENAI_API_KEY)
            if DEBUG_LLM:
                try:
                    LOGGER.info(json.dumps({"event": "llm.evaluate.call", "model": settings.OPENAI_MODEL, "sdk": "v1", "openai_version": OPENAI_VERSION}))
                except Exception:
                    pass
            v1_kwargs: Dict[str, Any] = {
                "model": settings.OPENAI_MODEL,
                "messages": chat_args["messages"],
                "temperature": chat_args.get("temperature", 0.0),
                "top_p": chat_args.get("top_p", 1.0),
            }
            if "response_format" in chat_args:
                v1_kwargs["response_format"] = chat_args["response_format"]
            resp = client.chat.completions.create(**v1_kwargs)  # type: ignore[arg-type]
            content_raw = resp.choices[0].message.content or ""
        else:
            if OPENAI_IS_V1_RUNTIME:
                # Unter v1-Runtime darf Legacy nicht verwendet werden
                if DEBUG_LLM:
                    try:
                        LOGGER.error(json.dumps({"event": "llm.evaluate.path_blocked", "reason": "v1_runtime_no_client", "openai_version": OPENAI_VERSION}))
                    except Exception:
                        pass
                raise RuntimeError("OpenAI>=1.x detected but OpenAI client unavailable")
            # Legacy 0.28.x Pfad (nur bei openai<1.0)
            if OPENAI_IMPORT_OK:
                openai.api_key = settings.OPENAI_API_KEY  # type: ignore[attr-defined]
            if DEBUG_LLM:
                try:
                    LOGGER.info(json.dumps({"event": "llm.evaluate.call", "model": chat_args.get("model"), "sdk": "legacy", "openai_version": OPENAI_VERSION}))
                except Exception:
                    pass
            resp = openai.ChatCompletion.create(**chat_args)  # type: ignore[call-arg]
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
        if DEBUG_LLM:
            LOGGER.error(json.dumps({"event": "llm.evaluate.error", "message": str(e)}))
        return _heuristic_mock_evaluation(requirement_text, criteria_keys)


def llm_suggest(requirement_text: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Liefert atomare Verbesserungsvorschläge ("Atoms") als Liste von Dicts.
    Rückgabe: List[Dict[str, Any]] mit mind. "correction" und "acceptance_criteria".
    In MOCK_MODE deterministisch, sonst LLM mit Blockformat (<<<REQ_ATOM>>>...<<<END_ATOM>>>).
    """
    if DEBUG_LLM:
        try:
            LOGGER.info(json.dumps({
                "event": "llm.suggest.start",
                "api_key_present": bool(settings.OPENAI_API_KEY),
                "openai_import_ok": OPENAI_IMPORT_OK,
                "openai_v1_client_available": bool(_OpenAIClient),
                "openai_is_v1_runtime": OPENAI_IS_V1_RUNTIME,
                "mock_mode": getattr(settings, "MOCK_MODE", False),
                "model": getattr(settings, "OPENAI_MODEL", "")
            }))
        except Exception:
            pass
    # MOCK_MODE
    if getattr(settings, "MOCK_MODE", False):
        if DEBUG_LLM:
            LOGGER.info(json.dumps({"event": "llm.suggest.path", "mode": "mock"}))
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

    # Kein API/Client
    if not settings.OPENAI_API_KEY or (not OPENAI_IMPORT_OK and not _OpenAIClient):
        if DEBUG_LLM:
            LOGGER.warning(json.dumps({"event": "llm.suggest.path", "mode": "fallback_empty", "reason": "no_api_key_or_openai_missing"}))
        return []

    # Robuste Normalisierung bleibt unverändert ...

    try:
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

        if OPENAI_IS_V1_RUNTIME and _OpenAIClient is not None:
            client = _OpenAIClient(api_key=settings.OPENAI_API_KEY)
            if DEBUG_LLM:
                try:
                    LOGGER.info(json.dumps({"event": "llm.suggest.call", "model": settings.OPENAI_MODEL, "sdk": "v1", "openai_version": OPENAI_VERSION}))
                except Exception:
                    pass
            v1_kwargs: Dict[str, Any] = {
                "model": settings.OPENAI_MODEL,
                "messages": messages,
                "temperature": getattr(settings, "LLM_TEMPERATURE", 0.0),
                "top_p": getattr(settings, "LLM_TOP_P", 1.0),
            }
            resp = client.chat.completions.create(**v1_kwargs)  # type: ignore[arg-type]
            content_raw = resp.choices[0].message.content or ""
        else:
            if OPENAI_IS_V1_RUNTIME:
                if DEBUG_LLM:
                    try:
                        LOGGER.error(json.dumps({"event": "llm.suggest.path_blocked", "reason": "v1_runtime_no_client", "openai_version": OPENAI_VERSION}))
                    except Exception:
                        pass
                raise RuntimeError("OpenAI>=1.x detected but OpenAI client unavailable")
            if OPENAI_IMPORT_OK:
                openai.api_key = settings.OPENAI_API_KEY  # type: ignore[attr-defined]
            if DEBUG_LLM:
                try:
                    LOGGER.info(json.dumps({"event": "llm.suggest.call", "model": settings.OPENAI_MODEL, "sdk": "legacy", "openai_version": OPENAI_VERSION}))
                except Exception:
                    pass
            chat_args: Dict[str, Any] = dict(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=getattr(settings, "LLM_TEMPERATURE", 0.0),
                top_p=getattr(settings, "LLM_TOP_P", 1.0),
            )
            max_tokens = getattr(settings, "LLM_MAX_TOKENS", 0)
            if isinstance(max_tokens, int) and max_tokens > 0:
                chat_args["max_tokens"] = max_tokens
            resp = openai.ChatCompletion.create(**chat_args)  # type: ignore[call-arg]
            content_raw = resp["choices"][0]["message"]["content"]  # type: ignore[index]

        if DEBUG_LLM_RAW:
            print("[LLM][suggest][RAW]", content_raw)

        # 1) Bevorzugt unser Block-Format parsen
        atoms = parse_suggestion_blocks(content_raw)
        if atoms:
            if DEBUG_LLM:
                LOGGER.info(json.dumps({"event": "llm.suggest.parsed", "format": "block", "count": len(atoms)}))
            return atoms

        # 2) Fallback: JSON erkennen (direkt oder innerhalb Code-Fence) und normalisieren
        try:
            json_text = _extract_json_string(content_raw)
        except Exception:
            json_text = ""
        if json_text:
            try:
                parsed = json.loads(json_text)
                atoms2 = _coerce_atoms_from_json(parsed)  # type: ignore[name-defined]
                if atoms2:
                    if DEBUG_LLM:
                        LOGGER.info(json.dumps({"event": "llm.suggest.parsed", "format": "json", "count": len(atoms2)}))
                    return atoms2
            except Exception as je:
                if DEBUG_LLM_RAW:
                    print("[LLM][suggest][JSON_PARSE_ERROR]", str(je))
                else:
                    if DEBUG_LLM:
                        LOGGER.error(json.dumps({"event": "llm.suggest.json_parse_error", "message": str(je)}))
        if DEBUG_LLM:
            LOGGER.warning(json.dumps({"event": "llm.suggest.empty", "reason": "no_atoms_extracted"}))
        return []
    except Exception as e:
        if DEBUG_LLM:
            LOGGER.error(json.dumps({"event": "llm.suggest.error", "message": str(e)}))
        return []


def llm_rewrite(requirement_text: str, context: Dict[str, Any]) -> str:
    """
    Formuliert die Anforderung präzise, testbar, messbar um. Fällt auf Heuristik zurück.
    """
    if DEBUG_LLM:
        try:
            LOGGER.info(json.dumps({
                "event": "llm.rewrite.start",
                "api_key_present": bool(settings.OPENAI_API_KEY),
                "openai_import_ok": OPENAI_IMPORT_OK,
                "openai_v1_client_available": bool(_OpenAIClient),
                "openai_is_v1_runtime": OPENAI_IS_V1_RUNTIME,
                "mock_mode": getattr(settings, "MOCK_MODE", False),
                "model": getattr(settings, "OPENAI_MODEL", "")
            }))
        except Exception:
            pass

    if not settings.OPENAI_API_KEY or (not OPENAI_IMPORT_OK and not _OpenAIClient):
        if DEBUG_LLM:
            LOGGER.warning(json.dumps({"event": "llm.rewrite.path", "mode": "heuristic_original", "reason": "no_api_key_or_openai_missing"}))
        return requirement_text

    try:
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

        if OPENAI_IS_V1_RUNTIME and _OpenAIClient is not None:
            client = _OpenAIClient(api_key=settings.OPENAI_API_KEY)
            chat_kwargs: Dict[str, Any] = {
                "model": settings.OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                "temperature": getattr(settings, "LLM_TEMPERATURE", 0.0),
                "top_p": getattr(settings, "LLM_TOP_P", 1.0),
            }
            if DEBUG_LLM:
                try:
                    LOGGER.info(json.dumps({"event": "llm.rewrite.call", "model": chat_kwargs.get("model"), "sdk": "v1", "openai_version": OPENAI_VERSION}))
                except Exception:
                    pass
            resp = client.chat.completions.create(**chat_kwargs)  # type: ignore[arg-type]
            content = resp.choices[0].message.content or ""
        else:
            if OPENAI_IS_V1_RUNTIME:
                if DEBUG_LLM:
                    try:
                        LOGGER.error(json.dumps({"event": "llm.rewrite.path_blocked", "reason": "v1_runtime_no_client", "openai_version": OPENAI_VERSION}))
                    except Exception:
                        pass
                raise RuntimeError("OpenAI>=1.x detected but OpenAI client unavailable")
            if OPENAI_IMPORT_OK:
                openai.api_key = settings.OPENAI_API_KEY  # type: ignore[attr-defined]
            chat_args = _make_chat_args(system_prompt, user_payload)
            if DEBUG_LLM:
                try:
                    LOGGER.info(json.dumps({"event": "llm.rewrite.call", "model": chat_args.get("model"), "sdk": "legacy", "openai_version": OPENAI_VERSION}))
                except Exception:
                    pass
            resp = openai.ChatCompletion.create(**chat_args)  # type: ignore[call-arg]
            content = resp["choices"][0]["message"]["content"]  # type: ignore[index]

        if content.strip().startswith("{"):
            parsed = json.loads(content)
        else:
            parsed = json.loads(_extract_json_string(content))
        text = str(parsed.get("redefinedRequirement", "")).strip()
        return text or requirement_text
    except Exception as e:
        if DEBUG_LLM:
            LOGGER.error(json.dumps({"event": "llm.rewrite.error", "message": str(e)}))
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
    if DEBUG_LLM:
        try:
            LOGGER.info(json.dumps({
                "event": "llm.apply.start",
                "api_key_present": bool(settings.OPENAI_API_KEY),
                "openai_import_ok": OPENAI_IMPORT_OK,
                "openai_v1_client_available": bool(_OpenAIClient),
                "openai_is_v1_runtime": OPENAI_IS_V1_RUNTIME,
                "mock_mode": getattr(settings, "MOCK_MODE", False),
                "model": getattr(settings, "OPENAI_MODEL", ""),
                "mode": str(mode),
                "selected_atoms": len(selected_atoms or [])
            }))
        except Exception:
            pass
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

    # MOCK_MODE
    if getattr(settings, "MOCK_MODE", False):
        if DEBUG_LLM:
            LOGGER.info(json.dumps({"event": "llm.apply.path", "mode": "mock"}))
        return _mock_split(selected_atoms) if str(mode).lower() == "split" else _mock_merge(selected_atoms)

    # Kein API/Client
    if not settings.OPENAI_API_KEY or (not OPENAI_IMPORT_OK and not _OpenAIClient):
        if DEBUG_LLM:
            LOGGER.warning(json.dumps({"event": "llm.apply.path", "mode": "mock_like", "reason": "no_api_key_or_openai_missing"}))
        return _mock_split(selected_atoms) if str(mode).lower() == "split" else _mock_merge(selected_atoms)

    # LLM-Mode
    try:
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

        if OPENAI_IS_V1_RUNTIME and _OpenAIClient is not None:
            client = _OpenAIClient(api_key=settings.OPENAI_API_KEY)
            if DEBUG_LLM:
                try:
                    LOGGER.info(json.dumps({"event": "llm.apply.call", "model": settings.OPENAI_MODEL, "mode": user_payload.get("mode"), "sdk": "v1", "openai_version": OPENAI_VERSION}))
                except Exception:
                    pass
            resp = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                temperature=getattr(settings, "LLM_TEMPERATURE", 0.0),
                top_p=getattr(settings, "LLM_TOP_P", 1.0),
            )
            content_raw = resp.choices[0].message.content or ""
        else:
            if OPENAI_IS_V1_RUNTIME:
                if DEBUG_LLM:
                    try:
                        LOGGER.error(json.dumps({"event": "llm.apply.path_blocked", "reason": "v1_runtime_no_client", "openai_version": OPENAI_VERSION}))
                    except Exception:
                        pass
                raise RuntimeError("OpenAI>=1.x detected but OpenAI client unavailable")
            if OPENAI_IMPORT_OK:
                openai.api_key = settings.OPENAI_API_KEY  # type: ignore[attr-defined]
            if DEBUG_LLM:
                try:
                    LOGGER.info(json.dumps({"event": "llm.apply.call", "model": settings.OPENAI_MODEL, "mode": user_payload.get("mode"), "sdk": "legacy", "openai_version": OPENAI_VERSION}))
                except Exception:
                    pass
            chat_args = _make_chat_args(sys_prompt, user_payload)
            resp = openai.ChatCompletion.create(**chat_args)  # type: ignore[call-arg]
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
        if not out and DEBUG_LLM:
            LOGGER.warning(json.dumps({"event": "llm.apply.empty_items", "reason": "no_items_in_response"}))
        if not out:
            # Fallback, falls LLM kein valides Ergebnis liefert
            return _mock_split(selected_atoms) if str(mode).lower() == "split" else _mock_merge(selected_atoms)
        return out
    except Exception as e:
        if DEBUG_LLM:
            LOGGER.error(json.dumps({"event": "llm.apply.error", "message": str(e)}))
        return _mock_split(selected_atoms) if str(mode).lower() == "split" else _mock_merge(selected_atoms)