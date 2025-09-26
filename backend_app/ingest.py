# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import json
import hashlib
import time
from typing import Any, Dict, Iterable, List, Tuple

from . import settings

# Optional heavy deps – beim Import fehlertolerant sein, erst beim Gebrauch prüfen.
try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None  # type: ignore

try:
    from docx import Document as DocxDocument  # python-docx
except Exception:  # pragma: no cover
    DocxDocument = None  # type: ignore

# Optional: Magika (Google) für Content-Type-Erkennung
try:
    from magika import Magika  # type: ignore
    _magika = Magika()
except Exception:  # pragma: no cover
    _magika = None  # type: ignore

# Optional: Docling v2 – universeller Document Converter
try:
    # API kann sich unterscheiden; wir kapseln Aufruf defensiv
    from docling.document_converter import DocumentConverter  # type: ignore
    _docling_available = True
except Exception:  # pragma: no cover
    DocumentConverter = None  # type: ignore
    _docling_available = False

try:
    import tiktoken
except Exception:  # pragma: no cover
    tiktoken = None  # type: ignore


# -------- Encoding / Tokenisierung --------

def _get_encoding():
    """
    Liefert eine tiktoken-encoding Instanz (cl100k_base). Fällt auf naive Spaltlogik zurück, falls tiktoken fehlt.
    """
    if tiktoken is None:
        return None
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # pragma: no cover
        return None


def tokenize_len(text: str) -> int:
    """
    Anzahl Tokens gemäß tiktoken cl100k_base; Fallback = Wörter zählen.
    """
    enc = _get_encoding()
    if enc is None:
        # Naive Fallback-Heuristik: Wortanzahl als Token-Approximation
        return max(1, len(text.split()))
    try:
        return len(enc.encode(text))
    except Exception:  # pragma: no cover
        return max(1, len(text.split()))


def _split_by_tokens(text: str, max_tokens: int) -> List[str]:
    """
    Grobe Token-basierte Unterteilung eines Textes in Teile mit max_tokens Länge (keine Overlaps).
    Wird als innerer Schritt beim Erstellen von Overlap-Chunks verwendet.
    """
    enc = _get_encoding()
    if enc is None:
        # Approx: Teile anhand von Wörtern
        words = text.split()
        out: List[str] = []
        if not words:
            return out
        step = max(1, max_tokens)
        for i in range(0, len(words), step):
            out.append(" ".join(words[i:i+step]))
        return out

    tokens = enc.encode(text)
    if not tokens:
        return []
    out: List[str] = []
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i:i+max_tokens]
        out.append(enc.decode(chunk_tokens))
    return out


def chunk_text(text: str, min_tokens: int, max_tokens: int, overlap_tokens: int) -> List[str]:
    """
    Erzeugt Chunks (200–400 Tokens empfohlen) mit Overlap (z. B. 50).
    Heuristik:
      - Schaffe zuerst grobe max_tokens-Slices,
      - Danach füge Overlaps hinzu, indem wir vom vorherigen Ende overlap_tokens übernehmen.
    """
    text = (text or "").strip()
    if not text:
        return []

    max_tokens = max(50, int(max_tokens or 400))
    min_tokens = max(10, min(int(min_tokens or 200), max_tokens))
    overlap_tokens = max(0, int(overlap_tokens or 0))
    if overlap_tokens >= max_tokens:
        overlap_tokens = max_tokens // 4  # sane default

    # Grobe Slices
    base_slices = _split_by_tokens(text, max_tokens=max_tokens)
    if not base_slices:
        return []

    # Falls keine Overlaps benötigt
    if overlap_tokens == 0:
        return [s for s in base_slices if tokenize_len(s) >= min_tokens or len(base_slices) == 1]

    # Encoding für Overlap
    enc = _get_encoding()
    if enc is None:
        # Best-effort Overlap per Wortanzahl
        out: List[str] = []
        prev_tail_words: List[str] = []
        overlap_words = max(1, overlap_tokens)
        for i, s in enumerate(base_slices):
            words = s.split()
            if i == 0:
                out.append(s)
                prev_tail_words = words[-overlap_words:] if len(words) > overlap_words else words
            else:
                merged = " ".join(prev_tail_words + words)
                out.append(merged)
                prev_tail_words = words[-overlap_words:] if len(words) > overlap_words else words
        # Filter kurz-unter min_tokens – außer wenn es nur ein Chunk ist
        out = [s for s in out if tokenize_len(s) >= min_tokens or len(out) == 1]
        return out

    # Mit tiktoken Overlap sauber auf Tokenbasis bilden
    out_tok: List[List[int]] = []
    prev_tail: List[int] = []
    for i, s in enumerate(base_slices):
        s_tok = enc.encode(s)
        if i == 0:
            out_tok.append(s_tok)
            prev_tail = s_tok[-overlap_tokens:] if len(s_tok) > overlap_tokens else s_tok
        else:
            merged_tok = prev_tail + s_tok
            out_tok.append(merged_tok)
            prev_tail = s_tok[-overlap_tokens:] if len(s_tok) > overlap_tokens else s_tok

    out_txt = [enc.decode(toks) for toks in out_tok]
    out_txt = [s for s in out_txt if tokenize_len(s) >= min_tokens or len(out_txt) == 1]
    return out_txt


