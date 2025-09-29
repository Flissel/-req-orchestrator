#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qdrant Collections Check/Migration Tool (Dry-Run/Auto-Create/Recreate)

Zweck:
- Prüft, ob die konfigurierte Qdrant-Collection existiert und ob die Vektordimension passt.
- Kann optional Collections (re)erstellen (destruktiv bei --recreate).
- Dimension wird aus Embeddings autodetektiert (fallback 1536) oder via --dim überschrieben.

Nutzung:
  python dev/qdrant_migrate.py --dry-run
  python dev/qdrant_migrate.py --auto-create
  python dev/qdrant_migrate.py --recreate
  python dev/qdrant_migrate.py --collection requirements_v2 --dim 1536 --auto-create

Optionen:
  --collection   Name der Collection (Default: ENV QDRANT_COLLECTION oder requirements_v1)
  --dim          Ziel-Dimension (Default: autodetect aus Embeddings)
  --dry-run      Nur prüfen, keine Änderungen
  --auto-create  Legt fehlende Collection an (wenn nicht vorhanden); kein Drop
  --recreate     Droppt und legt neu an (destruktiv)

Rückgabecodes:
  0 = ok (oder erfolgreich ausgeführt)
  1 = Fehler

Hinweis:
- Verwendet backend_app.vector_store (ensure/reset) und autodetect aus backend_app.embeddings / settings.
- Für „Backfill/Reindex“ nur Hinweis/Platzhalter (separate Pipelines/Jobs erforderlich).
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional

def main() -> int:
    # Lazy-Imports, um Pfade und Abhängigkeiten früh zu validieren
    try:
        from backend_app import settings as _settings  # type: ignore
        from backend_app.embeddings import get_embeddings_dim as _get_dim  # type: ignore
        from backend_app.vector_store import (  # type: ignore
            get_qdrant_client as _get_client,
            list_collections as _list_cols,
            reset_collection as _reset_coll,
            ensure_collection as _ensure_coll,
        )
    except Exception as e:
        print(f"[qdrant-migrate][error] Konnte Module nicht importieren: {e}", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description="Qdrant Collections Check/Migration Tool")
    parser.add_argument("--collection", type=str, default=getattr(_settings, "QDRANT_COLLECTION", "requirements_v1"))
    parser.add_argument("--dim", type=int, default=0, help="Ziel-Dimension; 0 = autodetect")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--auto-create", action="store_true", help="Erstellt fehlende Collection (kein Drop)")
    parser.add_argument("--recreate", action="store_true", help="Drop + Recreate (destruktiv)")
    args = parser.parse_args()

    coll = str(args.collection or getattr(_settings, "QDRANT_COLLECTION", "requirements_v1"))
    # Dim autodetect
    try:
        detected_dim = int(_get_dim())
    except Exception:
        detected_dim = 1536
    dim = int(args.dim or detected_dim or 1536)

    # Hole Client und prüfe vorhandene Collections
    try:
        cli, effective_port = _get_client()
        cols = _list_cols(cli)
        exists = coll in (cols or [])
    except Exception as e:
        print(f"[qdrant-migrate][error] Qdrant nicht erreichbar oder Fehler beim Listen: {e}", file=sys.stderr)
        return 1

    # Versuche Dimension zu lesen, falls vorhanden
    current_dim: Optional[int] = None
    if exists:
        try:
            info = cli.get_collection(collection_name=coll)
            vp = getattr(getattr(info, "config", None), "params", None)
            v = getattr(vp, "vectors", None)
            cdim = getattr(v, "size", None)
            if cdim is not None:
                current_dim = int(cdim)
        except Exception:
            current_dim = None

    # Bericht
    print("=== Qdrant Collections Check ===")
    print(f"URL:        {getattr(_settings, 'QDRANT_URL', 'http://localhost')}:{getattr(_settings, 'QDRANT_PORT', 6333)}")
    print(f"Collection: {coll}")
    print(f"Exists:     {exists}")
    print(f"Detected Dim (Embeddings): {detected_dim}")
    print(f"Current Dim (Qdrant):      {current_dim if current_dim is not None else '-'}")
    print(f"Target Dim:                {dim}")
    print(f"Mode:       dry_run={args.dry_run} auto_create={args.auto_create} recreate={args.recreate}")
    print("================================")

    if args.dry_run:
        # Keine Änderungen durchführen
        return 0

    try:
        if args.recreate:
            # Drop + Create (destruktiv)
            _reset_coll(client=cli, collection_name=coll, dim=dim)
            print(f"[qdrant-migrate] Recreated collection '{coll}' with dim={dim}")
            return 0

        if args.auto_create:
            if not exists:
                # create (non-destructive if missing)
                _ensure_coll(client=cli, collection_name=coll, dim=dim)
                print(f"[qdrant-migrate] Created missing collection '{coll}' with dim={dim}")
                return 0
            # exists: nur Hinweis, keine Änderung
            print(f"[qdrant-migrate] Collection '{coll}' existiert bereits (keine Änderung).")
            if current_dim is not None and current_dim != dim:
                print(f"[qdrant-migrate][warn] Dim mismatch: current={current_dim}, target={dim} (kein Drop im auto-create Modus).")
            return 0

        # Weder auto-create noch recreate: nur check
        if not exists:
            print(f"[qdrant-migrate][warn] Collection '{coll}' existiert nicht. Mit --auto-create anlegen oder --recreate erzwingen.")
            return 0

        if current_dim is not None and current_dim != dim:
            print(f"[qdrant-migrate][warn] Dim mismatch: current={current_dim}, target={dim}. Mit --recreate anpassen (destruktiv).")
        else:
            print("[qdrant-migrate] OK: Collection vorhanden und Dimension passt (oder unbekannt).")
        return 0
    except Exception as e:
        print(f"[qdrant-migrate][error] Migration fehlgeschlagen: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())