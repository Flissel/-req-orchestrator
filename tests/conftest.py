# Ensure project root is on sys.path so 'arch_team.*' imports work during test collection
import sys as _sys_path_guard
from pathlib import Path as _Path_path_guard
_PROJECT_ROOT = str(_Path_path_guard(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in _sys_path_guard.path:
    _sys_path_guard.path.insert(0, _PROJECT_ROOT)
# --- Diagnostics: Frühes Logging von sys.path und Herkunft von 'arch_team' ---
def _diag_log_sys_path_and_arch_team():
    """
    Gibt Diagnose-Informationen aus, um Import-Reihenfolge/Shadowing zu erkennen:
      - Projektroot (aus Guard oben)
      - sys.path-Head
      - lokaler Pfad zu ./arch_team
      - Falls 'arch_team' bereits importiert ist: __file__/__path__
      - Andernfalls: find_spec('arch_team')-Resultat (origin/submodule_search_locations)
    """
    try:
        import sys as _sys_diag
        import importlib.util as _importlib_util
        from pathlib import Path as _Path_diag

        _head = list(_sys_diag.path)[:8]
        print(f"[diag] project_root={_PROJECT_ROOT}")
        print(f"[diag] sys.path[0:8]={_head}")

        _local_arch_dir = str(_Path_diag('arch_team').resolve())
        print(f"[diag] local_arch_team_dir={_local_arch_dir}")

        if 'arch_team' in _sys_diag.modules:
            _m = _sys_diag.modules['arch_team']
            _m_file = getattr(_m, '__file__', None)
            _m_path = getattr(_m, '__path__', None)
            print(f"[diag] arch_team already in sys.modules: __file__={_m_file} __path__={_m_path}")
        else:
            _spec = _importlib_util.find_spec('arch_team')
            if _spec is None:
                print("[diag] find_spec('arch_team') -> None (kein Treffer auf sys.path)")
            else:
                _origin = getattr(_spec, 'origin', None)
                _subs = getattr(_spec, 'submodule_search_locations', None)
                try:
                    _subs_list = list(_subs) if _subs is not None else None
                except Exception:
                    _subs_list = str(_subs)
                print(f"[diag] arch_team not imported yet; find_spec -> origin={_origin} submodule_search_locations={_subs_list}")
    except Exception as _e:
        print(f"[diag] error while logging diagnostics: {_e!r}")

# Führe direkt beim Import des conftest Diagnose-Logging aus (vor weiteren Imports).
_diag_log_sys_path_and_arch_team()
# --- Ende Diagnostics ---
# Global pytest configuration for offline test runs.
# Injects lightweight fakes for backend_app.api and backend_app.embeddings into sys.modules
# so that importing backend_app submodules does NOT pull heavy runtime deps (tenacity, requests, Flask).
# This allows end-to-end offline tests without modifying production code.

import sys
import types
from pathlib import Path


def _fake_backend_embeddings(dim: int = 8) -> types.ModuleType:
    """
    Provide a minimal embeddings module compatible with:
      - get_embeddings_dim() -> int
      - build_embeddings(texts: list[str]) -> list[list[float]]

    Deterministic, offline-friendly vectors based on a simple hash.
    """
    mod = types.ModuleType("backend_app.embeddings")

    def get_embeddings_dim() -> int:
        return dim

    def build_embeddings(texts):
        vecs = []
        texts = texts or []
        for t in texts:
            h = abs(hash(t))
            # Deterministic dim-length vector in [0,1)
            vec = [((float((h >> (i % 8)) & 0xFF) + (len(t) % 7)) % 97) / 97.0 for i in range(dim)]
            vecs.append(vec)
        return vecs

    mod.get_embeddings_dim = get_embeddings_dim
    mod.build_embeddings = build_embeddings
    return mod


def _fake_backend_api() -> types.ModuleType:
    """
    Provide a minimal API module stub that satisfies:
      - api_bp (blueprint placeholder)
    """
    mod = types.ModuleType("backend_app.api")
    mod.api_bp = None  # Dummy blueprint placeholder
    return mod


def _ensure_backend_namespace_package() -> None:
    """
    Register a namespace-like package for 'backend_app' to avoid executing its real __init__.py.
    This allows importing real submodules like backend_app.ingest from disk while preventing
    heavy deps from being pulled at package import time.
    """
    if "backend_app" not in sys.modules or not getattr(sys.modules.get("backend_app"), "__path__", None):
        pkg = types.ModuleType("backend_app")
        # Point to actual folder so submodules (e.g., backend_app.ingest) can be imported from disk
        pkg.__path__ = [str(Path("backend_app").resolve())]
        sys.modules["backend_app"] = pkg


def _install_backend_fakes(dim: int = 8) -> None:
    """
    Install fakes for backend_app.api and backend_app.embeddings into sys.modules.
    Must run BEFORE any import of modules that transitively import backend_app.*.
    """
    _ensure_backend_namespace_package()
    sys.modules["backend_app.embeddings"] = _fake_backend_embeddings(dim=dim)
    sys.modules["backend_app.api"] = _fake_backend_api()
    # Expose submodules as attributes on the package so monkeypatch.resolve('backend_app.embeddings.*') works
    pkg = sys.modules.get("backend_app")
    if pkg is not None:
        try:
            setattr(pkg, "embeddings", sys.modules["backend_app.embeddings"])
            setattr(pkg, "api", sys.modules["backend_app.api"])
        except Exception:
            # Non-fatal: continue without raising
            pass


# Perform installation at import time so it takes effect before test collection imports modules.
_install_backend_fakes()