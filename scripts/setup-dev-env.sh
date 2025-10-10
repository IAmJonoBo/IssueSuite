#!/usr/bin/env bash
# Setup script for IssueSuite development environment
#
# This script:
# 1. Installs Git hooks for pre-commit validation
# 2. Validates Python environment and dependencies
# 3. Checks lockfile synchronization
# 4. Verifies tool versions match CI

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
	echo -e "${GREEN}[setup]${NC} $*"
}

warn() {
	echo -e "${YELLOW}[setup]${NC} $*"
}

error() {
	echo -e "${RED}[setup]${NC} $*" >&2
}

echo "Setting up IssueSuite development environment..."
echo ""

# 1. Install Git hooks
if [ -d "${PROJECT_ROOT}/.git" ]; then
	log "Installing Git hooks..."
	git config core.hooksPath "${PROJECT_ROOT}/.githooks"
	chmod +x "${PROJECT_ROOT}/.githooks"/* 2>/dev/null || true
	log "✓ Git hooks configured"
else
	warn "⚠ Not a Git repository, skipping hook setup"
fi

# 2. Validate Python environment
log "Checking Python environment..."

if ! command -v python >/dev/null 2>&1; then
	error "✗ Python not found in PATH"
	exit 1
fi

PYTHON_VERSION=$(python --version | awk '{print $2}')
log "✓ Python ${PYTHON_VERSION} found"

# Check if IssueSuite is installed
if python -c "import issuesuite" 2>/dev/null; then
	log "✓ IssueSuite package installed"
else
	warn "⚠ IssueSuite not installed"
	echo "  Run: pip install -e .[dev,all]"
fi

# 3. Check lockfile synchronization
if command -v uv >/dev/null 2>&1; then
	log "Checking lockfile synchronization..."
	if "${PROJECT_ROOT}/scripts/refresh-deps.sh" --check 2>/dev/null; then
		log "✓ Lockfiles synchronized"
	else
		warn "⚠ Lockfiles out of sync"
		echo "  Run: ./scripts/refresh-deps.sh"
	fi
else
	warn "⚠ uv not installed (optional but recommended)"
	echo "  Install: pip install uv"
fi

# 4. Validate tool versions
log "Checking development tools..."

check_tool() {
	local tool=$1
	local min_version=$2

	if command -v "${tool}" >/dev/null 2>&1; then
		log "✓ ${tool} available"
		return 0
	else
		warn "⚠ ${tool} not found (required for development)"
		return 1
	fi
}

TOOLS_OK=true
check_tool "ruff" "" || TOOLS_OK=false
check_tool "mypy" "" || TOOLS_OK=false
check_tool "pytest" "" || TOOLS_OK=false
check_tool "nox" "" || TOOLS_OK=false

if [ "$TOOLS_OK" = false ]; then
	echo ""
	echo "Install missing tools with:"
	echo "  pip install -e .[dev,all]"
fi

# 5. Validate Node.js environment (for docs)
if command -v node >/dev/null 2>&1; then
	NODE_VERSION=$(node --version)
	log "✓ Node.js ${NODE_VERSION} available"

	if [ -f "${PROJECT_ROOT}/docs/starlight/package.json" ]; then
		if [ -f "${PROJECT_ROOT}/docs/starlight/node_modules/.package-lock.json" ]; then
			log "✓ Documentation dependencies installed"
		else
			warn "⚠ Documentation dependencies not installed"
			echo "  Run: cd docs/starlight && npm install"
		fi
	fi
else
	warn "⚠ Node.js not found (needed for documentation builds)"
	echo "  Install Node.js 20+ from: https://nodejs.org/"
fi

echo ""
log "Development environment ready!"
echo ""
echo "Next steps:"
echo "  • Run quality gates locally: nox -s tests lint typecheck"
echo "  • Check your setup: issuesuite doctor"
echo "  • Build documentation: nox -s docs"
echo ""
echo "Before committing:"
echo "  • Pre-commit hooks will automatically run format/lockfile checks"
echo "  • Run full gates: nox -s tests lint typecheck security"
echo "  • Update lockfiles after dependency changes: ./scripts/refresh-deps.sh"
echo ""
