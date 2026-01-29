"""
Import Spedition MVP feature documents as TechStack projects.

Parses markdown feature specifications and creates TechStack projects
with extracted requirements.

Usage:
    python scripts/import_spedition_features.py
"""
import re
import json
import requests
from pathlib import Path
from datetime import datetime

# Configuration
DOCS_PATH = Path(r"C:\code\Seb_drity_dreams\MVP_Spedition_Systemdesign\Unit-y-ai\Docs\Features\docs")
API_BASE = "http://localhost:8087/api/v1/techstack"


def parse_markdown_sections(content: str) -> dict:
    """
    Extract sections from markdown document.

    Returns dict mapping section titles to their content.
    """
    sections = {}
    current_section = None
    current_content = []

    for line in content.split('\n'):
        # Match ## headings (level 2)
        if line.startswith('## '):
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            current_section = line[3:].strip()
            current_content = []
        # Match ### headings (level 3) as subsections
        elif line.startswith('### '):
            current_content.append(line)
        else:
            current_content.append(line)

    # Don't forget the last section
    if current_section:
        sections[current_section] = '\n'.join(current_content)

    return sections


def extract_service_info(content: str) -> dict:
    """Extract service overview information."""
    info = {}

    # Extract service name
    name_match = re.search(r'\*\*Service Name\*\*:\s*(.+)', content)
    if name_match:
        info['service_name'] = name_match.group(1).strip()

    # Extract responsibility
    resp_match = re.search(r'\*\*Verantwortlichkeit\*\*:\s*(.+)', content)
    if resp_match:
        info['responsibility'] = resp_match.group(1).strip()

    # Extract architecture
    arch_match = re.search(r'\*\*Architektur\*\*:\s*(.+)', content)
    if arch_match:
        info['architecture'] = arch_match.group(1).strip()

    return info


def extract_requirements(sections: dict, source_file: str) -> list:
    """
    Extract requirements from parsed sections.

    Extracts from:
    - Funktionen (functional requirements)
    - API Endpoints Design (API specifications)
    - Datenmodell Design (data model requirements)
    - n8n Workflow Design (workflow requirements)
    """
    requirements = []
    req_id = 1

    # Extract from Funktionen section
    for key in sections:
        if 'Funktionen' in key or 'Functions' in key:
            content = sections[key]
            # Match bold items with descriptions: **Title**: Description
            for match in re.finditer(r'\*\*(.+?)\*\*:\s*(.+?)(?=\n|\*\*|$)', content, re.DOTALL):
                title = match.group(1).strip()
                text = match.group(2).strip()
                # Skip TODO items
                if title.startswith('//') or 'TODO' in title:
                    continue
                if len(text) > 10:  # Only meaningful descriptions
                    requirements.append({
                        "id": f"REQ-{req_id:03d}",
                        "title": title,
                        "text": text,
                        "category": "functional",
                        "source_section": key,
                        "source_file": source_file
                    })
                    req_id += 1

    # Extract from API Endpoints Design sections
    for key in sections:
        if 'Endpoints' in key or 'API' in key:
            content = sections[key]
            for match in re.finditer(r'\*\*(.+?)\*\*:\s*(.+?)(?=\n|\*\*|$)', content, re.DOTALL):
                title = match.group(1).strip()
                text = match.group(2).strip()
                # Skip TODO items
                if title.startswith('//') or 'TODO' in title:
                    continue
                if len(text) > 10:
                    requirements.append({
                        "id": f"REQ-{req_id:03d}",
                        "title": title,
                        "text": text,
                        "category": "api",
                        "source_section": key,
                        "source_file": source_file
                    })
                    req_id += 1

    # Extract from Datenmodell Design sections
    for key in sections:
        if 'Datenmodell' in key or 'Data Model' in key:
            content = sections[key]
            # Extract entity names and their fields
            entity_matches = re.finditer(r'###\s+(.+?)\n(.*?)(?=###|\Z)', content, re.DOTALL)
            for entity_match in entity_matches:
                entity_name = entity_match.group(1).strip()
                entity_content = entity_match.group(2)

                # Skip TODO sections
                if 'TODO' in entity_name:
                    continue

                # Extract field descriptions
                for field_match in re.finditer(r'\*\*(.+?)\*\*:\s*(.+?)(?=\n|\*\*|$)', entity_content):
                    field_title = field_match.group(1).strip()
                    field_desc = field_match.group(2).strip()
                    if field_title.startswith('//') or 'TODO' in field_title:
                        continue
                    if len(field_desc) > 10:
                        requirements.append({
                            "id": f"REQ-{req_id:03d}",
                            "title": f"{entity_name}: {field_title}",
                            "text": field_desc,
                            "category": "data_model",
                            "source_section": key,
                            "source_file": source_file
                        })
                        req_id += 1

    # Extract from n8n Workflow Design sections
    for key in sections:
        if 'Workflow' in key or 'n8n' in key:
            content = sections[key]
            # Extract workflow names and their steps
            workflow_matches = re.finditer(r'####\s+(.+?)\n(.*?)(?=####|\Z)', content, re.DOTALL)
            for wf_match in workflow_matches:
                wf_name = wf_match.group(1).strip()
                wf_content = wf_match.group(2)

                if 'TODO' in wf_name:
                    continue

                for step_match in re.finditer(r'\*\*(.+?)\*\*:\s*(.+?)(?=\n|\*\*|$)', wf_content):
                    step_title = step_match.group(1).strip()
                    step_desc = step_match.group(2).strip()
                    if step_title.startswith('//') or 'TODO' in step_title:
                        continue
                    if len(step_desc) > 10:
                        requirements.append({
                            "id": f"REQ-{req_id:03d}",
                            "title": f"{wf_name}: {step_title}",
                            "text": step_desc,
                            "category": "workflow",
                            "source_section": key,
                            "source_file": source_file
                        })
                        req_id += 1

    return requirements


