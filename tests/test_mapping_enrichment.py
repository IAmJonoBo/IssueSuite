import json
import os
import subprocess
import sys
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

# Constants used across tests (avoid magic numbers)
SMALL_MAPPING_SIZE = 2
LARGE_MAPPING_THRESHOLD_EXCEEDED = 501  # threshold (500) + 1

CONFIG = "issue_suite.config.yaml"


def run_cli(args: list[str]) -> str:
    """Invoke issuesuite CLI returning stdout (asserts success)."""
    env = os.environ.copy()
    env["ISSUESUITE_AI_MODE"] = "1"  # force dry-run safety
    proc = subprocess.run(
        [sys.executable, "-m", "issuesuite"] + args,
        capture_output=True,
        text=True,
        env=env,
        check=False,  # we assert explicitly to capture stderr in assertion message
    )
    assert proc.returncode == 0, proc.stderr
    # Some tests run with logging still enabled; extract JSON object from mixed output.
    out = proc.stdout.strip()
    if out.startswith("{") and out.endswith("}"):  # fast path
        return out
    # Fallback: locate first '{' and last '}' to slice potential JSON
    start = out.find("{")
    end = out.rfind("}")
    if start != -1 and end != -1 and start < end:
        return out[start : end + 1]
    return out  # let caller fail with JSON error for visibility


def test_ai_context_includes_mapping_snapshot(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Copy config & sources into temp dir
    repo_root = Path(__file__).resolve().parent.parent
    for name in ["issue_suite.config.yaml", "ISSUES.md"]:
        src = repo_root / name
        if src.exists():
            (tmp_path / name).write_text(src.read_text())
    # Create minimal index.json with small mapping
    issues_dir = tmp_path / ".issuesuite"
    issues_dir.mkdir(exist_ok=True)
    (issues_dir / "index.json").write_text(
        json.dumps({"mapping": {"alpha": 101, "beta": 202}}, indent=2)
    )
    monkeypatch.chdir(tmp_path)

    out = run_cli(["ai-context", "--config", CONFIG, "--preview", "2"])
    data = json.loads(out)
    mapping = data["mapping"]
    assert mapping["present"] is True
    assert mapping["size"] == SMALL_MAPPING_SIZE
    assert mapping["snapshot_included"] is True
    assert mapping["snapshot"] == {"alpha": 101, "beta": 202}


def test_ai_context_large_mapping_excludes_snapshot(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    for name in ["issue_suite.config.yaml", "ISSUES.md"]:
        src = repo_root / name
        if src.exists():
            (tmp_path / name).write_text(src.read_text())
    issues_dir = tmp_path / ".issuesuite"
    issues_dir.mkdir(exist_ok=True)
    # Generate mapping > threshold (501 entries)
    large_map = {f"id{i}": i for i in range(0, LARGE_MAPPING_THRESHOLD_EXCEEDED)}
    (issues_dir / "index.json").write_text(json.dumps({"mapping": large_map}))
    monkeypatch.chdir(tmp_path)

    out = run_cli(["ai-context", "--config", CONFIG, "--preview", "1"])
    data = json.loads(out)
    mapping = data["mapping"]
    assert mapping["present"] is True
    assert mapping["size"] == LARGE_MAPPING_THRESHOLD_EXCEEDED
    assert mapping["snapshot_included"] is False
    assert mapping["snapshot"] is None


def test_sync_summary_mapping_fields(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    for name in ["issue_suite.config.yaml", "ISSUES.md"]:
        src = repo_root / name
        if src.exists():
            (tmp_path / name).write_text(src.read_text())
    # Pre-seed mapping file
    issues_dir = tmp_path / ".issuesuite"
    issues_dir.mkdir(exist_ok=True)
    (issues_dir / "index.json").write_text(json.dumps({"mapping": {"x": 1}}, indent=2))
    monkeypatch.chdir(tmp_path)

    env = os.environ.copy()
    env["ISSUESUITE_AI_MODE"] = "1"  # force dry-run (ensures we don't mutate mapping)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "issuesuite",
            "sync",
            "--config",
            CONFIG,
            "--dry-run",
            "--update",
            "--summary-json",
            "summary.json",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    summary_json = json.loads(Path("summary.json").read_text())
    assert "mapping_present" in summary_json
    assert "mapping_size" in summary_json
    assert isinstance(summary_json["mapping_present"], bool)
    assert isinstance(summary_json["mapping_size"], int)
