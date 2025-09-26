#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LangExtract Dev-Pipeline:
- Liest Markdown-Anforderungen (Standard: data/requirements.out.md)
- Chunking mit Überlappung
- Strukturierte Extraktion mit Span-Grounding
- Export als JSONL + interaktive HTML-Visualisierung

Konfiguration via Umgebungsvariablen:
- LX_INPUT: Pfad zur Eingabedatei (Default: data/requirements.out.md)
- LX_OUTPUT_DIR: Ausgabeverzeichnis (Default: dev/output)
- LX_MODEL_ID: Modell-ID (z. B. gemini-2.5-flash oder ein lokales Ollama-Model) (Default: gemini-2.5-flash)
- LX_CHUNK_SIZE: Chunk-Limit in Zeichen (Default: 5000)
- LX_CHUNK_OVERLAP: Überlappung in Zeichen (Default: 400)
"""

import os
import re
from pathlib import Path
from datetime import datetime
import textwrap

try:
    import langextract as lx
except ImportError:
    raise SystemExit(
        "LangExtract ist nicht installiert. Installation: pip install langextract\n"
        "Hinweis: Für Cloud-Modelle ggf. API-Key und Provider-spezifische Umgebung konfigurieren."
    )

# ---------------------------------------------------------------------------
# .env laden (falls vorhanden), bevor Konfiguration aus Umgebungsvariablen erfolgt
# ---------------------------------------------------------------------------
def _load_env_file():
    try:
        p = Path(".env")
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if "=" in s:
                    k, v = s.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception:
        # .env ist optional – Fehler hier nicht kritisch
        pass

_load_env_file()

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

INPUT_PATH = os.getenv("LX_INPUT", "data/requirements.out.md")
OUTPUT_DIR = Path(os.getenv("LX_OUTPUT_DIR", "dev/output"))
MODEL_ID = os.getenv("LX_MODEL_ID", "gpt-4.1")
CHUNK_SIZE = int(os.getenv("LX_CHUNK_SIZE", "400"))
CHUNK_OVERLAP = int(os.getenv("LX_CHUNK_OVERLAP", "50"))

# API-Key (OpenAI/Allgemein)
API_KEY = os.getenv("LANGEXTRACT_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")

PROMPT = textwrap.dedent("""\
    Extrahiere Anforderungen aus Software-Requirements in strukturierter Form.
    Regeln:
    - Nutze ausschließlich exakte Textspannen aus der Quelle (keine Paraphrasen).
    - Überschneide Extraktionen nicht.
    - Bevorzuge prägnante, aussagekräftige Textspannen.
    - Halte dich strikt an das Schema unten.
    - Falls ein Feld nicht sicher bestimmbar ist, lasse es leer/weg.

    Zielklassen und empfohlene Attribute:
    - requirement: attributes: priority (low/medium/high), category, rationale
    - actor: attributes: role (end_user/admin/system/external)
    - capability: attributes: area (module/feature)
    - constraint: attributes: type (security/compliance/performance/availability/other)
    - acceptance_criterion: attributes: kind (functional/nonfunctional)
    - relation: attributes: type (depends_on/conflicts_with/relates_to)

    Ausgabe: Erzeuge eine robuste, konsistente Struktur mit klaren Klassen und sinnvollen Attributen.
    """)

EXAMPLES = [
    lx.data.ExampleData(
        text="Requirement: The system shall allow users to reset passwords within 5 minutes after request. Constraint: MFA is mandatory. Actor: user",
        extractions=[
            lx.data.Extraction(
                extraction_class="requirement",
                extraction_text="allow users to reset passwords",
                attributes={"priority": "high", "category": "account_management", "rationale": "security usability"}
            ),
            lx.data.Extraction(
                extraction_class="constraint",
                extraction_text="MFA is mandatory",
                attributes={"type": "security"}
            ),
            lx.data.Extraction(
                extraction_class="actor",
                extraction_text="user",
                attributes={"role": "end_user"}
            ),
        ]
    )
]

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def read_text(path_str: str) -> str:
    p = Path(path_str)
    if not p.exists():
        alt = Path("data/requirements.md")
        if alt.exists():
            p = alt
        else:
            raise FileNotFoundError(f"Eingabedatei nicht gefunden: {path_str} (alternativ geprüft: {alt})")
    return p.read_text(encoding="utf-8")


def split_paragraphs(text: str) -> list[str]:
    # Aufteilen an Leerzeilen (Markdown-Absätze)
    parts = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in parts if p.strip()]


def build_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Erzeugt überlappende Chunks basierend auf Absätzen. Bei extrem langen Absätzen wird hart gesplittet.
    """
    paras = split_paragraphs(text)
    chunks: list[str] = []
    cur = ""
    for para in paras:
        candidate = (cur + ("\n\n" if cur else "") + para)
        if len(candidate) <= chunk_size:
            cur = candidate
        else:
            if cur:
                chunks.append(cur)
                # Überlappung am Chunk-Ende
                tail = cur[-overlap:] if overlap > 0 and len(cur) > overlap else ""
                cur = (tail + ("\n\n" if tail else "") + para)
            else:
                # Einzelner Absatz ist größer als chunk_size: hart teilen
                start = 0
                while start < len(para):
                    end = min(start + chunk_size, len(para))
                    piece = para[start:end]
                    chunks.append(piece)
                    # Überlappung berücksichtigen
                    start = max(end - overlap, end)
                cur = ""
    if cur:
        chunks.append(cur)
    return chunks


