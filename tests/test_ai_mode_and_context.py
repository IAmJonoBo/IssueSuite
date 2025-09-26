import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_MODULE = 'issuesuite.cli'

MAX_PREVIEW_CHARS = 2000  # keep previews lightweight for AI ingestion


def run_cli(env: dict[str, str] | None = None, *args: str) -> subprocess.CompletedProcess[str]:
    # Invoke via module so that relative imports resolve under package
    cmd: list[str] = [sys.executable, '-m', CLI_MODULE, *args]
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: PLR1730
        cmd,
        capture_output=True,
        text=True,
        env=proc_env,
        check=False,
    )
    return result


def test_ai_mode_forces_dry_run(tmp_path: Path, monkeypatch: Any) -> None:
    # Minimal config + ISSUES.md
    config = tmp_path / "issue_suite.config.yaml"
    config.write_text("""version: 1\nrepository: example/repo\n""")
    (tmp_path / "ISSUES.md").write_text("""# Roadmap\n\n## [slug: example-feature]\n```yaml\ntitle: Example Feature\nlabels: [feature]\nbody: |\n  Task one\n```\n""")

    env = {"ISSUESUITE_AI_MODE": "1", "ISSUES_SUITE_MOCK": "1"}

    # We call summary which will go through orchestrator path and embed ai_mode
    res = run_cli(env, "summary", "--config", str(config))
    assert res.returncode == 0, res.stderr
    # Expect ai_mode indicator in output
    assert "ai_mode" in res.stdout
    # Dry run should be enforced implicitly (text heuristic)
    assert "dry_run=True" in res.stdout or "dry-run=True" in res.stdout or "dry_run': True" in res.stdout


def test_ai_context_command_structure(tmp_path: Path, monkeypatch: Any) -> None:
    config = tmp_path / "issue_suite.config.yaml"
    config.write_text("""version: 1\nrepository: example/repo\n""")
    (tmp_path / "ISSUES.md").write_text("""# Roadmap\n\n## [slug: example-feature]\n```yaml\ntitle: Example Feature\nlabels: [feature]\nbody: |\n  Task one\n```\n""")

    env = {"ISSUES_SUITE_MOCK": "1"}
    res = run_cli(env, "ai-context", "--config", str(config))
    assert res.returncode == 0, res.stderr

    # Extract last JSON object from potential logging noise
    output_lines = [ln for ln in res.stdout.splitlines() if ln.strip()]
    # Find first line that begins JSON and reconstruct from there
    json_start_index = None
    for idx, ln in enumerate(output_lines):
        if ln.lstrip().startswith('{'):
            json_start_index = idx
            break
    assert json_start_index is not None, f"No JSON object found in output: {res.stdout}"
    json_text = '\n'.join(output_lines[json_start_index:])
    data = json.loads(json_text)
    # Core expected keys
    for key in [
        "schemaVersion",
        "spec_count",
        "preview",
        "config",
        "env",
        "recommended",
    ]:
        assert key in data, f"Missing key: {key} in {data.keys()}"

    assert isinstance(data["preview"], list)
    assert data["schemaVersion"].startswith("ai-context/1"), data["schemaVersion"]
    # Each preview item should have limited keys
    for item in data["preview"]:
        assert set(item.keys()) <= {"external_id","title","hash","labels","milestone","status"}

    # recommended section sanity checks
    assert "usage" in data["recommended"]
    assert "env" in data["recommended"]

