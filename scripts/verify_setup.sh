#!/bin/bash
# Setup Verification Script for Unix/Linux/Mac
# Checks if all required services are running

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERROR_COUNT=0

print_header() {
    echo ""
    echo "======================================================================"
    echo "  $1"
    echo "======================================================================"
    echo ""
}

print_ok() {
    echo -e "${GREEN}✓${NC} $1"
}

print_fail() {
    echo -e "${RED}✗${NC} $1"
    ((ERROR_COUNT++))
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

print_header "arch_team Setup Verification"

# 1. Check .env file
print_header "1. Environment Configuration"

if [ -f ".env" ]; then
    print_ok ".env file exists"

    # Check critical env vars
    if grep -q "OPENAI_API_KEY=sk-" .env; then
        print_ok "OPENAI_API_KEY is set"
    elif grep -q "MOCK_MODE=true" .env; then
        print_ok "MOCK_MODE is enabled (no API key needed)"
    else
        print_fail "OPENAI_API_KEY not set and MOCK_MODE not enabled"
        echo "  → Edit .env and add your OpenAI API key"
    fi

    # Check for new standardized port variables
    if grep -qE "^(QDRANT_PORT|BACKEND_PORT|ARCH_TEAM_PORT)" .env; then
        print_ok "Port configuration variables detected"
    else
        print_info "Using default port configuration"
    fi
else
    print_fail ".env file not found"
    echo "  → Run: cp .env.example .env"
fi

# 2. Check dependencies
print_header "2. Dependencies"

if command -v python3 &> /dev/null || command -v python &> /dev/null; then
    print_ok "Python is installed"
else
    print_fail "Python not found"
fi

if command -v node &> /dev/null; then
    print_ok "Node.js is installed ($(node --version))"
else
    print_fail "Node.js not found"
fi

if [ -d "node_modules" ]; then
    print_ok "Node.js packages installed"
else
    print_fail "node_modules not found"
    echo "  → Run: npm install"
fi

# 3. Check services
print_header "3. Required Services"

# Load environment variables with defaults
QDRANT_PORT=${QDRANT_PORT:-6333}
ARCH_TEAM_PORT=${ARCH_TEAM_PORT:-8000}
BACKEND_PORT=${BACKEND_PORT:-8087}

# Check Qdrant
if curl -s http://localhost:${QDRANT_PORT}/collections > /dev/null 2>&1; then
    COLLECTIONS=$(curl -s http://localhost:${QDRANT_PORT}/collections | grep -o '"name"' | wc -l)
    print_ok "Qdrant is running on port ${QDRANT_PORT} ($COLLECTIONS collections)"
else
    print_fail "Qdrant not reachable on port ${QDRANT_PORT}"
    echo "  → Run: docker-compose -f docker-compose.qdrant.yml up -d"
fi

# Check arch_team service
if curl -s http://localhost:${ARCH_TEAM_PORT}/health > /dev/null 2>&1; then
    print_ok "arch_team service is running on port ${ARCH_TEAM_PORT}"
else
    print_fail "arch_team service not reachable on port ${ARCH_TEAM_PORT}"
    echo "  → Run: python -m arch_team.service"
fi

# Check SQLite database
if [ -f "data/app.db" ]; then
    print_ok "SQLite database exists"
else
    print_info "SQLite database not found (will be created on first run)"
fi

# 4. Optional services
print_header "4. Optional Services"

if curl -s http://localhost:${BACKEND_PORT}/health > /dev/null 2>&1; then
    print_ok "FastAPI backend is running on port ${BACKEND_PORT}"
else
    print_info "FastAPI backend not running (optional)"
    echo "  → Run: python -m uvicorn backend.main:fastapi_app --port ${BACKEND_PORT}"
fi

# Summary
print_header "Summary"

if [ $ERROR_COUNT -eq 0 ]; then
    echo -e "${GREEN}✓ All critical checks passed!${NC}"
    echo ""
    echo "You can start the React frontend:"
    echo "  npm run dev"
    echo ""
    echo "Access the UI at: http://localhost:3000"
else
    echo -e "${RED}✗ $ERROR_COUNT check(s) failed. Please fix the issues above.${NC}"
    echo ""
    echo "Quick start commands:"
    echo "  1. cp .env.example .env  # Then edit .env to add OPENAI_API_KEY"
    echo "  2. pip install -r requirements.txt"
    echo "  3. npm install"
    echo "  4. docker-compose -f docker-compose.qdrant.yml up -d"
    echo "  5. python -m arch_team.service"
    echo "  6. npm run dev"
fi

echo ""
exit $ERROR_COUNT
