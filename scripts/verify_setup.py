#!/usr/bin/env python3
"""
Setup Verification Script for arch_team Requirements Engineering System

This script verifies that all required services are running and properly configured.
It checks:
- Environment configuration (.env file)
- Qdrant vector database connection
- arch_team Flask service (port 8000)
- Optional: FastAPI v2 backend (port 8087)
- SQLite database
- Python/Node.js dependencies

Usage:
    python scripts/verify_setup.py
    python scripts/verify_setup.py --full  # Include optional services
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
import argparse

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def print_header(text: str):
    """Print formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")

def print_status(check_name: str, passed: bool, message: str = ""):
    """Print status with colored indicator"""
    status = "✓" if passed else "✗"
    color = "\033[92m" if passed else "\033[91m"  # Green or Red
    reset = "\033[0m"

    print(f"{color}{status}{reset} {check_name}")
    if message:
        print(f"  → {message}")

def check_env_file() -> Tuple[bool, Dict[str, str]]:
    """Check if .env file exists and load it"""
    env_path = PROJECT_ROOT / ".env"

    if not env_path.exists():
        return False, {}

    # Load .env file
    env_vars = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    return True, env_vars

def check_python_dependencies() -> Tuple[bool, List[str]]:
    """Check if critical Python packages are installed"""
    required_packages = [
        "flask",
        "fastapi",
        "openai",
        "autogen",
        "qdrant_client",
        "uvicorn",
    ]

    missing = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing.append(package)

    return len(missing) == 0, missing

def check_node_dependencies() -> bool:
    """Check if node_modules exists"""
    node_modules = PROJECT_ROOT / "node_modules"
    return node_modules.exists()

def check_qdrant(port: int = 6401) -> Tuple[bool, str]:
    """Check Qdrant connection"""
    try:
        import requests
        url = f"http://localhost:{port}/collections"
        response = requests.get(url, timeout=3)

        if response.status_code == 200:
            data = response.json()
            collections = data.get("result", {}).get("collections", [])
            collection_names = [c.get("name") for c in collections]
            return True, f"Connected on port {port}, Collections: {len(collection_names)}"
        else:
            return False, f"HTTP {response.status_code}"
    except ImportError:
        return False, "requests package not installed"
    except Exception as e:
        return False, str(e)

def check_arch_team_service(port: int = 8000) -> Tuple[bool, str]:
    """Check arch_team Flask service"""
    try:
        import requests
        url = f"http://localhost:{port}/health"
        response = requests.get(url, timeout=3)

        if response.status_code == 200:
            return True, f"Running on port {port}"
        else:
            return False, f"HTTP {response.status_code}"
    except ImportError:
        return False, "requests package not installed"
    except Exception as e:
        return False, f"Not running: {e}"

def check_fastapi_service(port: int = 8087) -> Tuple[bool, str]:
    """Check FastAPI v2 backend"""
    try:
        import requests
        url = f"http://localhost:{port}/health"
        response = requests.get(url, timeout=3)

        if response.status_code == 200:
            return True, f"Running on port {port}"
        else:
            return False, f"HTTP {response.status_code}"
    except ImportError:
        return False, "requests package not installed"
    except Exception as e:
        return False, f"Not running: {e}"

def check_sqlite_db(db_path: str) -> Tuple[bool, str]:
    """Check SQLite database"""
    if db_path.startswith("/app/data"):
        # Docker path, adjust to local
        db_path = db_path.replace("/app/data", "data")

    db_file = PROJECT_ROOT / db_path.lstrip("./")

    if not db_file.exists():
        return False, f"Database not found at {db_file}"

    try:
        import sqlite3
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        return True, f"Found {len(tables)} tables: {', '.join(tables[:5])}"
    except Exception as e:
        return False, str(e)

