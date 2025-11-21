#!/bin/bash
# Complete Test Suite Runner for Requirements Engineering System
# Run all tests: backend unit, integration, and E2E

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Requirements Engineering System - Complete Test Suite         ║"
echo "╚════════════════════════════════════════════════════════════════╝"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run test section
run_test_section() {
    local name=$1
    local command=$2

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  $name"
    echo "═══════════════════════════════════════════════════════════════"

    if eval "$command"; then
        echo -e "${GREEN}✓ $name PASSED${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ $name FAILED${NC}"
        ((TESTS_FAILED++))
    fi
}

# Ensure we're in project root
cd "$(dirname "$0")/.."

# Check if services are running
echo ""
echo "Checking if required services are running..."

if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Warning: arch_team service (port 8000) not running${NC}"
    echo "  Start with: python -m arch_team.service"
fi

if ! curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Warning: React frontend (port 3000) not running${NC}"
    echo "  Start with: npm run dev"
fi

if ! curl -s http://localhost:6401/collections > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Warning: Qdrant (port 6401) not running${NC}"
    echo "  Start with: docker-compose -f docker-compose.qdrant.yml up -d"
fi

# Test Section 1: Backend Unit Tests
run_test_section "Backend Unit Tests" \
    "pytest tests/backend/ -v --tb=short"

# Test Section 2: Service Layer Tests
run_test_section "Service Layer Tests" \
    "pytest tests/services/ -v --tb=short"

# Test Section 3: arch_team Integration Tests
run_test_section "arch_team Integration Tests" \
    "pytest tests/arch_team/ -v --tb=short -k 'not e2e'"

# Test Section 4: Parity Tests (v1/v2 compatibility)
run_test_section "Parity Tests" \
    "pytest tests/parity/ -v --tb=short"

# Test Section 5: E2E Playwright Tests
if command -v npx &> /dev/null; then
    run_test_section "E2E Smoke Tests" \
        "npx playwright test tests/e2e/01-smoke-test.spec.ts --reporter=list"

    run_test_section "E2E Mining Workflow" \
        "npx playwright test tests/e2e/02-mining-workflow.spec.ts --reporter=list"

    run_test_section "E2E KG Visualization" \
        "npx playwright test tests/e2e/03-kg-visualization.spec.ts --reporter=list"
else
    echo -e "${YELLOW}⚠ Playwright not found - skipping E2E tests${NC}"
fi

# Summary
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                     TEST SUITE SUMMARY                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo -e "  ${GREEN}Passed:${NC} $TESTS_PASSED"
echo -e "  ${RED}Failed:${NC} $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All test suites passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Check output above for details.${NC}"
    exit 1
fi