def create_project(project_name: str, requirements: list):
    """Create TechStack project via API."""
    try:
        response = requests.post(
            f"{API_BASE}/create",
            json={
                "template_id": "02-api-service",
                "project_name": project_name,
                "requirements": requirements
            },
            timeout=30
        )
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}


def main():
    """Main import function."""
    print("=" * 60)
    print("Spedition Feature Documents -> TechStack Projects Importer")
    print("=" * 60)
    print(f"\nSource: {DOCS_PATH}")
    print(f"API: {API_BASE}")
    print()

    # Check if source path exists
    if not DOCS_PATH.exists():
        print(f"ERROR: Source path does not exist: {DOCS_PATH}")
        return []

    # Get all markdown files
    md_files = list(DOCS_PATH.glob("*.md"))
    print(f"Found {len(md_files)} markdown files\n")

    results = []
    total_requirements = 0
    successful_projects = 0

    for md_file in sorted(md_files):
        print(f"Processing: {md_file.name}")
        print("-" * 40)

        # Read and parse document
        content = md_file.read_text(encoding='utf-8')
        sections = parse_markdown_sections(content)

        # Extract service info
        service_info = {}
        if 'Service-Überblick' in sections:
            service_info = extract_service_info(sections['Service-Überblick'])
        elif 'Service Overview' in sections:
            service_info = extract_service_info(sections['Service Overview'])

        # Extract requirements
        requirements = extract_requirements(sections, md_file.name)
        total_requirements += len(requirements)

        # Determine project name
        # Use first line (# heading) or service name
        first_line = content.split('\n')[0]
        project_name = first_line.replace('#', '').strip()

        # Clean up project name
        if not project_name:
            project_name = md_file.stem.replace('_', ' ').title()

        print(f"  Service: {service_info.get('service_name', 'N/A')}")
        print(f"  Project Name: {project_name}")
        print(f"  Requirements Extracted: {len(requirements)}")

        # Category breakdown
        categories = {}
        for req in requirements:
            cat = req.get('category', 'other')
            categories[cat] = categories.get(cat, 0) + 1
        print(f"  Categories: {categories}")

        # Create project
        result = create_project(project_name, requirements)

        if result.get('success'):
            print("  Status: [OK] SUCCESS")
            print(f"  Path: {result.get('path')}")
            print(f"  Files Created: {result.get('files_created')}")
            successful_projects += 1
        else:
            print("  Status: [FAIL] FAILED")
            print(f"  Error: {result.get('error')}")

        results.append({
            "file": md_file.name,
            "project": project_name,
            "service_info": service_info,
            "requirements_count": len(requirements),
            "categories": categories,
            "result": result
        })
        print()

    # Summary
    print("=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    print(f"Documents Processed: {len(md_files)}")
    print(f"Projects Created: {successful_projects}")
    print(f"Total Requirements: {total_requirements}")
    print()

    # Save results to JSON
    results_file = Path(__file__).parent / "import_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "source_path": str(DOCS_PATH),
            "summary": {
                "documents_processed": len(md_files),
                "projects_created": successful_projects,
                "total_requirements": total_requirements
            },
            "results": results
        }, f, indent=2, ensure_ascii=False)
    print(f"Results saved to: {results_file}")

    return results


if __name__ == "__main__":
    main()
