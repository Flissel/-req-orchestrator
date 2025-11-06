#!/usr/bin/env python3
"""
Analyze arch_team directory to find:
1. Unused files (not imported by any other file)
2. External dependencies (which root directories are used)
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

def normalize_import(import_name, base_dir="arch_team"):
    """Normalize import to file path."""
    # Handle relative imports
    if import_name.startswith('.'):
        return None

    # Convert to path
    parts = import_name.split('.')

    # Check if it's an arch_team import
    if parts[0] == 'arch_team':
        # Convert to relative path
        return '/'.join(parts) + '.py'

    return None

def find_all_python_files(directory):
    """Find all Python files in directory."""
    files = []
    for root, dirs, filenames in os.walk(directory):
        for filename in filenames:
            if filename.endswith('.py'):
                files.append(os.path.join(root, filename))
    return sorted(files)

def main():
    base_dir = Path('/home/user/-req-orchestrator')
    arch_team_dir = base_dir / 'arch_team'

    # Find all Python files
    all_files = find_all_python_files(arch_team_dir)

    # Build dependency map
    file_imports = {}  # file -> set of imports
    imported_by = defaultdict(set)  # file -> set of files that import it
    external_deps = defaultdict(set)  # external module -> files that use it

    print("=== ANALYZING IMPORTS ===\n")

    for file_path in all_files:
        rel_path = os.path.relpath(file_path, base_dir)
        imports = extract_imports(file_path)
        file_imports[rel_path] = imports

        for imp in imports:
            # Check if it's an arch_team import
            normalized = normalize_import(imp)
            if normalized:
                # Check if file exists
                target_file = str(base_dir / normalized)
                if os.path.exists(target_file):
                    imported_by[normalized].add(rel_path)
                # Also check __init__.py
                if normalized.endswith('.py'):
                    init_file = normalized[:-3] + '/__init__.py'
                    if os.path.exists(str(base_dir / init_file)):
                        imported_by[init_file].add(rel_path)

            # Track external dependencies
            parts = imp.split('.')
            root_module = parts[0]

            # Check if it's a root directory dependency
            root_dirs = ['backend_app', 'backend_app_v2', 'backend_app_fastapi',
                        'agent_worker', 'config', 'data', 'tests']
            if root_module in root_dirs:
                external_deps[root_module].add(rel_path)

    # Entry points (files that can be run directly or are primary interfaces)
    entry_points = [
        'arch_team/main.py',
        'arch_team/service.py',
        'arch_team/autogen_rac.py',
        'arch_team/test_imports.py',
        'arch_team/test_validation_e2e.py',
    ]

    # Find files that are never imported
    all_rel_files = [os.path.relpath(f, base_dir) for f in all_files]
    unused_files = []

    for file_path in all_rel_files:
        # Skip entry points
        if file_path in entry_points:
            continue

        # Skip __init__.py files (they're implicitly used)
        if file_path.endswith('__init__.py'):
            continue

        # Check if this file is imported by anyone
        if file_path not in imported_by or len(imported_by[file_path]) == 0:
            unused_files.append(file_path)

    # Print results
    print("=== UNUSED FILES (not imported by any other file) ===\n")
    if unused_files:
        for f in sorted(unused_files):
            print(f"  - {f}")
    else:
        print("  (none found)")

    print("\n=== FILES AND THEIR IMPORTERS ===\n")
    for file_path in sorted(all_rel_files):
        if file_path in imported_by and imported_by[file_path]:
            print(f"{file_path}")
            print(f"  Imported by: {len(imported_by[file_path])} file(s)")
            for importer in sorted(imported_by[file_path]):
                print(f"    - {importer}")
            print()

    print("\n=== EXTERNAL ROOT DIRECTORY DEPENDENCIES ===\n")
    if external_deps:
        for module, files in sorted(external_deps.items()):
            print(f"{module}/")
            print(f"  Used by {len(files)} file(s):")
            for f in sorted(files):
                print(f"    - {f}")
            print()
    else:
        print("  (none found)")

    print("\n=== ENTRY POINTS ===\n")
    for ep in entry_points:
        exists = "✓" if os.path.exists(base_dir / ep) else "✗"
        print(f"  {exists} {ep}")

if __name__ == '__main__':
    main()
