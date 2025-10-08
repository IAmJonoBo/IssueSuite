#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME=$(basename "$0")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
	cat <<'EOF'
Usage: cleanup-macos-cruft.sh [--dry-run] [--include-git]

Remove macOS-specific metadata files and directories that tend to clutter the
IssueSuite workspace (e.g., .DS_Store, __MACOSX, Spotlight caches).

Options:
  --dry-run      Print what would be removed without deleting anything.
  --include-git  Include the .git directory in cleanup (skipped by default).
  -h, --help     Show this help message.
EOF
}

die() {
	echo "${SCRIPT_NAME}: $*" >&2
	exit 1
}

if PROJECT_ROOT=$(cd "${SCRIPT_DIR}" && git rev-parse --show-toplevel 2>/dev/null); then
	PROJECT_ROOT=${PROJECT_ROOT%$'\n'}
else
	PROJECT_ROOT=${SCRIPT_DIR}
fi

[[ -n ${PROJECT_ROOT} ]] || die "Unable to determine project root."

cd "${PROJECT_ROOT}" || die "Unable to change directory to project root."

DRY_RUN=0
INCLUDE_GIT=0

while [[ $# -gt 0 ]]; do
	case $1 in
		--dry-run)
			DRY_RUN=1
			shift
			;;
		--include-git)
			INCLUDE_GIT=1
			shift
			;;
		-h|--help)
			usage
			exit 0
			;;
		*)
			die "Unknown option: $1"
			;;
	esac
done

log() {
	printf '[cleanup] %s\n' "$*"
}

remove_path() {
	local target=$1
	if (( DRY_RUN )); then
		log "Would remove: ${target}"
	else
		rm -rf -- "${target}"
		log "Removed: ${target}"
	fi
}

find_and_remove() {
	local type_flag=$1
	local pattern=$2
	local -a cmd=(find "${PROJECT_ROOT}")

	if (( INCLUDE_GIT )); then
		cmd+=(-type "${type_flag}" -name "${pattern}" -print0)
	else
		cmd+=(
			'(' -path "${PROJECT_ROOT}/.git" -prune ')'
			-o
			'(' -type "${type_flag}" -name "${pattern}" -print0 ')'
		)
	fi

	while IFS= read -r -d '' match; do
		remove_path "${match}"
	done < <("${cmd[@]}")
}

CLEAN_FILE_PATTERNS=(
	".DS_Store"
	"._*"
	"Icon?"
	".LSOverride"
)

CLEAN_DIR_PATTERNS=(
	".AppleDouble"
	".AppleDesktop"
	".DocumentRevisions-V100"
	".Spotlight-V100"
	".TemporaryItems"
	".Trashes"
	".fseventsd"
	"__MACOSX"
)

log "Cleaning macOS metadata from ${PROJECT_ROOT}"
(( DRY_RUN )) && log "Dry run enabled; no files will be deleted."

for pattern in "${CLEAN_FILE_PATTERNS[@]}"; do
	find_and_remove f "${pattern}"
done

for pattern in "${CLEAN_DIR_PATTERNS[@]}"; do
	find_and_remove d "${pattern}"
done

log "macOS cleanup complete."
