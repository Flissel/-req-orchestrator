# Setup Verification Scripts

This directory contains scripts to verify that your arch_team environment is properly configured and all required services are running.

## Available Scripts

### 1. `verify_setup.py` (Python - Cross-platform, Detailed)

**Most comprehensive** - Provides detailed checks and diagnostic information.

**Usage:**
```bash
# Basic check (required services only)
python scripts/verify_setup.py

# Full check (includes optional services)
python scripts/verify_setup.py --full
```

**Requires:**
- Python 3.x
- `requests` package (installed via `pip install -r requirements.txt`)

**Checks:**
- ✓ .env file exists and is properly configured
- ✓ Python packages installed
- ✓ Node.js packages installed
- ✓ Qdrant connection (with collection count)
- ✓ arch_team Flask service
- ✓ SQLite database
- ✓ FastAPI v2 backend (with `--full` flag)

**Output:**
- Colored status indicators (✓/✗)
- Detailed error messages
- Suggested fix commands
- Service information (collections, tables, etc.)

---

### 2. `verify_setup.bat` (Windows Batch Script)

**Quick check for Windows users** - Minimal dependencies.

**Usage:**
```cmd
scripts\verify_setup.bat
```

**Requires:**
- Windows command prompt
- `curl` (included in Windows 10+)

**Checks:**
- ✓ .env file exists
- ✓ Python/Node.js in PATH
- ✓ node_modules exists
- ✓ Qdrant reachable on port 6401
- ✓ arch_team service reachable on port 8000

**Output:**
- Simple [OK]/[FAIL] status
- Quick start commands if checks fail
- Exit code (0 = success, >0 = failures)

---

### 3. `verify_setup.sh` (Unix/Linux/Mac Shell Script)

**Quick check for Unix-like systems** - Minimal dependencies.

**Usage:**
```bash
# Make executable (first time only)
chmod +x scripts/verify_setup.sh

# Run
./scripts/verify_setup.sh
```

**Requires:**
- Bash shell
- `curl` command

**Checks:**
- ✓ .env file exists and key variables are set
- ✓ Python/Node.js installed
- ✓ node_modules exists
- ✓ Qdrant running (port 6401)
- ✓ arch_team service running (port 8000)
- ✓ SQLite database exists
- ℹ FastAPI v2 backend (optional)

**Output:**
- Colored status indicators (✓/✗/ℹ)
- Quick start commands if checks fail
- Exit code (0 = success, >0 = failures)

---

## What Each Script Checks

| Check | Python | Batch | Shell | Description |
|-------|--------|-------|-------|-------------|
| .env file | ✓ | ✓ | ✓ | Verifies configuration file exists |
| .env content | ✓ | ✗ | ✓ | Validates OPENAI_API_KEY, QDRANT_PORT |
| Python packages | ✓ | ✗ | ✗ | Checks required packages installed |
| Node.js packages | ✓ | ✓ | ✓ | Verifies node_modules exists |
| Qdrant service | ✓ | ✓ | ✓ | Tests connection and lists collections |
| arch_team service | ✓ | ✓ | ✓ | Verifies Flask API is running |
| SQLite database | ✓ | ✗ | ✓ | Checks database and tables |
| FastAPI v2 | ✓ | ✗ | ✓ | Optional backend service |

---

## When to Use Which Script

**Use `verify_setup.py` when:**
- You want detailed diagnostic information
- You need to troubleshoot configuration issues
- You want to verify database contents
- You're setting up for the first time

**Use `verify_setup.bat` when:**
- You're on Windows and want a quick check
- You don't want to install Python dependencies
- You just need to verify services are running

**Use `verify_setup.sh` when:**
- You're on Unix/Linux/Mac and want a quick check
- You want colored output in terminal
- You need a lightweight verification script

---

## Common Issues and Fixes

### Issue: "Qdrant not reachable"

**Fix:**
```bash
docker-compose -f docker-compose.qdrant.yml up -d
```

**Verify:**
```bash
curl http://localhost:6401/collections
```

---

### Issue: "arch_team service not reachable"

**Fix:**
```bash
python -m arch_team.service
```

**Verify:**
```bash
curl http://localhost:8000/health
```

---

### Issue: ".env file not found"

**Fix:**
```bash
cp .env.example .env
# Then edit .env and add your OPENAI_API_KEY
```

---

### Issue: "QDRANT_PORT incorrect"

**Fix:**
Edit `.env` and set:
```bash
QDRANT_PORT=6401
```

---

### Issue: "node_modules not found"

**Fix:**
```bash
npm install
```

---

### Issue: "Python packages missing"

**Fix:**
```bash
pip install -r requirements.txt
```

---

## Exit Codes

All scripts return an exit code:
- **0** = All checks passed
- **>0** = Number of failed checks

**Example usage in CI/CD:**
```bash
./scripts/verify_setup.sh || exit 1
```

---

## Integration with Startup

You can add these checks to your startup scripts:

**Windows (startup.bat):**
```batch
@echo off
call scripts\verify_setup.bat
if %ERRORLEVEL% NEQ 0 (
    echo Please fix the issues above before starting services
    pause
    exit /b 1
)
python -m arch_team.service
```

**Unix (startup.sh):**
```bash
#!/bin/bash
./scripts/verify_setup.sh || exit 1
python -m arch_team.service
```

---

## Contributing

When adding new services or dependencies, please update all three verification scripts to maintain consistency.

**Required updates:**
1. Add new checks to `verify_setup.py`
2. Add basic connectivity test to `.bat` and `.sh`
3. Update this README with new check descriptions
4. Update the comparison table