def ensure_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_chunk(chunk_text: str, idx: int):
    """
    Führt die Extraktion für einen einzelnen Chunk aus und annotiert leichte Metadaten.
    """
    result = lx.extract(
        text_or_documents=chunk_text,
        prompt_description=PROMPT,
        examples=EXAMPLES,
        model_id=MODEL_ID,
        api_key=API_KEY,
    )
    # Metadaten für Nachvollziehbarkeit ergänzen, falls verfügbar
    try:
        if hasattr(result, "metadata") and isinstance(result.metadata, dict):
            result.metadata.setdefault("chunk_index", idx)
            result.metadata.setdefault("source", str(INPUT_PATH))
    except Exception:
        # Metadaten sind optional; robuste Ausführung bevorzugen
        pass
    return result


def main():
    ensure_output_dir()
    source_text = read_text(INPUT_PATH)
    chunks = build_chunks(source_text, CHUNK_SIZE, CHUNK_OVERLAP)

    print(f"[LangExtract] Eingabe: {INPUT_PATH} | Chunks: {len(chunks)} | Modell: {MODEL_ID}")
    results = []
    for i, ch in enumerate(chunks):
        print(f"[LangExtract] Verarbeite Chunk {i+1}/{len(chunks)} (len={len(ch)})")
        res = extract_chunk(ch, i)
        results.append(res)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    output_basename = f"requirements_extraction_{timestamp}"
    jsonl_path = OUTPUT_DIR / f"{output_basename}.jsonl"
    html_path = OUTPUT_DIR / f"{output_basename}.html"

    # Ergebnisse speichern
    lx.io.save_annotated_documents(results, output_name=jsonl_path.name, output_dir=str(OUTPUT_DIR))
    print(f"[LangExtract] JSONL gespeichert: {jsonl_path}")

    # Visualisierung erzeugen
    vis = lx.visualize(str(jsonl_path))
    with open(html_path, "w", encoding="utf-8") as f:
        if hasattr(vis, "data"):
            f.write(vis.data)  # Für Notebook-Objekte
        else:
            f.write(vis)
    print(f"[LangExtract] Visualisierung gespeichert: {html_path}")
    print("[LangExtract] Fertig.")


if __name__ == "__main__":
    main()