#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME=$(basename "$0")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PREFLIGHT_SCRIPT="${PROJECT_ROOT}/scripts/issuesuite-preflight.sh"

usage() {
	cat <<'EOF'
Usage: issuesuite-dx-sweep.sh [options]

Runs the preflight workflow (validate + dry-run sync) and then executes a
comprehensive developer experience sweep: summary, export, schema generation,
AI context capture, and optional reconcile.

Options:
  --with-reconcile         Run issuesuite reconcile (exit code 2 is tolerated)
  --skip-summary-step      Skip the summary command
  --skip-export            Skip export generation
  --skip-schema            Skip schema generation
  --skip-ai-context        Skip AI context capture
	--export-json <path>     Destination for issues_export.json (default project root)
  --ai-context-json <path> Destination for ai-context output (default ai_context.json)
  --issuesuite-bin <exe>   Explicit path to issuesuite binary

  Any additional options are forwarded to issuesuite-preflight.sh so you can
	customise config/summary/plan paths or skip validation. For example:
    issuesuite-dx-sweep.sh --skip-validate --plan-json /tmp/plan.json
EOF
}

die() {
	echo "${SCRIPT_NAME}: $*" >&2
	exit 1
}

ISSUESUITE_BIN="${ISSUESUITE_BIN:-}"
CONFIG_PATH="${PROJECT_ROOT}/issue_suite.config.yaml"
SUMMARY_JSON="${PROJECT_ROOT}/issues_summary.json"
PLAN_JSON="${PROJECT_ROOT}/issues_plan.json"
EXPORT_PATH="${PROJECT_ROOT}/issues_export.json"
AI_CONTEXT_JSON="${PROJECT_ROOT}/ai_context.json"
WITH_RECONCILE=0
RUN_SUMMARY=1
RUN_EXPORT=1
RUN_SCHEMA=1
RUN_AI_CONTEXT=1
PREFLIGHT_ARGS=()

while [[ $# -gt 0 ]]; do
	case $1 in
		--with-reconcile)
			WITH_RECONCILE=1
			shift
			;;
		--skip-summary-step)
			RUN_SUMMARY=0
			shift
			;;
		--skip-export)
			RUN_EXPORT=0
			shift
			;;
		--skip-schema)
			RUN_SCHEMA=0
			shift
			;;
		--skip-ai-context)
			RUN_AI_CONTEXT=0
			shift
			;;
		--ai-context-json)
			[[ $# -ge 2 ]] || die "--ai-context-json requires a path"
			AI_CONTEXT_JSON=$2
			shift 2
			;;
		--issuesuite-bin)
			[[ $# -ge 2 ]] || die "--issuesuite-bin requires a path"
			ISSUESUITE_BIN=$2
			PREFLIGHT_ARGS+=("--issuesuite-bin" "$2")
			shift 2
			;;
		--export-json)
			[[ $# -ge 2 ]] || die "--export-json requires a path"
			EXPORT_PATH=$2
			shift 2
			;;
		--config)
			[[ $# -ge 2 ]] || die "--config requires a path"
			CONFIG_PATH=$2
			PREFLIGHT_ARGS+=("--config" "$2")
			shift 2
			;;
		--summary-json)
			[[ $# -ge 2 ]] || die "--summary-json requires a path"
			SUMMARY_JSON=$2
			PREFLIGHT_ARGS+=("--summary-json" "$2")
			shift 2
			;;
		--plan-json)
			[[ $# -ge 2 ]] || die "--plan-json requires a path"
			PLAN_JSON=$2
			PREFLIGHT_ARGS+=("--plan-json" "$2")
			shift 2
			;;
		--no-summary|--no-plan|--skip-validate|--respect-status)
			PREFLIGHT_ARGS+=("$1")
			[[ $1 == --no-summary ]] && SUMMARY_JSON=""
			[[ $1 == --no-plan ]] && PLAN_JSON=""
			shift
			;;
		-h|--help)
			usage
			exit 0
			;;
		--)
			shift
			PREFLIGHT_ARGS+=("$@")
			break
			;;
		*)
			PREFLIGHT_ARGS+=("$1")
			shift
			;;
	esac

done

[[ -x ${PREFLIGHT_SCRIPT} ]] || die "Preflight script not found at ${PREFLIGHT_SCRIPT}"

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
	printf '[dx] %s\n' "$*"
}

log "Starting preflight"
"${PREFLIGHT_SCRIPT}" "${PREFLIGHT_ARGS[@]}"

if (( RUN_SUMMARY )); then
	log "Running summary"
	"${ISSUESUITE_BIN}" summary --config "${CONFIG_PATH}"
else
	log "Skipping summary step"
fi

if (( RUN_EXPORT )); then
	log "Exporting specs to ${EXPORT_PATH}"
	"${ISSUESUITE_BIN}" export --pretty --config "${CONFIG_PATH}" --output "${EXPORT_PATH}"
else
	log "Skipping export step"
fi

if (( RUN_SCHEMA )); then
	log "Generating JSON schemas"
	"${ISSUESUITE_BIN}" schema --config "${CONFIG_PATH}"
else
	log "Skipping schema step"
fi

if (( RUN_AI_CONTEXT )); then
	log "Writing AI context to ${AI_CONTEXT_JSON}"
	"${ISSUESUITE_BIN}" ai-context --quiet --config "${CONFIG_PATH}" > "${AI_CONTEXT_JSON}"
else
	log "Skipping AI context step"
fi

if (( WITH_RECONCILE )); then
	log "Running reconcile"
	set +e
	"${ISSUESUITE_BIN}" reconcile --config "${CONFIG_PATH}"
	status=$?
	set -e
	if [[ ${status} -eq 2 ]]; then
		log "Reconcile detected drift (exit 2); continuing"
	elif [[ ${status} -ne 0 ]]; then
		die "Reconcile failed with exit code ${status}"
	fi
else
	log "Skipping reconcile step"
fi

log "DX sweep completed"
