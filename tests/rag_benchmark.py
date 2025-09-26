import json
import os
import re
import time
from typing import List, Dict, Any, Tuple

import requests

API_BASE = os.environ.get("API_BASE", "http://localhost:8083").rstrip("/")


def get_requirements() -> List[str]:
    """
    Lädt die Referenz-Requirements aus dem Backend-Endpunkt.
    Backend liest aus settings.REQUIREMENTS_MD_PATH (Default via .env: /data/requirements.md).
    """
    url = f"{API_BASE}/api/v1/demo/requirements"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("items", [])
    reqs = [str(it.get("requirementText") or it.get("requirement") or it.get("text") or "").strip() for it in items]
    return [r for r in reqs if r]


def rag_search(query: str, top_k: int = 5) -> Dict[str, Any]:
    url = f"{API_BASE}/api/v1/rag/search"
    resp = requests.get(url, params={"query": query, "top_k": top_k}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def tokenize(text: str) -> List[str]:
    t = re.sub(r"[^a-zA-Z0-9äöüÄÖÜß]+", " ", text.lower()).strip()
    return [w for w in t.split() if w and len(w) >= 3]


def keyword_overlap(query: str, snippet: str) -> float:
    """
    Sehr einfache Heuristik: Anteil Query-Keywords, die im Snippet vorkommen.
    """
    q_tok = set(tokenize(query))
    s_tok = set(tokenize(snippet))
    if not q_tok:
        return 0.0
    hit = len(q_tok.intersection(s_tok))
    return hit / len(q_tok)


def ref_similarity(snippet: str, refs: List[str]) -> float:
    """
    Grobe Heuristik: max Keyword-Overlap zwischen Snippet und jedem Requirement.
    """
    s_tok = set(tokenize(snippet))
    if not s_tok:
        return 0.0
    best = 0.0
    for r in refs:
        r_tok = set(tokenize(r))
        if not r_tok:
            continue
        overlap = len(s_tok.intersection(r_tok)) / max(1, len(r_tok))
        if overlap > best:
            best = overlap
    return best


PROMPTS: List[str] = [
    "Wie viele Requirements sind in der Datei?",
    "Beschreibt das Dokument Anforderungen an einen Health-Endpoint?",
    "Gibt es eine Anforderung zu CORS für /api/*?",
    "Wie soll Docker Compose Volumes und SQLite Datei mounten?",
    "Welche Endpunkte werden als Zielzustand genannt?",
    "Gibt es Anforderungen zu Batch-Verarbeitung oder Parallelität?",
    "Wo werden Korrekturen gespeichert (Pfad/Datei)?",
    "Welche Kriterien werden für die Bewertung genutzt?",
    "Gibt es Anforderungen an die Laufzeitkonfiguration/Settings?",
    "Ist ein Demo-Endpunkt zum Laden von Requirements vorgesehen?",
    "Gibt es eine Anforderung zur Rückgabe eines JSON-Objekts beim Health-Check?",
    "Gibt es Anforderungen zur Nutzung einer Vektor-Suche/RAG?",
    "Sind Upload- oder Ingest-Funktionen im Scope erwähnt?",
    "Welche Hinweise zu Deployment/Compose stehen im Dokument?",
    "Wird die Nutzung von SQLite explizit gefordert?",
    "Sind Entscheidungen für akzeptiert/abgelehnt irgendwo festgehalten?",
    "Gibt es Hinweise zu Systemprompts oder Kriterien-Konfig?",
    "Wie ist das Frontend eingebunden bzw. ausgeliefert?",
    "Ist CORS Preflight adressiert?",
    "Gibt es Hinweise zu Ports der Dienste (Frontend/Backend)?",
]


def evaluate(query: str, refs: List[str], top_k: int = 5) -> Dict[str, Any]:
    data = rag_search(query, top_k=top_k)
    hits = data.get("hits", []) or []
    items = []
    best_keyword = 0.0
    best_ref = 0.0
    for i, h in enumerate(hits, 1):
        p = h.get("payload") or {}
        score = h.get("score")
        snippet = str(p.get("text") or "")[:400]
        src = str(p.get("sourceFile") or p.get("source") or "")
        chunk_index = p.get("chunkIndex")
        kw = keyword_overlap(query, snippet)
        rs = ref_similarity(snippet, refs)
        best_keyword = max(best_keyword, kw)
        best_ref = max(best_ref, rs)
        items.append({
            "rank": i,
            "score": float(score) if isinstance(score, (int, float)) else score,
            "source": src,
            "chunkIndex": chunk_index,
            "keywordOverlap": round(kw, 4),
            "refSim": round(rs, 4),
            "snippet": snippet
        })

    quality = "ok"
    notes = []
    if best_keyword < 0.2:
        quality = "weak"
        notes.append("Geringer Keyword-Overlap zur Query (< 0.2).")
    if best_ref < 0.15:
        quality = "weak"
        notes.append("Geringe Ähnlichkeit zu Referenz-Requirements (< 0.15).")

    return {
        "query": query,
        "topK": top_k,
        "bestKeywordOverlap": round(best_keyword, 4),
        "bestRefSimilarity": round(best_ref, 4),
        "quality": quality,
        "notes": notes,
        "items": items
    }


def main():
    out_dir = os.path.join("tests", "out")
    os.makedirs(out_dir, exist_ok=True)

    print(f"Backend: {API_BASE}")
    print("Lade Referenz-Requirements …")
    refs = get_requirements()
    print(f"Referenzen: {len(refs)} Items")

    report: Dict[str, Any] = {
        "ts": int(time.time()),
        "apiBase": API_BASE,
        "promptCount": len(PROMPTS),
        "results": []
    }

    ok_cnt = 0
    weak_cnt = 0

    for q in PROMPTS:
        try:
            res = evaluate(q, refs, top_k=5)
            report["results"].append(res)
            if res["quality"] == "ok":
                ok_cnt += 1
            else:
                weak_cnt += 1
            print(f"[{res['quality']}] {q}  bestKW={res['bestKeywordOverlap']} bestRef={res['bestRefSimilarity']}")
        except Exception as e:
            report["results"].append({
                "query": q,
                "error": str(e)
            })
            weak_cnt += 1
            print(f"[error] {q} → {e}")

    report["summary"] = {
        "ok": ok_cnt,
        "weak": weak_cnt,
        "total": len(PROMPTS),
        "ok_ratio": round(ok_cnt / max(1, len(PROMPTS)), 3)
    }

    # Persist Report JSON
    json_path = os.path.join(out_dir, "rag_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Markdown Kurzreport
    md_lines = [
        "# RAG Benchmark Report",
        "",
        f"- API Base: {API_BASE}",
        f"- Referenzen: {len(refs)}",
        f"- Prompts: {len(PROMPTS)}",
        f"- OK: {ok_cnt}  Weak: {weak_cnt}  Ratio OK: {report['summary']['ok_ratio']}",
        "",
        "## Ergebnisse",
    ]
    for r in report["results"]:
        if "error" in r:
            md_lines.append(f"- [error] {r['query']} → {r['error']}")
        else:
            md_lines.append(
                f"- [{r['quality']}] {r['query']} (bestKW={r['bestKeywordOverlap']}, bestRef={r['bestRefSimilarity']})"
            )
            if r.get("items"):
                top = r["items"][0]
                md_lines.append(
                    f"  - Top1: score={top['score']} src={top['source']}#{top.get('chunkIndex')} kw={top['keywordOverlap']} ref={top['refSim']}"
                )
    md_path = os.path.join(out_dir, "rag_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"\nReport geschrieben: {json_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()