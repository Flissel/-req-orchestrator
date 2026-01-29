#!/usr/bin/env python3
"""
Template Import Tool
====================

Creates a new project from a template.

Usage:
    python import_template.py <template_id> <project_name> [--output <path>]

Examples:
    python import_template.py 01-web-app my-webapp
    python import_template.py 02-api-service my-api --output ./projects/
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class TemplateImporter:
    """Handles template import and project initialization."""

    TEMPLATES_DIR = Path(__file__).parent.parent
    PLACEHOLDERS = {
        "{{PROJECT_NAME}}": "project_name",
        "{{TEMPLATE_NAME}}": "template_name",
        "{{TEMPLATE_ID}}": "template_id",
        "{{CREATED_AT}}": "created_at",
        "{{YEAR}}": "year",
    }

    def __init__(self, template_id: str, project_name: str, output_path: Optional[Path] = None):
        self.template_id = template_id
        self.project_name = project_name
        self.output_path = output_path or Path.cwd() / project_name
        self.template_dir = self.TEMPLATES_DIR / template_id
        self.meta = {}

    def validate(self) -> bool:
        """Validate template exists and project name is valid."""
        # Check template exists
        if not self.template_dir.exists():
            available = self._list_available_templates()
            print(f"❌ Template '{self.template_id}' not found.")
            print(f"Available templates: {', '.join(available)}")
            return False

        # Check meta.json exists
        meta_file = self.template_dir / "meta.json"
        if not meta_file.exists():
            print(f"❌ Template '{self.template_id}' is missing meta.json")
            return False

        # Load meta
        self.meta = json.loads(meta_file.read_text())

        # Validate project name
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", self.project_name):
            print(f"❌ Invalid project name: '{self.project_name}'")
            print("Project name must start with a letter and contain only letters, numbers, underscores, and hyphens.")
            return False

        # Check output doesn't exist
        if self.output_path.exists():
            print(f"❌ Output path already exists: {self.output_path}")
            return False

        return True

    def import_template(self) -> bool:
        """Copy template and replace placeholders."""
        try:
            template_source = self.template_dir / "template"

            if not template_source.exists():
                print(f"❌ Template source directory not found: {template_source}")
                return False

            # Copy template directory
            print(f"📁 Copying template to {self.output_path}...")
            shutil.copytree(template_source, self.output_path)

            # Get replacement values
            replacements = self._get_replacements()

            # Replace placeholders in all files
            print("🔄 Replacing placeholders...")
            self._replace_in_directory(self.output_path, replacements)

            # Copy requirements if they exist
            self._copy_requirements()

            # Generate README
            self._generate_readme(replacements)

            # Copy base files
            self._copy_base_files()

            print(f"\n✅ Project '{self.project_name}' created successfully!")
            print(f"📂 Location: {self.output_path}")
            self._print_next_steps()

            return True

        except Exception as e:
            print(f"❌ Error importing template: {e}")
            # Cleanup on failure
            if self.output_path.exists():
                shutil.rmtree(self.output_path)
            return False

    def _get_replacements(self) -> dict:
        """Get placeholder replacement values."""
        return {
            "{{PROJECT_NAME}}": self.project_name,
            "{{TEMPLATE_NAME}}": self.meta.get("name", self.template_id),
            "{{TEMPLATE_ID}}": self.template_id,
            "{{CREATED_AT}}": datetime.now().isoformat(),
            "{{YEAR}}": str(datetime.now().year),
            "{{INSTALL_COMMAND}}": self.meta.get("commands", {}).get("install", "npm install"),
            "{{DEV_COMMAND}}": self.meta.get("commands", {}).get("dev", "npm run dev"),
            "{{BUILD_COMMAND}}": self.meta.get("commands", {}).get("build", "npm run build"),
            "{{TEST_COMMAND}}": self.meta.get("commands", {}).get("test", "npm test"),
        }

    def _replace_in_directory(self, directory: Path, replacements: dict):
        """Replace placeholders in all text files."""
        text_extensions = {
            ".js", ".ts", ".jsx", ".tsx", ".json", ".md", ".txt",
            ".html", ".css", ".scss", ".yaml", ".yml", ".toml",
            ".py", ".c", ".cpp", ".h", ".hpp", ".sh", ".bat",
            ".sol", ".env.example", ".gitignore", ".editorconfig"
        }

        for file_path in directory.rglob("*"):
            if file_path.is_file():
                # Check if it's a text file
                if file_path.suffix in text_extensions or file_path.name in {
                    "Dockerfile", "Makefile", ".gitignore", ".env.example"
                }:
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        original = content
                        for placeholder, value in replacements.items():
                            content = content.replace(placeholder, value)
                        if content != original:
                            file_path.write_text(content, encoding="utf-8")
                    except UnicodeDecodeError:
                        pass  # Skip binary files

                # Rename files with placeholders
                if "{{PROJECT_NAME}}" in file_path.name:
                    new_name = file_path.name.replace("{{PROJECT_NAME}}", self.project_name)
                    file_path.rename(file_path.parent / new_name)

    def _copy_requirements(self):
        """Copy requirements from template docs."""
        req_source = self.template_dir / "docs" / "requirements"
        if req_source.exists():
            req_dest = self.output_path / "docs" / "requirements"
            shutil.copytree(req_source, req_dest)
            print("📋 Copied requirements documentation")

    def _generate_readme(self, replacements: dict):
        """Generate README from template."""
        readme_template = self.TEMPLATES_DIR / "_base" / "README.template.md"
        if readme_template.exists():
            content = readme_template.read_text()
            for placeholder, value in replacements.items():
                content = content.replace(placeholder, value)

            # Add tech stack list
            stack = self.meta.get("stack", [])
            tech_list = "\n".join(f"- {tech}" for tech in stack)
            content = content.replace("{{TECH_STACK_LIST}}", tech_list)

            # Add prerequisites
            prereqs = self.meta.get("pc_requirements", [])
            prereq_list = "\n".join(f"- {p}" for p in prereqs)
            content = content.replace("{{PREREQUISITES}}", prereq_list)

            # Add project structure
            structure = self._generate_structure_tree()
            content = content.replace("{{PROJECT_STRUCTURE}}", structure)

            # Default license
            content = content.replace("{{LICENSE}}", "MIT")

            readme_path = self.output_path / "README.md"
            readme_path.write_text(content)

    def _copy_base_files(self):
        """Copy base configuration files."""
        base_dir = self.TEMPLATES_DIR / "_base"

        # Copy .editorconfig
        editorconfig = base_dir / ".editorconfig"
        if editorconfig.exists():
            shutil.copy(editorconfig, self.output_path / ".editorconfig")

        # Copy .gitignore (rename from .gitignore.base)
        gitignore = base_dir / ".gitignore.base"
        if gitignore.exists():
            shutil.copy(gitignore, self.output_path / ".gitignore")

    def _generate_structure_tree(self) -> str:
        """Generate directory tree for README."""
        lines = []
        template_source = self.template_dir / "template"

        def add_tree(path: Path, prefix: str = ""):
            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
            for i, item in enumerate(items):
                if item.name.startswith("."):
                    continue
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{item.name}")
                if item.is_dir():
                    extension = "    " if is_last else "│   "
                    add_tree(item, prefix + extension)

        if template_source.exists():
            add_tree(template_source)

        return "\n".join(lines[:20])  # Limit to 20 lines

    def _list_available_templates(self) -> list:
        """List all available template IDs."""
        templates = []
        for path in self.TEMPLATES_DIR.iterdir():
            if path.is_dir() and path.name.startswith(tuple("0123456789")):
                templates.append(path.name)
        return sorted(templates)

    def _print_next_steps(self):
        """Print next steps for the user."""
        commands = self.meta.get("commands", {})
        print("\n📖 Next steps:")
        print(f"   cd {self.project_name}")
        if "install" in commands:
            print(f"   {commands['install']}")
        if "dev" in commands:
            print(f"   {commands['dev']}")


def list_templates():
    """List all available templates."""
    templates_dir = Path(__file__).parent.parent
    print("\n📦 Available Templates:\n")

    for path in sorted(templates_dir.iterdir()):
        if path.is_dir() and path.name.startswith(tuple("0123456789")):
            meta_file = path / "meta.json"
            if meta_file.exists():
                meta = json.loads(meta_file.read_text())
                name = meta.get("name", path.name)
                desc = meta.get("description", "")
                stack = ", ".join(meta.get("stack", [])[:3])
                print(f"  {path.name}")
                print(f"    Name: {name}")
                print(f"    Stack: {stack}")
                if desc:
                    print(f"    Description: {desc[:60]}...")
                print()


def main():
    parser = argparse.ArgumentParser(
        description="Import a template to create a new project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python import_template.py 01-web-app my-webapp
  python import_template.py 02-api-service my-api --output ./projects/
  python import_template.py --list
        """
    )

    parser.add_argument("template_id", nargs="?", help="Template ID (e.g., 01-web-app)")
    parser.add_argument("project_name", nargs="?", help="Name for the new project")
    parser.add_argument("--output", "-o", type=Path, help="Output directory")
    parser.add_argument("--list", "-l", action="store_true", help="List available templates")

    args = parser.parse_args()

    if args.list:
        list_templates()
        return 0

    if not args.template_id or not args.project_name:
        parser.print_help()
        return 1

    importer = TemplateImporter(args.template_id, args.project_name, args.output)

    if not importer.validate():
        return 1

    if not importer.import_template():
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())