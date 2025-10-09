#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CACHE_DIR="${PROJECT_ROOT}/.cache"
UV_BIN=""
CHECK_ONLY=0

usage() {
	cat <<'EOF'
Usage: refresh-deps.sh [--check]

Refresh repository dependency artifacts so Renovate / contributors keep
lockfiles and generated metadata in sync after updating manifest versions.

Options:
  --check   Run update commands and fail if generated artifacts change.
  -h        Show this help message.
EOF
}

log() {
	printf '[refresh-deps] %s\n' "$*"
}

die() {
	log "error: $*"
	exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
	case $1 in
	--check)
		CHECK_ONLY=1
		shift
		;;
	-h|--help)
		usage
		exit 0
		;;
	*)
		die "unknown option: $1"
		;;
	esac
done

# Ensure cache directory exists for optional tools
mkdir -p "${CACHE_DIR}"

ensure_uv() {
	if command -v uv >/dev/null 2>&1; then
		UV_BIN=$(command -v uv)
		return
	fi

	LOCAL_UV="${CACHE_DIR}/uv-bin/uv"
	if [[ -x ${LOCAL_UV} ]]; then
		UV_BIN="${LOCAL_UV}"
		export PATH="${CACHE_DIR}/uv-bin:${PATH}"
		return
	fi

	log "uv not found; installing to ${CACHE_DIR}/uv-bin"
	mkdir -p "${CACHE_DIR}/uv-bin"
	curl -LsSf https://astral.sh/uv/install.sh | sh -s -- --install-dir "${CACHE_DIR}/uv-bin" --no-modify-path
	UV_BIN="${LOCAL_UV}"
	export PATH="${CACHE_DIR}/uv-bin:${PATH}"
}

update_python_lock() {
	ensure_uv
	log "Refreshing uv.lock via ${UV_BIN}"
	"${UV_BIN}" lock --project "${PROJECT_ROOT}"
}

update_docs_lock() {
	log "Refreshing docs/starlight/package-lock.json"
	(
		cd "${PROJECT_ROOT}/docs/starlight"
		npm install --package-lock-only --no-audit --no-fund
	)
}

update_python_lock
update_docs_lock

if (( CHECK_ONLY )); then
	log "Verifying generated artifacts are current"
	if ! git -C "${PROJECT_ROOT}" diff --quiet -- uv.lock docs/starlight/package-lock.json; then
		log "dependency artifacts are stale; run scripts/refresh-deps.sh to update"
		exit 1
	fi
	log "Dependency artifacts are up to date"
fi