# -------- Datei-Extraktion --------

def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _now() -> int:
    return int(time.time())


def extract_texts_from_md(text: str) -> List[str]:
    """
    Minimal: vollständiger Text; optional könnte nach Headings gesplittet werden.
    Für die erste Iteration erzeugen wir einen Block; das Chunking übernimmt die feine Aufteilung.
    """
    return [text or ""]


def extract_texts_from_txt(text: str) -> List[str]:
    return [text or ""]


def extract_texts_from_json(text: str) -> List[str]:
    """
    Erwartet:
      - Array[str]
      - Array[object] mit requirementText|text
      - Objekt mit items: Array[...]
    Liefert eine Liste von Requirement-Strings.
    """
    try:
        data = json.loads(text)
    except Exception:
        return [text or ""]
    items: List[str] = []

    def _coerce(v: Any):
        if isinstance(v, str) and v.strip():
            items.append(v.strip())
        elif isinstance(v, dict):
            cand = v.get("requirementText") or v.get("text") or v.get("requirement")
            if isinstance(cand, str) and cand.strip():
                items.append(cand.strip())

    if isinstance(data, list):
        for el in data:
            _coerce(el)
    elif isinstance(data, dict):
        if isinstance(data.get("items"), list):
            for el in data["items"]:
                _coerce(el)
        else:
            # alles als JSON-Text; Chunker kümmert sich
            return [text]
    else:
        return [text]

    return items or [text]


def extract_texts_from_pdf(data: bytes) -> List[str]:
    if fitz is None:
        raise RuntimeError("PyMuPDF nicht installiert. Bitte PyMuPDF in requirements aufnehmen.")
    out: List[str] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            txt = page.get_text("text") or ""
            if txt.strip():
                out.append(txt)
    return out or [""]


def extract_texts_from_docx(data: bytes) -> List[str]:
    if DocxDocument is None:
        raise RuntimeError("python-docx nicht installiert. Bitte python-docx in requirements aufnehmen.")
    bio = io.BytesIO(data)
    doc = DocxDocument(bio)
    paras = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    text = "\n".join(paras).strip()
    return [text] if text else [""]


def _magika_guess_ct(data: bytes) -> str | None:
    """Nutze Magika (falls vorhanden), um MIME zu bestimmen."""
    try:
        if _magika is None:
            return None
        res = _magika.identify_bytes(data)
        return getattr(res, "mime_type", None) or None
    except Exception:
        return None


def _docling_convert(data: bytes, filename: str) -> List[str]:
    """Verwende Docling, um verschiedenste Formate in Textblöcke zu überführen.
    Fällt zurück auf leere Liste bei Fehlern.
    """
    try:
        if not _docling_available:
            return []
        conv = DocumentConverter()
        doc = conv.convert_bytes(data, file_name=filename)
        # Sammle Absätze/Liste/Tabellenzellen als Textblöcke
        blocks: List[str] = []
        for el in getattr(doc, "elements", []) or []:
            try:
                txt = (getattr(el, "text", None) or "").strip()
                if txt:
                    blocks.append(txt)
            except Exception:
                continue
        # Fallback: gesamter Plaintext
        if not blocks:
            try:
                ptxt = (getattr(doc, "plain_text", None) or "").strip()
                if ptxt:
                    blocks = [ptxt]
            except Exception:
                pass
        return blocks
    except Exception:
        return []


