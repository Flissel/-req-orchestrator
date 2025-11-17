# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.core.embeddings import build_embeddings  # optional für embeddings-gestützte Evaluation
from backend.api_v2_part2 import (
    _lx_gold_dir,
    _lx_gold_path,
    _lx_results_dir,
    _lx_result_path,
    _normalize_req_text,
    _similarity_score,
    _cosine_sim,
)

router = APIRouter(tags=["gold"])


@router.get("/api/v1/lx/gold/list")
def lx_gold_list_fastapi() -> JSONResponse:
    """
    FastAPI-Port: Liste gespeicherter Gold-Sets (Dateinamen ohne .json)
    """
    try:
        d = _lx_gold_dir()
        names = []
        for fn in os.listdir(d):
            if fn.endswith(".json"):
                names.append(os.path.splitext(fn)[0])
        names.sort()
        return JSONResponse(content={"items": names}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.get("/api/v1/lx/gold/get")
def lx_gold_get_fastapi(id: Optional[str] = None) -> JSONResponse:
    """
    FastAPI-Port: Gold-Set laden
    """
    try:
        gid = id or "default"
        p = _lx_gold_path(gid)
        if not os.path.exists(p):
            return JSONResponse(content={"goldId": gid, "gold": {"items": []}}, status_code=200)
        import json as _json
        with open(p, "r", encoding="utf-8") as f:
            data = _json.load(f)
        return JSONResponse(content={"goldId": gid, "gold": data}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.post("/api/v1/lx/gold/save")
async def lx_gold_save_fastapi(request: Request) -> JSONResponse:
    """
    FastAPI-Port: Gold-Set speichern
    Body: { "goldId": "demo", "gold": { "items": [ { requirementText }, ... ] } }
    """
    try:
        body = await request.json()
        gid = (body.get("goldId") or "default").strip() or "default"
        gold = body.get("gold")
        if not isinstance(gold, dict) or not isinstance(gold.get("items"), list):
            return JSONResponse(content={"error": "invalid_request", "message": "gold.items muss Liste sein"}, status_code=400)
        import json as _json
        p = _lx_gold_path(gid)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            _json.dump(gold, f, ensure_ascii=False, indent=2)
        return JSONResponse(content={"status": "ok", "goldId": gid, "path": p}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.post("/api/v1/lx/evaluate")
async def lx_evaluate_fastapi(request: Request) -> JSONResponse:
    """
    FastAPI-Port: Evaluate predicted requirements against a gold set.
    Body:
      {
        goldId?: str,
        gold?: { items: [ { requirementText } | str ] },
        saveId?: str, latest?: bool, items?: [ { requirementText } ],
        threshold?: float,
        use_embeddings?: bool,
        embed_threshold?: float
      }
    """
    try:
        body = await request.json()
        threshold = float(body.get("threshold") or 0.9)
        use_embeddings = bool(body.get("use_embeddings") or False)
        embed_threshold = float(body.get("embed_threshold") or 0.9)

        # Load GOLD
        gold_items: List[Dict[str, Any]] = []
        if isinstance(body.get("gold"), dict):
            gold_items = list(body.get("gold", {}).get("items") or [])
        elif body.get("goldId"):
            gid = str(body.get("goldId"))
            p = _lx_gold_path(gid)
            if os.path.exists(p):
                import json as _json
                with open(p, "r", encoding="utf-8") as f:
                    gold_data = _json.load(f) or {}
                gold_items = gold_data.get("items") or []
        gold_strs = [_normalize_req_text(x) for x in (gold_items or []) if _normalize_req_text(x)]

        # Load PRED
        pred_texts: List[str] = []
        if isinstance(body.get("items"), list):
            for x in body.get("items"):
                pred_texts.append(_normalize_req_text(x))
        else:
            sid = body.get("saveId")
            if not sid and bool(body.get("latest")):
                d = _lx_results_dir()
                files = [os.path.join(d, fn) for fn in os.listdir(d) if fn.endswith(".json")]
                files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                sid = os.path.splitext(os.path.basename(files[0]))[0] if files else None
            if sid:
                import json as _json
                p = _lx_result_path(str(sid))
                if os.path.exists(p):
                    with open(p, "r", encoding="utf-8") as f:
                        data = _json.load(f)
                    for e in (data.get("lxPreview") or []):
                        if str(e.get("extraction_class") or "").lower() == "requirement":
                            pred_texts.append(_normalize_req_text(e.get("extraction_text")))
        pred_texts = [s for s in pred_texts if s]

        # Evaluate
        used_g = [False] * len(gold_strs)
        tp = 0
        matches = []

        pred_vecs = []
        gold_vecs = []
        if use_embeddings and pred_texts and gold_strs:
            try:
                pred_vecs = build_embeddings(pred_texts)
                gold_vecs = build_embeddings(gold_strs)
            except Exception:
                pred_vecs = []
                gold_vecs = []

        for i, pred in enumerate(pred_texts):
            best_j = -1
            best_sim = 0.0
            for j, gold in enumerate(gold_strs):
                if used_g[j]:
                    continue
                sim = _similarity_score(pred, gold)
                if use_embeddings and pred_vecs and gold_vecs:
                    try:
                        cs = _cosine_sim(pred_vecs[i], gold_vecs[j])
                        sim = max(sim, cs if cs >= embed_threshold else sim)
                    except Exception:
                        pass
                if sim > best_sim:
                    best_sim = sim
                    best_j = j
            if best_j >= 0 and best_sim >= threshold:
                used_g[best_j] = True
                tp += 1
                matches.append({"pred": pred_texts[i], "gold": gold_strs[best_j], "score": round(best_sim, 3)})

        fp = max(0, len(pred_texts) - tp)
        fn = max(0, len(gold_strs) - tp)
        prec = (tp / max(1, tp + fp))
        rec = (tp / max(1, tp + fn))
        f1 = (2 * prec * rec / max(1e-9, prec + rec)) if (prec + rec) > 0 else 0.0

        # Beispiele für Fehler
        unmatched_gold = [gold_strs[i] for i, u in enumerate(used_g) if not u]

        return JSONResponse(
            content={
                "metrics": {
                    "threshold": threshold,
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "precision": round(prec, 3),
                    "recall": round(rec, 3),
                    "f1": round(f1, 3),
                },
                "matches": matches,
                "unmatched_gold": unmatched_gold[:20],
                "pred_count": len(pred_texts),
                "gold_count": len(gold_strs),
            },
            status_code=200,
        )
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)