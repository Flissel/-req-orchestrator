# 📋 CLI Tool - Projekt-Fragebogen
## Template: 09-cli-tool (Python + Typer + Rich)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **Tool Name** | |
| **Command Name** | $ mytool |
| **Zweck** | Was macht das Tool? |

---

## A. TOOL-TYP & ZWECK

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| A1 | Was macht das Tool? | Datei-Verarbeitung, API-Client, Automation | |
| A2 | Zielgruppe? | Entwickler, DevOps, End-User | |
| A3 | Interaktiv? | Prompts, Wizards | |
| A4 | Daemon Mode? | Hintergrundprozess | |

---

## B. COMMANDS & STRUKTUR

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| B1 | Haupt-Commands? | init, run, deploy, etc. | |
| B2 | Subcommands? | mytool config get/set | |
| B3 | Global Options? | --verbose, --config | |
| B4 | Positional Arguments? | mytool process FILE | |

---

## C. INPUT/OUTPUT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| C1 | Input-Typen? | [ ] Files [ ] Stdin [ ] API [ ] Database | |
| C2 | Output-Format? | [ ] Text [ ] JSON [ ] Table [ ] YAML | |
| C3 | Progress Anzeige? | [ ] Spinner [ ] Progress Bar [ ] Logs | |
| C4 | Colored Output? | [ ] Ja [ ] Nein [ ] Optional (--no-color) | |

---

## D. KONFIGURATION

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D1 | Config File? | [ ] Keins [ ] TOML [ ] YAML [ ] JSON | |
| D2 | Config Location? | [ ] ~/.config/tool/ [ ] ./.toolrc [ ] Both | |
| D3 | Environment Variables? | TOOL_API_KEY, etc. | |
| D4 | Secrets? | [ ] Keyring [ ] .env [ ] Environment | |

---

## E. TECH-STACK ENTSCHEIDUNGEN

### CLI Framework

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E1 | CLI Framework? | [ ] Typer (empfohlen) [ ] Click [ ] argparse | |
| E2 | Rich Output? | [ ] Rich (empfohlen) [ ] colorama [ ] Plain | |
| E3 | Prompts? | [ ] Rich Prompt [ ] questionary [ ] None | |

### Dependencies

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E4 | HTTP Client? | [ ] httpx (empfohlen) [ ] requests [ ] aiohttp | |
| E5 | File Handling? | [ ] pathlib [ ] shutil [ ] watchdog | |
| E6 | Data Validation? | [ ] Pydantic [ ] attrs [ ] None | |

### Packaging

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E7 | Package Manager? | [ ] Poetry (empfohlen) [ ] pip + setup.py [ ] Hatch | |
| E8 | Distribution? | [ ] PyPI [ ] GitHub Releases [ ] Both | |
| E9 | Entry Point? | [ ] Console Script [ ] __main__.py | |

---

## F. FEATURES

| # | Frage | Benötigt? |
|---|-------|-----------|
| F1 | Tab Completion? | [ ] Ja [ ] Nein |
| F2 | Auto-Update Check? | [ ] Ja [ ] Nein |
| F3 | Logging to File? | [ ] Ja [ ] Nein |
| F4 | Plugin System? | [ ] Ja [ ] Nein |
| F5 | Shell Integration? | [ ] Ja [ ] Nein |
| F6 | Man Pages? | [ ] Ja [ ] Nein |

---

## G. TESTING

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| G1 | Test Framework? | [ ] pytest (default) [ ] unittest | |
| G2 | CLI Testing? | [ ] CliRunner (Typer) [ ] subprocess | |
| G3 | Coverage? | [ ] Ja [ ] Nein | |
| G4 | Fixtures? | Mocked files, APIs | |

---

## H. DOKUMENTATION

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| H1 | --help Generated? | [ ] Ja (Typer auto) | |
| H2 | README? | [ ] Ja [ ] Nein | |
| H3 | Usage Examples? | [ ] Inline [ ] Docs Site | |
| H4 | Changelog? | [ ] Ja [ ] Nein | |

---

## I. CI/CD

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| I1 | CI Pipeline? | [ ] GitHub Actions [ ] GitLab CI | |
| I2 | Auto-Release? | [ ] Ja (on tag) [ ] Manual | |
| I3 | PyPI Publish? | [ ] Ja [ ] Nein | |
| I4 | Binary Builds? | [ ] Nein [ ] PyInstaller [ ] Nuitka | |

---

# 📊 GENERIERUNGSOPTIONEN

- [ ] Main CLI App
- [ ] Command Modules
- [ ] Config Management
- [ ] Rich Output Utils
- [ ] Tests
- [ ] pyproject.toml
- [ ] README
- [ ] GitHub Actions

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "09-cli-tool",
  "cli": {
    "framework": "Typer",
    "output": "Rich",
    "prompts": "questionary"
  },
  "python": {
    "version": "3.12+",
    "packaging": "Poetry",
    "testing": "pytest"
  },
  "distribution": {
    "package": "PyPI",
    "binary": "PyInstaller (optional)"
  }
}
```