def extract_texts(
    filename: str,
    data: bytes,
    content_type: str = "",
) -> List[Dict[str, Any]]:
    """
    Liefert eine Liste von {text, meta} mit Rohtexten und Metadaten pro Dokumentteil.
    Für PDF wird pro Seite ein Eintrag erzeugt; für andere Typen idR ein Eintrag.
    """
    name_l = (filename or "").lower()
    ct = (content_type or "").lower()
    # Magika: Content-Type erkennen, falls leer oder unbekannt
    if not ct or ct in ("application/octet-stream", "binary/octet-stream"):
        try:
            guess = _magika_guess_ct(data)
            if guess:
                ct = guess.lower()
        except Exception:
            pass
    sha1 = _sha1(data)
    created = _now()

    def base_meta(extra: Dict[str, Any] | None = None):
        m = {
            "sourceFile": filename,
            "sourceType": "auto",
            "sha1": sha1,
            "createdAt": created,
        }
        if extra:
            m.update(extra)
        return m

    # Erkennung anhand von Endung/MIME
    if name_l.endswith(".md") or "markdown" in ct:
        text = data.decode("utf-8", errors="ignore")
        blocks = extract_texts_from_md(text)
        return [{"text": b, "meta": base_meta({"sourceType": "md"})} for b in blocks]

    if name_l.endswith(".txt") or "text/plain" in ct:
        text = data.decode("utf-8", errors="ignore")
        blocks = extract_texts_from_txt(text)
        return [{"text": b, "meta": base_meta({"sourceType": "txt"})} for b in blocks]

    if name_l.endswith(".json") or "application/json" in ct:
        text = data.decode("utf-8", errors="ignore")
        blocks = extract_texts_from_json(text)
        return [{"text": b, "meta": base_meta({"sourceType": "json"})} for b in blocks]

    if name_l.endswith(".pdf") or "application/pdf" in ct:
        blocks = extract_texts_from_pdf(data)
        out: List[Dict[str, Any]] = []
        for i, b in enumerate(blocks):
            out.append({"text": b, "meta": base_meta({"sourceType": "pdf", "pageNo": i + 1})})
        return out

    if name_l.endswith(".docx") or "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in ct:
        # Bevorzugt Docling, sonst python-docx
        blocks = _docling_convert(data, filename)
        if not blocks:
            blocks = extract_texts_from_docx(data)
        return [{"text": b, "meta": base_meta({"sourceType": "docx"})} for b in blocks]

    # Falls Magika HTML meldet → Docling versuchen
    if "text/html" in ct or name_l.endswith(".html") or name_l.endswith(".htm"):
        blocks = _docling_convert(data, filename)
        if blocks:
            return [{"text": b, "meta": base_meta({"sourceType": "html"})} for b in blocks]

    # Fallback als Text
    text = data.decode("utf-8", errors="ignore")
    return [{"text": text, "meta": base_meta({"sourceType": "unknown"})}]


def chunk_payloads(
    records: List[Dict[str, Any]],
    min_tokens: int | None = None,
    max_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> List[Dict[str, Any]]:
    """
    Nimmt Rohtexte mit Meta und erzeugt daraus Chunk-Payloads:
      [{ text, payload }, ...]
    payload enthält merged Metadaten + chunkIndex + tokenLen
    """
    min_tokens = min_tokens if min_tokens is not None else getattr(settings, "CHUNK_TOKENS_MIN", 200)
    max_tokens = max_tokens if max_tokens is not None else getattr(settings, "CHUNK_TOKENS_MAX", 400)
    overlap_tokens = overlap_tokens if overlap_tokens is not None else getattr(settings, "CHUNK_OVERLAP_TOKENS", 50)

    out: List[Dict[str, Any]] = []
    for rec in records:
        text = str(rec.get("text") or "").strip()
        meta = dict(rec.get("meta") or {})
        if not text:
            continue
        chunks = chunk_text(text, int(min_tokens), int(max_tokens), int(overlap_tokens))
        for idx, ch in enumerate(chunks):
            payload = dict(meta)
            payload["chunkIndex"] = idx
            payload["tokenLen"] = tokenize_len(ch)
            out.append({"text": ch, "payload": payload})
    return out