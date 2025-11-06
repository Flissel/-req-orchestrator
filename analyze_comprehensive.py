#!/usr/bin/env python3
"""
Comprehensive analysis of arch_team file usage including:
- Static imports
- Dynamic imports (importlib)
- Test usage
- __init__.py exports
- Direct execution (__main__)
"""

import os
import re
from pathlib import Path
from collections import defaultdict

def find_all_python_files(directory):
    """Find all Python files recursively."""
    files = []
    for root, dirs, filenames in os.walk(directory):
        # Skip __pycache__
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for filename in filenames:
            if filename.endswith('.py'):
                files.append(os.path.join(root, filename))
    return sorted(files)

def extract_all_references(file_path):
    """Extract all references to arch_team modules."""
    references = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Static imports
        for match in re.finditer(r'from\s+(arch_team[\w.]*)\s+import', content, re.MULTILINE):
            references.add(match.group(1))

        for match in re.finditer(r'import\s+(arch_team[\w.]*)', content, re.MULTILINE):
            references.add(match.group(1))

        # Dynamic imports with importlib
        for match in re.finditer(r'importlib\.import_module\(["\']([^"\']+)["\']\)', content):
            references.add(match.group(1))

        # __main__ execution
        if 'if __name__ == "__main__"' in content or 'if __name__ == \'__main__\'' in content:
            references.add('__MAIN_EXECUTABLE__')

    except Exception as e:
        print(f"Error reading {file_path}: {e}")

    return references

def module_to_file(module_name, base_path):
    """Convert module name to possible file paths."""
    if not module_name.startswith('arch_team'):
        return []

    parts = module_name.split('.')
    paths = []

    # Direct file: arch_team.agents.chunk_miner -> arch_team/agents/chunk_miner.py
    file_path = '/'.join(parts) + '.py'
    paths.append(file_path)

    # Package: arch_team.agents -> arch_team/agents/__init__.py
    init_path = '/'.join(parts) + '/__init__.py'
    paths.append(init_path)

    return [p for p in paths if os.path.exists(base_path / p)]

def main():
    base_dir = Path('/home/user/-req-orchestrator')
    arch_team_dir = base_dir / 'arch_team'
    tests_dir = base_dir / 'tests'

    # Find all Python files in arch_team and tests
    arch_files = find_all_python_files(arch_team_dir)
    test_files = find_all_python_files(tests_dir)
    all_files = arch_files + test_files

    print("=== COMPREHENSIVE ARCH_TEAM USAGE ANALYSIS ===\n")
    print(f"Found {len(arch_files)} files in arch_team/")
    print(f"Found {len(test_files)} files in tests/")
    print()

    # Build reference map
    referenced_modules = defaultdict(set)  # module -> set of files that reference it
    executable_files = []

    for file_path in all_files:
        rel_path = os.path.relpath(file_path, base_dir)
        references = extract_all_references(file_path)

        if '__MAIN_EXECUTABLE__' in references:
            executable_files.append(rel_path)
            references.remove('__MAIN_EXECUTABLE__')

        for ref in references:
            # Convert module reference to file paths
            file_candidates = module_to_file(ref, base_dir)
            for candidate in file_candidates:
                referenced_modules[candidate].add(rel_path)

    # Find unreferenced files
    unreferenced = []
    potentially_unused = []

    for file_path in arch_files:
        rel_path = os.path.relpath(file_path, base_dir)

        # Skip __init__.py files (implicitly used)
        if rel_path.endswith('__init__.py'):
            continue

        # Check if it's an entry point
        if rel_path in executable_files:
            continue

        # Check if it's referenced
        if rel_path not in referenced_modules or len(referenced_modules[rel_path]) == 0:
            # Check if it's in dev_folder_ or distributed/
            if '/dev_folder_/' in rel_path or '/distributed/' in rel_path:
                potentially_unused.append(rel_path)
            else:
                unreferenced.append(rel_path)

    # Print results
    print("=== ENTRY POINTS (can be executed with __main__) ===\n")
    for f in sorted(executable_files):
        if f.startswith('arch_team/'):
            print(f"  ✓ {f}")
    print()

    print("=== UNREFERENCED FILES (likely unused) ===\n")
    if unreferenced:
        for f in sorted(unreferenced):
            print(f"  ! {f}")
            # Show what imports it has
            refs = extract_all_references(base_dir / f)
            arch_refs = [r for r in refs if r.startswith('arch_team')]
            if arch_refs:
                print(f"    (imports: {', '.join(sorted(arch_refs)[:3])}{'...' if len(arch_refs) > 3 else ''})")
    else:
        print("  (none found)")
    print()

    print("=== POTENTIALLY UNUSED (dev/experimental) ===\n")
    if potentially_unused:
        for f in sorted(potentially_unused):
            print(f"  ? {f}")
    else:
        print("  (none found)")
    print()

    print("=== USAGE SUMMARY ===\n")
    # Group by category
    categories = {
        'Used by production': [],
        'Used by tests only': [],
        'Unreferenced': unreferenced + potentially_unused
    }

    for file_path in arch_files:
        rel_path = os.path.relpath(file_path, base_dir)
        if rel_path.endswith('__init__.py') or rel_path in executable_files:
            continue

        if rel_path in unreferenced or rel_path in potentially_unused:
            continue

        refs = referenced_modules.get(rel_path, set())
        prod_refs = [r for r in refs if not r.startswith('tests/')]
        test_refs = [r for r in refs if r.startswith('tests/')]

        if prod_refs:
            categories['Used by production'].append(rel_path)
        elif test_refs:
            categories['Used by tests only'].append(rel_path)

    for category, files in categories.items():
        print(f"{category}: {len(files)} files")
    print()

    # Show detailed usage for key files
    print("=== DETAILED USAGE FOR KEY FILES ===\n")
    key_files = [
        'arch_team/agents/master_agent.py',
        'arch_team/autogen_tools/requirements_rag.py',
        'arch_team/tools/kg_tools.py',
        'arch_team/tools/mining_tools.py',
    ]

    for key_file in key_files:
        if key_file in referenced_modules:
            refs = referenced_modules[key_file]
            print(f"{key_file}")
            print(f"  Used by {len(refs)} file(s):")
            for ref in sorted(refs):
                print(f"    - {ref}")
            print()

if __name__ == '__main__':
    main()
