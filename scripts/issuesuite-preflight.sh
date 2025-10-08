#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME=$(basename "$0")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
	cat <<'EOF'
Usage: issuesuite-preflight.sh [options]

Runs `issuesuite validate` (unless skipped) followed by a dry-run sync with
preflight checks. By default the command writes both the summary and plan
artifacts to the repository root.

Options:
  --config <path>         Path to issue_suite.config.yaml (default: project root)
  --summary-json <path>   Where to write the sync summary JSON
                          (default: issues_summary.json)
  --plan-json <path>      Where to write the plan JSON (default: issues_plan.json)
  --no-summary            Skip writing the summary JSON artifact
  --no-plan               Skip writing the plan JSON artifact
  --skip-validate         Do not run the validate step before syncing
  --respect-status        Pass --respect-status to the sync command
  --issuesuite-bin <exe>  Explicit path to the issuesuite binary
  -h, --help              Show this help output and exit
EOF
}

die() {
	echo "${SCRIPT_NAME}: $*" >&2
	exit 1
}

CONFIG_PATH="${PROJECT_ROOT}/issue_suite.config.yaml"
SUMMARY_JSON="${PROJECT_ROOT}/issues_summary.json"
PLAN_JSON="${PROJECT_ROOT}/issues_plan.json"
RUN_VALIDATE=1
RESPECT_STATUS=0
ISSUESUITE_BIN="${ISSUESUITE_BIN:-}"

while [[ $# -gt 0 ]]; do
	case $1 in
		--config)
			[[ $# -ge 2 ]] || die "--config requires a path"
			CONFIG_PATH=$2
			shift 2
			;;
		--summary-json)
			[[ $# -ge 2 ]] || die "--summary-json requires a path"
			SUMMARY_JSON=$2
			shift 2
			;;
		--plan-json)
			[[ $# -ge 2 ]] || die "--plan-json requires a path"
			PLAN_JSON=$2
			shift 2
			;;
		--no-summary)
			SUMMARY_JSON=""
			shift
			;;
		--no-plan)
			PLAN_JSON=""
			shift
			;;
		--skip-validate)
			RUN_VALIDATE=0
			shift
			;;
		--respect-status)
			RESPECT_STATUS=1
			shift
			;;
		--issuesuite-bin)
			[[ $# -ge 2 ]] || die "--issuesuite-bin requires a path"
			ISSUESUITE_BIN=$2
			shift 2
			;;
		-h|--help)
			usage
			exit 0
			;;
		--)
			shift
			break
			;;
		*)
			die "Unknown option: $1"
			;;
	esac

done

if [[ -z ${ISSUESUITE_BIN} ]]; then
	if [[ -x "${PROJECT_ROOT}/.venv/bin/issuesuite" ]]; then
		ISSUESUITE_BIN="${PROJECT_ROOT}/.venv/bin/issuesuite"
	else
		ISSUESUITE_BIN=$(command -v issuesuite || true)
	fi
fi

[[ -n ${ISSUESUITE_BIN} ]] || die "issuesuite executable not found; set ISSUESUITE_BIN"
[[ -f ${CONFIG_PATH} ]] || die "Config not found at ${CONFIG_PATH}"

log() {
	printf '[preflight] %s\n' "$*"
}

if (( RUN_VALIDATE )); then
	log "Validating specs via ${ISSUESUITE_BIN}"
	"${ISSUESUITE_BIN}" validate --config "${CONFIG_PATH}"
else
	log "Skipping validate step"
fi

SYNC_ARGS=(sync --dry-run --update --preflight --config "${CONFIG_PATH}")
(( RESPECT_STATUS )) && SYNC_ARGS+=(--respect-status)
[[ -n ${SUMMARY_JSON} ]] && SYNC_ARGS+=(--summary-json "${SUMMARY_JSON}")
[[ -n ${PLAN_JSON} ]] && SYNC_ARGS+=(--plan-json "${PLAN_JSON}")

log "Running dry-run sync${RESPECT_STATUS:+ (respect-status)}"
"${ISSUESUITE_BIN}" "${SYNC_ARGS[@]}"

log "Preflight completed"
