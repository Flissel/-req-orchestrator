#!/usr/bin/env python3
"""
Requirements Manager
====================

Manages requirements persistence, loading, and export.

Usage:
    python requirements_manager.py save <template_id> <requirements_file>
    python requirements_manager.py load <template_id>
    python requirements_manager.py export <template_id> --format json|md
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class RequirementType(str, Enum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non-functional"
    CONSTRAINT = "constraint"
    INTERFACE = "interface"


class RequirementPriority(str, Enum):
    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    WONT = "wont"


class RequirementStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    TESTED = "tested"
    DEPRECATED = "deprecated"


@dataclass
class Trace:
    type: str  # implements, tests, depends_on, conflicts_with, refines, derives_from
    target: str
    description: str = ""


@dataclass
class ImplementationHint:
    files: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    libraries: list[str] = field(default_factory=list)
    code_snippets: list[dict] = field(default_factory=list)


@dataclass
class RequirementMetadata:
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "system"
    source: str = "generated"
    validation_score: float = 0.0
    enhancement_version: int = 0
    kg_node_id: str = ""


@dataclass
class Requirement:
    id: str
    text: str
    type: RequirementType
    template_id: str
    status: RequirementStatus = RequirementStatus.DRAFT
    priority: RequirementPriority = RequirementPriority.SHOULD
    category: str = ""
    component: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    traces: list[Trace] = field(default_factory=list)
    implementation_hints: Optional[ImplementationHint] = None
    metadata: RequirementMetadata = field(default_factory=RequirementMetadata)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["type"] = self.type.value
        data["status"] = self.status.value
        data["priority"] = self.priority.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Requirement":
        """Create from dictionary."""
        data["type"] = RequirementType(data["type"])
        data["status"] = RequirementStatus(data.get("status", "draft"))
        data["priority"] = RequirementPriority(data.get("priority", "should"))

        # Handle nested objects
        if "traces" in data and data["traces"]:
            data["traces"] = [Trace(**t) if isinstance(t, dict) else t for t in data["traces"]]

        if "implementation_hints" in data and data["implementation_hints"]:
            data["implementation_hints"] = ImplementationHint(**data["implementation_hints"])

        if "metadata" in data and data["metadata"]:
            data["metadata"] = RequirementMetadata(**data["metadata"])

        return cls(**data)


class RequirementsManager:
    """Manages requirements for templates."""

    TEMPLATES_DIR = Path(__file__).parent.parent

    def __init__(self, template_id: str):
        self.template_id = template_id
        self.template_dir = self.TEMPLATES_DIR / template_id
        self.requirements_dir = self.template_dir / "docs" / "requirements"

    def save(self, requirements: list[Requirement]) -> Path:
        """
        Save requirements to the template's docs/requirements directory.

        Creates:
        - docs/requirements/functional/*.req.json
        - docs/requirements/non-functional/*.req.json
        - docs/requirements/manifest.json
        """
        # Create directories
        self.requirements_dir.mkdir(parents=True, exist_ok=True)

        for req_type in RequirementType:
            type_dir = self.requirements_dir / req_type.value.replace("-", "_")
            type_dir.mkdir(exist_ok=True)

        # Save requirements by type
        saved_count = 0
        for req in requirements:
            # Update metadata
            now = datetime.now().isoformat()
            if not req.metadata.created_at:
                req.metadata.created_at = now
            req.metadata.updated_at = now

            # Determine directory
            type_dir = self.requirements_dir / req.type.value.replace("-", "_")

            # Save file
            file_path = type_dir / f"{req.id}.req.json"
            file_path.write_text(json.dumps(req.to_dict(), indent=2, ensure_ascii=False))
            saved_count += 1

        # Create manifest
        manifest = {
            "template_id": self.template_id,
            "total_requirements": len(requirements),
            "by_type": {},
            "by_priority": {},
            "by_status": {},
            "requirements": [r.id for r in requirements],
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        }

        # Count by type
        for req_type in RequirementType:
            count = len([r for r in requirements if r.type == req_type])
            if count > 0:
                manifest["by_type"][req_type.value] = count

        # Count by priority
        for priority in RequirementPriority:
            count = len([r for r in requirements if r.priority == priority])
            if count > 0:
                manifest["by_priority"][priority.value] = count

        # Count by status
        for status in RequirementStatus:
            count = len([r for r in requirements if r.status == status])
            if count > 0:
                manifest["by_status"][status.value] = count

        manifest_path = self.requirements_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

        print(f"✅ Saved {saved_count} requirements to {self.requirements_dir}")
        return self.requirements_dir

    def load(self) -> list[Requirement]:
        """
        Load all requirements for the template.

        Returns list of Requirement objects.
        """
        requirements = []

        if not self.requirements_dir.exists():
            print(f"⚠️ No requirements found for template '{self.template_id}'")
            return requirements

        # Load all .req.json files
        for req_file in self.requirements_dir.rglob("*.req.json"):
            try:
                data = json.loads(req_file.read_text(encoding="utf-8"))
                req = Requirement.from_dict(data)
                requirements.append(req)
            except Exception as e:
                print(f"⚠️ Error loading {req_file}: {e}")

        print(f"📋 Loaded {len(requirements)} requirements from {self.template_id}")
        return requirements

    def load_manifest(self) -> Optional[dict]:
        """Load the requirements manifest."""
        manifest_path = self.requirements_dir / "manifest.json"
        if manifest_path.exists():
            return json.loads(manifest_path.read_text())
        return None

    def export_json(self, output_path: Optional[Path] = None) -> Path:
        """Export all requirements as a single JSON file."""
        requirements = self.load()
        data = {
            "template_id": self.template_id,
            "exported_at": datetime.now().isoformat(),
            "requirements": [r.to_dict() for r in requirements]
        }

        output = output_path or Path(f"{self.template_id}_requirements.json")
        output.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"📤 Exported to {output}")
        return output

    def export_markdown(self, output_path: Optional[Path] = None) -> Path:
        """Export requirements as Markdown documentation."""
        requirements = self.load()

        lines = [
            f"# Requirements: {self.template_id}",
            "",
            f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Summary",
            "",
            f"- **Total Requirements:** {len(requirements)}",
        ]

        # Group by type
        for req_type in RequirementType:
            type_reqs = [r for r in requirements if r.type == req_type]
            if type_reqs:
                type_name = req_type.value.replace("-", " ").title()
                lines.append(f"- **{type_name}:** {len(type_reqs)}")

        lines.extend(["", "---", ""])

        # Requirements by type
        for req_type in RequirementType:
            type_reqs = [r for r in requirements if r.type == req_type]
            if not type_reqs:
                continue

            type_name = req_type.value.replace("-", " ").title()
            lines.extend([f"## {type_name} Requirements", ""])

            for req in sorted(type_reqs, key=lambda r: r.id):
                priority_badge = {
                    RequirementPriority.MUST: "🔴",
                    RequirementPriority.SHOULD: "🟡",
                    RequirementPriority.COULD: "🟢",
                    RequirementPriority.WONT: "⚪"
                }.get(req.priority, "")

                lines.extend([
                    f"### {req.id} {priority_badge}",
                    "",
                    f"> **Priority:** {req.priority.value.upper()} | "
                    f"**Status:** {req.status.value} | "
                    f"**Category:** {req.category or 'N/A'}",
                    "",
                    req.text,
                    ""
                ])

                if req.acceptance_criteria:
                    lines.append("**Acceptance Criteria:**")
                    for ac in req.acceptance_criteria:
                        lines.append(f"- [ ] {ac}")
                    lines.append("")

                if req.implementation_hints:
                    if req.implementation_hints.files:
                        lines.append(f"**Files:** `{', '.join(req.implementation_hints.files)}`")
                    if req.implementation_hints.libraries:
                        lines.append(f"**Libraries:** {', '.join(req.implementation_hints.libraries)}")
                    lines.append("")

                if req.tags:
                    lines.append(f"**Tags:** {', '.join(f'`{t}`' for t in req.tags)}")
                    lines.append("")

                lines.append("---")
                lines.append("")

        output = output_path or Path(f"{self.template_id}_requirements.md")
        output.write_text("\n".join(lines), encoding="utf-8")
        print(f"📤 Exported to {output}")
        return output

    def get_by_id(self, requirement_id: str) -> Optional[Requirement]:
        """Get a specific requirement by ID."""
        requirements = self.load()
        for req in requirements:
            if req.id == requirement_id:
                return req
        return None

    def get_by_type(self, req_type: RequirementType) -> list[Requirement]:
        """Get all requirements of a specific type."""
        requirements = self.load()
        return [r for r in requirements if r.type == req_type]

    def get_by_status(self, status: RequirementStatus) -> list[Requirement]:
        """Get all requirements with a specific status."""
        requirements = self.load()
        return [r for r in requirements if r.status == status]

    def update_status(self, requirement_id: str, new_status: RequirementStatus) -> bool:
        """Update the status of a requirement."""
        requirements = self.load()
        for i, req in enumerate(requirements):
            if req.id == requirement_id:
                req.status = new_status
                req.metadata.updated_at = datetime.now().isoformat()
                self.save(requirements)
                print(f"✅ Updated {requirement_id} status to {new_status.value}")
                return True
        print(f"❌ Requirement {requirement_id} not found")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Manage requirements for templates",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Save command
    save_parser = subparsers.add_parser("save", help="Save requirements from JSON file")
    save_parser.add_argument("template_id", help="Template ID")
    save_parser.add_argument("input_file", type=Path, help="Input JSON file")

    # Load command
    load_parser = subparsers.add_parser("load", help="Load and display requirements")
    load_parser.add_argument("template_id", help="Template ID")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export requirements")
    export_parser.add_argument("template_id", help="Template ID")
    export_parser.add_argument("--format", "-f", choices=["json", "md"], default="json")
    export_parser.add_argument("--output", "-o", type=Path, help="Output file")

    # Status command
    status_parser = subparsers.add_parser("status", help="Update requirement status")
    status_parser.add_argument("template_id", help="Template ID")
    status_parser.add_argument("requirement_id", help="Requirement ID")
    status_parser.add_argument("new_status", choices=[s.value for s in RequirementStatus])

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    manager = RequirementsManager(args.template_id)

    if args.command == "save":
        if not args.input_file.exists():
            print(f"❌ Input file not found: {args.input_file}")
            return 1

        data = json.loads(args.input_file.read_text())
        requirements = []

        # Handle both list and dict with "requirements" key
        req_list = data if isinstance(data, list) else data.get("requirements", [])

        for item in req_list:
            req = Requirement.from_dict(item)
            requirements.append(req)

        manager.save(requirements)

    elif args.command == "load":
        requirements = manager.load()
        for req in requirements:
            print(f"  {req.id}: {req.text[:50]}... [{req.type.value}]")

    elif args.command == "export":
        if args.format == "json":
            manager.export_json(args.output)
        else:
            manager.export_markdown(args.output)

    elif args.command == "status":
        manager.update_status(args.requirement_id, RequirementStatus(args.new_status))

    return 0


if __name__ == "__main__":
    sys.exit(main())