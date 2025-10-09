"""Guided setup experience for IssueSuite CLI users."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from textwrap import wrap
from typing import Any

from .coverage_trends import DEFAULT_TARGET

BOX_WIDTH = 74
CONTENT_WIDTH = BOX_WIDTH - 4


class CheckStatus(str, Enum):
    """Checklist status codes used in the guided wizard."""

    READY = "ready"
    ACTION = "action"
    INFO = "info"


@dataclass
class GuidedCheck:
    name: str
    status: CheckStatus
    message: str
    recommendation: str | None = None


@dataclass
class GuidedPlan:
    """Structured plan used for rendering the guided setup."""

    environment: str
    token_status: str
    app_status: str
    checks: list[GuidedCheck]
    commands: list[str]
    follow_ups: list[str]


def _load_coverage_summary(root: Path) -> tuple[str, float | None, list[str]] | None:
    summary_path = root / "coverage_summary.json"
    if not summary_path.exists():
        return None
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    modules = data.get("modules")
    if not isinstance(modules, list):
        return None
    coverages: list[float] = []
    failing: list[str] = []
    for module in modules:
        name = module.get("module")
        coverage = module.get("coverage")
        meets_threshold = module.get("meets_threshold", False)
        if isinstance(coverage, (int, float)):
            coverages.append(float(coverage))
        if not meets_threshold and isinstance(name, str):
            failing.append(name)
    overall = sum(coverages) / len(coverages) if coverages else None
    return summary_path.name, overall, failing


def _format_percentage(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _dedupe_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _config_check(base: Path) -> tuple[GuidedCheck, list[str]]:
    config_path = base / "issue_suite.config.yaml"
    if config_path.exists():
        return (
            GuidedCheck(
                name="Configuration",
                status=CheckStatus.READY,
                message=f"Configuration detected at {config_path.name}",
            ),
            [],
        )
    return (
        GuidedCheck(
            name="Configuration",
            status=CheckStatus.ACTION,
            message="Configuration file missing (issue_suite.config.yaml)",
            recommendation="Run `issuesuite init --all-extras` to scaffold the workspace",
        ),
        ["issuesuite init --all-extras"],
    )


def _spec_check(base: Path) -> tuple[GuidedCheck, list[str]]:
    issues_path = base / "ISSUES.md"
    if issues_path.exists():
        return (
            GuidedCheck(
                name="Specifications",
                status=CheckStatus.READY,
                message="ISSUES.md present and ready for sync",
            ),
            [],
        )
    return (
        GuidedCheck(
            name="Specifications",
            status=CheckStatus.ACTION,
            message="ISSUES.md not found — create specs before syncing",
            recommendation="Use `issuesuite import --output ISSUES.md` or scaffold manually",
        ),
        ["issuesuite import --output ISSUES.md --limit 50"],
    )


def _environment_check(base: Path, token: str | None) -> tuple[GuidedCheck, list[str]]:
    env_path = base / ".env"
    if env_path.exists() and token:
        return (
            GuidedCheck(
                name="Environment",
                status=CheckStatus.READY,
                message=".env present with GitHub token",
            ),
            [],
        )
    return (
        GuidedCheck(
            name="Environment",
            status=CheckStatus.ACTION,
            message="Environment file or GitHub token missing",
            recommendation="Run `issuesuite setup --create-env` then populate GITHUB_TOKEN",
        ),
        ["issuesuite setup --create-env"],
    )


def _developer_ux_check(base: Path) -> GuidedCheck:
    if (base / ".vscode").exists():
        return GuidedCheck(
            name="Developer UX",
            status=CheckStatus.READY,
            message="VS Code workspace detected",
        )
    return GuidedCheck(
        name="Developer UX",
        status=CheckStatus.INFO,
        message="VS Code tasks not found; optional but recommended",
        recommendation="Run `issuesuite setup --vscode` to scaffold tasks and debug profiles",
    )


def _coverage_check(base: Path) -> tuple[GuidedCheck, list[str]]:
    coverage_summary = _load_coverage_summary(base)
    if coverage_summary is None:
        return (
            GuidedCheck(
                name="Coverage Telemetry",
                status=CheckStatus.INFO,
                message="Run tests with coverage to generate coverage_summary.json",
                recommendation="Execute `pytest --cov=issuesuite --cov-report=xml`",
            ),
            ["pytest --cov=issuesuite --cov-report=term --cov-report=xml"],
        )
    summary_name, overall, failing = coverage_summary
    status = CheckStatus.READY if overall and overall >= DEFAULT_TARGET else CheckStatus.INFO
    message = f"{summary_name} reports {_format_percentage(overall)} coverage"
    if failing:
        message += f"; modules below threshold: {', '.join(failing)}"
        status = CheckStatus.INFO
    return (
        GuidedCheck(
            name="Coverage Telemetry",
            status=status,
            message=message,
            recommendation="Run `python scripts/coverage_trends.py` to push telemetry",
        ),
        ["python scripts/coverage_trends.py"],
    )


def build_guided_plan(auth_manager: object, *, root: Path | None = None) -> GuidedPlan:
    base = (root or Path.cwd()).resolve()
    checks: list[GuidedCheck] = []
    commands: list[str] = []
    follow_ups: list[str] = []

    online = bool(getattr(auth_manager, "is_online_environment", lambda: False)())
    token = getattr(auth_manager, "get_github_token", lambda: None)()
    app_cfg_raw: object = getattr(auth_manager, "get_github_app_config", lambda: {})()
    app_cfg: dict[str, object]
    if isinstance(app_cfg_raw, dict):
        app_cfg = {str(key): value for key, value in app_cfg_raw.items()}
    else:
        app_cfg = {}
    recommendations_raw: object = getattr(
        auth_manager, "get_authentication_recommendations", lambda: []
    )()
    recommendations: list[str]
    if isinstance(recommendations_raw, list):
        recommendations = [str(item) for item in recommendations_raw]
    else:
        recommendations = []

    token_status = "✓ Found" if token else "✗ Missing"
    app_ready = (
        all(bool(value) for value in app_cfg.values()) if isinstance(app_cfg, dict) else False
    )
    app_status = "✓ Configured" if app_ready else "✗ Incomplete"

    config_check, config_cmds = _config_check(base)
    checks.append(config_check)
    commands.extend(config_cmds)

    specs_check, spec_cmds = _spec_check(base)
    checks.append(specs_check)
    commands.extend(spec_cmds)

    env_check, env_cmds = _environment_check(base, token)
    checks.append(env_check)
    commands.extend(env_cmds)

    checks.append(_developer_ux_check(base))

    coverage_check, coverage_followups = _coverage_check(base)
    checks.append(coverage_check)
    follow_ups.extend(coverage_followups)

    follow_ups.append("python scripts/quality_gates.py")
    follow_ups.append("python scripts/verify_next_steps.py")
    if isinstance(recommendations, list) and recommendations:
        for rec in recommendations:
            follow_ups.append(rec)

    commands = _dedupe_preserve(commands)
    follow_ups = _dedupe_preserve(follow_ups)

    return GuidedPlan(
        environment="Online" if online else "Local",
        token_status=token_status,
        app_status=app_status,
        checks=checks,
        commands=commands,
        follow_ups=follow_ups,
    )


def _render_line(stream: Any, text: str = "") -> None:
    stream.write(f"║ {text.ljust(CONTENT_WIDTH)} ║\n")


def _render_block(stream: Any, text: str) -> None:
    for line in wrap(text, CONTENT_WIDTH):
        _render_line(stream, line)


def render_guided_plan(plan: GuidedPlan, *, stream: Any | None = None) -> None:
    out = stream or sys.stdout
    top = "╔" + "═" * (BOX_WIDTH - 2) + "╗"
    bottom = "╚" + "═" * (BOX_WIDTH - 2) + "╝"
    out.write(f"{top}\n")
    _render_line(out, "IssueSuite Guided Setup")
    _render_line(out, f"Environment: {plan.environment}")
    _render_line(out, f"GitHub Token: {plan.token_status}")
    _render_line(out, f"GitHub App: {plan.app_status}")
    _render_line(out)
    _render_line(out, "Checklist")
    _render_line(out, "─────────")
    icon_map = {
        CheckStatus.READY: "✅",
        CheckStatus.ACTION: "🔧",
        CheckStatus.INFO: "ℹ️",
    }
    for check in plan.checks:
        prefix = f"{icon_map[check.status]} {check.name}:"
        _render_block(out, f"{prefix} {check.message}")
        if check.recommendation:
            _render_block(out, f"   → {check.recommendation}")
        _render_line(out)
    if plan.commands:
        _render_line(out, "Recommended Commands")
        _render_line(out, "────────────────────")
        for cmd in plan.commands:
            _render_block(out, f"$ {cmd}")
        _render_line(out)
    _render_line(out, "Next Actions")
    _render_line(out, "────────────")
    for action in plan.follow_ups:
        _render_block(out, f"• {action}")
    out.write(f"{bottom}\n")


def run_guided_setup(
    auth_manager: object, *, root: Path | None = None, stream: Any | None = None
) -> None:
    plan = build_guided_plan(auth_manager, root=root)
    render_guided_plan(plan, stream=stream)


__all__ = [
    "CheckStatus",
    "GuidedCheck",
    "GuidedPlan",
    "build_guided_plan",
    "render_guided_plan",
    "run_guided_setup",
]
