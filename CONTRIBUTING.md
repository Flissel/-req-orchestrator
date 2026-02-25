# Contributing to req-orchestrator

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.10+
- Node.js 20+
- Qdrant (optional, for vector search / RAG features)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_ORG/req-orchestrator.git
cd req-orchestrator

# Create a Python virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install Python dependencies (with dev tools)
pip install -e ".[dev]"

# Install frontend dependencies
npm ci

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Running Locally

```bash
# Backend (FastAPI, port 8087)
uvicorn backend.main:fastapi_app --reload --port 8087

# Frontend (Vite, port 3000)
npm run dev

# Arch Team agent service (port 8000)
python -m arch_team.service
```

## Code Style

We use **black** for formatting and **ruff** for linting:

```bash
# Format code
black .

# Check linting
ruff check .

# Auto-fix lint issues
ruff check --fix .
```

Configuration is in `pyproject.toml` (line-length: 100, target: Python 3.10+).

## Testing

### Unit Tests

```bash
pytest tests/ -v
```

### End-to-End Tests (Playwright)

```bash
# Install Playwright browsers (first time)
npx playwright install

# Run E2E tests
npx playwright test
```

### Mock Mode

Set `MOCK_MODE=true` in `.env` to run without LLM API calls (uses heuristic evaluation).

## Pull Request Process

1. Fork the repository and create a feature branch
2. Make your changes with tests where applicable
3. Run `black .` and `ruff check .` to ensure code style
4. Run `pytest tests/` to verify tests pass
5. Submit a pull request with a clear description of your changes

## Project Structure

See [docs/architecture/](docs/architecture/) for detailed architecture documentation.

```
backend/          # FastAPI REST API + services
arch_team/        # Multi-agent system (AutoGen)
mcp_server/       # MCP server for Claude CLI
src/              # React + Vite frontend
config/           # Prompts & evaluation criteria
tests/            # Pytest + Playwright tests
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