def verify_env_configuration(env_vars: Dict[str, str]) -> List[Tuple[str, bool, str]]:
    """Verify critical environment variables"""
    checks = []

    # OpenAI API Key
    openai_key = env_vars.get("OPENAI_API_KEY", "")
    mock_mode = env_vars.get("MOCK_MODE", "false").lower() == "true"

    if openai_key and openai_key.startswith("sk-"):
        checks.append(("OPENAI_API_KEY", True, "Set (sk-...)"))
    elif mock_mode:
        checks.append(("OPENAI_API_KEY", True, "Not set (MOCK_MODE enabled)"))
    else:
        checks.append(("OPENAI_API_KEY", False, "Missing (and MOCK_MODE not enabled)"))

    # Qdrant Port
    qdrant_port = env_vars.get("QDRANT_PORT", "")
    if qdrant_port == "6401":
        checks.append(("QDRANT_PORT", True, f"{qdrant_port} (correct for docker-compose)"))
    else:
        checks.append(("QDRANT_PORT", False, f"{qdrant_port} (should be 6401 for docker-compose)"))

    # Qdrant URL
    qdrant_url = env_vars.get("QDRANT_URL", "")
    if qdrant_url:
        checks.append(("QDRANT_URL", True, qdrant_url))
    else:
        checks.append(("QDRANT_URL", False, "Not set"))

    # Model
    model = env_vars.get("OPENAI_MODEL", "")
    if model:
        checks.append(("OPENAI_MODEL", True, model))
    else:
        checks.append(("OPENAI_MODEL", False, "Not set"))

    return checks

def main():
    parser = argparse.ArgumentParser(description="Verify arch_team setup")
    parser.add_argument("--full", action="store_true", help="Check optional services")
    args = parser.parse_args()

    print_header("arch_team Setup Verification")

    all_passed = True

    # 1. Check .env file
    print_header("1. Environment Configuration")
    env_exists, env_vars = check_env_file()
    print_status(".env file exists", env_exists)

    if env_exists:
        env_checks = verify_env_configuration(env_vars)
        for check_name, passed, message in env_checks:
            print_status(f"  {check_name}", passed, message)
            all_passed = all_passed and passed
    else:
        print("  ⚠ Run: cp .env.example .env")
        all_passed = False

    # 2. Check dependencies
    print_header("2. Dependencies")

    py_ok, missing_py = check_python_dependencies()
    print_status("Python packages", py_ok)
    if not py_ok:
        print(f"  → Missing: {', '.join(missing_py)}")
        print(f"  → Run: pip install -r requirements.txt")
        all_passed = False

    node_ok = check_node_dependencies()
    print_status("Node.js packages", node_ok)
    if not node_ok:
        print(f"  → Run: npm install")
        all_passed = False

    # 3. Check services
    print_header("3. Required Services")

    # Qdrant
    qdrant_port = int(env_vars.get("QDRANT_PORT", "6401")) if env_exists else 6401
    qdrant_ok, qdrant_msg = check_qdrant(qdrant_port)
    print_status(f"Qdrant (port {qdrant_port})", qdrant_ok, qdrant_msg)
    if not qdrant_ok:
        print(f"  → Run: docker-compose -f docker-compose.qdrant.yml up -d")
        all_passed = False

    # arch_team Flask service
    arch_port = int(env_vars.get("APP_PORT", "8000")) if env_exists else 8000
    arch_ok, arch_msg = check_arch_team_service(arch_port)
    print_status(f"arch_team service (port {arch_port})", arch_ok, arch_msg)
    if not arch_ok:
        print(f"  → Run: python -m arch_team.service")
        all_passed = False

    # SQLite database
    if env_exists:
        db_path = env_vars.get("SQLITE_PATH", "./data/app.db")
        db_ok, db_msg = check_sqlite_db(db_path)
        print_status("SQLite database", db_ok, db_msg)
        if not db_ok and "not found" in db_msg.lower():
            print(f"  ℹ Database will be created on first service start")

    # 4. Optional services
    if args.full:
        print_header("4. Optional Services")

        fastapi_ok, fastapi_msg = check_fastapi_service(8087)
        print_status("FastAPI v2 backend (port 8087)", fastapi_ok, fastapi_msg)
        if not fastapi_ok:
            print(f"  ℹ Optional: python -m uvicorn backend_app_v2.main:fastapi_app --port 8087")

    # Summary
    print_header("Summary")

    if all_passed:
        print("\033[92m✓ All critical checks passed!\033[0m")
        print("\nYou can start the React frontend:")
        print("  npm run dev")
        print("\nAccess the UI at: http://localhost:3000")
    else:
        print("\033[91m✗ Some checks failed. Please fix the issues above.\033[0m")
        print("\nQuick start commands:")
        print("  1. cp .env.example .env  # Then edit .env to add OPENAI_API_KEY")
        print("  2. pip install -r requirements.txt")
        print("  3. npm install")
        print("  4. docker-compose -f docker-compose.qdrant.yml up -d")
        print("  5. python -m arch_team.service")
        print("  6. npm run dev")

    print()
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
