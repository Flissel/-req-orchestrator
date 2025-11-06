#!/usr/bin/env python3
"""
Analyze which root directories are used by arch_team.
"""

import os
import re
from pathlib import Path
from collections import defaultdict

def extract_imports(file_path):
    """Extract all imports from a Python file."""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Match: import module / import module as alias
        for match in re.finditer(r'^import\s+([\w.]+)', content, re.MULTILINE):
            imports.add(match.group(1))

        # Match: from module import ...
        for match in re.finditer(r'^from\s+([\w.]+)\s+import', content, re.MULTILINE):
            imports.add(match.group(1))

    except Exception as e:
        print(f"Error reading {file_path}: {e}")

    return imports

def find_all_python_files(directory):
    """Find all Python files in directory."""
    files = []
    for root, dirs, filenames in os.walk(directory):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for filename in filenames:
            if filename.endswith('.py'):
                files.append(os.path.join(root, filename))
    return sorted(files)

def main():
    base_dir = Path('/home/user/-req-orchestrator')
    arch_team_dir = base_dir / 'arch_team'

    # Root directories to check
    root_dirs = [
        'backend_app',
        'backend_app_v2',
        'backend_app_fastapi',
        'agent_worker',
        'config',
        'tests',
        'dev',
        'frontend',
        'src',
    ]

    # Find all Python files in arch_team
    all_files = find_all_python_files(arch_team_dir)

    # Track which root directories are imported
    external_deps = defaultdict(set)  # root_dir -> set of files that import it

    print("=== EXTERNAL ROOT DIRECTORY DEPENDENCIES ===\n")

    for file_path in all_files:
        rel_path = os.path.relpath(file_path, base_dir)
        imports = extract_imports(file_path)

        for imp in imports:
            parts = imp.split('.')
            root_module = parts[0]

            if root_module in root_dirs:
                external_deps[root_module].add(rel_path)

    # Print results
    if external_deps:
        for module in sorted(external_deps.keys()):
            files = external_deps[module]
            print(f"📦 {module}/ (used by {len(files)} arch_team file(s))")
            for f in sorted(files):
                print(f"   ├─ {f}")
            print()
    else:
        print("  (no external root directory dependencies found)")

    # Summary
    print("\n=== SUMMARY ===\n")
    print(f"Root directories used by arch_team: {len(external_deps)}")
    print(f"Total arch_team files analyzed: {len(all_files)}")

    if external_deps:
        print("\nDependency details:")
        for module in sorted(external_deps.keys()):
            print(f"  - {module}: {len(external_deps[module])} files depend on it")

    # Check if any root directories exist but are NOT used
    print("\n=== ROOT DIRECTORIES NOT USED BY ARCH_TEAM ===\n")
    unused_roots = []
    for root_dir in root_dirs:
        if os.path.exists(base_dir / root_dir) and root_dir not in external_deps:
            unused_roots.append(root_dir)

    if unused_roots:
        for root in sorted(unused_roots):
            print(f"  ✗ {root}/ (exists but not imported by arch_team)")
    else:
        print("  (all existing root directories are used)")

if __name__ == '__main__':
    main()
