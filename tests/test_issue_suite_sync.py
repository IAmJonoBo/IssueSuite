from __future__ import annotations

import shutil
import subprocess
import textwrap
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import pytest

from issuesuite.core import IssueSuite
from issuesuite.models import IssueSpec


class _StubLogger:
    def debug(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def info(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def log_operation(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def log_error(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def timed_operation(self, *_args: Any, **_kwargs: Any):  # noqa: ANN201 - context manager
        return nullcontext()


class _StubBenchmark:
    def measure(self, *_args: Any, **_kwargs: Any):  # noqa: ANN201 - context manager
        return nullcontext()

    def generate_report(self) -> None:
        pass


class _StubAssigner:
    def assign(self, issue_number: int, spec: Any) -> None:
        pass


@pytest.fixture(autouse=True)
def _stub_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("issuesuite.core.configure_logging", lambda **_kwargs: _StubLogger())
    monkeypatch.setattr("issuesuite.core.create_benchmark", lambda cfg, mock: _StubBenchmark())


def _make_spec() -> IssueSpec:
    return IssueSpec(
        external_id="frontier-apex",
        title="Frontier Apex launch",
        labels=["governance"],
        milestone=None,
        body="Finalize blueprint",
        status="open",
    )


def test_issue_suite_sync_covers_dry_run_and_apply(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = _write_basic_config(tmp_path)
    issues_path = tmp_path / "ISSUES.md"
    issues_path.write_text(
        textwrap.dedent(
            """
            ## [slug: frontier-apex]

            ```yaml
            title: Frontier Apex launch
            labels: [governance]
            body: |
              Finalize blueprint
            ```
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    suite = IssueSuite.from_config_path(config_path)
    spec = _make_spec()

    monkeypatch.setattr(suite, "_sync_parse_and_preflight", lambda preflight: [spec])
    monkeypatch.setattr(suite, "_build_project_assigner", lambda: _StubAssigner())
    monkeypatch.setattr(suite, "_sync_fetch_existing", lambda preflight: [])
    monkeypatch.setattr(suite, "_load_hash_state", lambda: {})

    def fake_process(
        specs: list[IssueSpec],
        existing: list[dict[str, Any]],
        prev_hashes: dict[str, str],
        dry_run: bool,
        update: bool,
        respect_status: bool,
        project_assigner: Any,
    ) -> list[dict[str, Any]]:
        return [{"spec": specs[0], "action": "create", "number": 101}]

    monkeypatch.setattr(suite, "_sync_process_specs", fake_process)

    monkeypatch.setattr(
        suite,
        "_sync_build_summary",
        lambda specs, results: {
            "totals": {"created": 1, "updated": 0, "closed": 0, "specs": len(specs), "skipped": 0}
        },
    )
    prune_calls: list[str] = []
    save_calls: list[str] = []
    monkeypatch.setattr(suite, "_prune_unmatched", lambda existing, results, dry_run: prune_calls.append("prune"))
    monkeypatch.setattr(suite, "_save_hash_state", lambda specs: save_calls.append("save"))

    dry_summary = suite.sync(dry_run=True, update=True, respect_status=True, preflight=False)

    assert dry_summary["plan"][0]["action"] == "create"
    assert dry_summary["totals"]["created"] == 1

    apply_summary = suite.sync(dry_run=False, update=False, respect_status=False, preflight=False, prune=True)

    assert "plan" not in apply_summary
    assert prune_calls == ["prune"]
    assert save_calls == ["save"]


def _write_basic_config(tmp_path: Path, *, milestone_required: bool = False) -> Path:
    config_path = tmp_path / "issue_suite.config.yaml"
    base = textwrap.dedent(
        """
        version: 1
        source:
          file: ISSUES.md
        defaults:
          ensure_labels_enabled: false
          ensure_milestones_enabled: false
        output:
          summary_json: issues_summary.json
          export_json: issues_export.json
          hash_state_file: .issuesuite_hashes.json
        """
    ).strip()
    if milestone_required:
        base = base.replace("file: ISSUES.md", "file: ISSUES.md\n  milestone_required: true")
    config_path.write_text(base + "\n", encoding="utf-8")
    return config_path


def test_issue_suite_build_summary(tmp_path: Path) -> None:
    config_path = _write_basic_config(tmp_path)
    issues_path = tmp_path / "ISSUES.md"
    issues_path.write_text(
        textwrap.dedent(
            """
            ## [slug: frontier-apex]

            ```yaml
            title: Frontier Apex launch
            labels: [governance]
            milestone: Alpha
            body: |
              Finalize blueprint
            ```
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    suite = IssueSuite.from_config_path(config_path)
    spec1 = _make_spec()
    spec2 = IssueSpec(
        external_id="frontier-done",
        title="Frontier Done",
        labels=["governance"],
        milestone="Beta",
        body="Done",
        status="closed",
    )
    processed = [
        {"spec": spec1, "result": {"created": True, "mapped": 5}},
        {
            "spec": spec2,
            "result": {
                "updated": {"body": "Done"},
                "closed": {"number": 8},
                "skipped": True,
            },
        },
    ]

    summary = suite._sync_build_summary([spec1, spec2], processed)

    assert summary["totals"] == {
        "specs": 2,
        "created": 1,
        "updated": 1,
        "closed": 1,
        "skipped": 1,
    }
    assert summary["mapping"]["frontier-apex"] == 5


def test_sync_parse_and_preflight_enforces_milestones(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = _write_basic_config(tmp_path, milestone_required=True)
    issues_path = tmp_path / "ISSUES.md"
    issues_path.write_text(
        textwrap.dedent(
            """
            ## [slug: frontier-apex]

            ```yaml
            title: Frontier Apex launch
            labels: [governance]
            body: |
              Finalize blueprint
            ```
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    suite = IssueSuite.from_config_path(config_path)

    with pytest.raises(ValueError):
        suite._sync_parse_and_preflight(preflight=False)


def test_sync_parse_and_preflight_runs_preflight(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = _write_basic_config(tmp_path)
    issues_path = tmp_path / "ISSUES.md"
    issues_path.write_text(
        textwrap.dedent(
            """
            ## [slug: frontier-apex]

            ```yaml
            title: Frontier Apex launch
            labels: [governance]
            milestone: Alpha
            body: |
              Finalize blueprint
            ```
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    suite = IssueSuite.from_config_path(config_path)
    called: list[int] = []
    monkeypatch.setattr(suite, "_preflight", lambda specs: called.append(len(specs)))

    specs = suite._sync_parse_and_preflight(preflight=True)

    assert called == [len(specs)]


def test_process_spec_create_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = _write_basic_config(tmp_path)
    issues_path = tmp_path / "ISSUES.md"
    issues_path.write_text(
        textwrap.dedent(
            """
            ## [slug: frontier-apex]

            ```yaml
            title: Frontier Apex launch
            labels: [governance]
            body: |
              Finalize blueprint
            ```
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    suite = IssueSuite.from_config_path(config_path)
    spec = _make_spec()
    created: list[str] = []
    monkeypatch.setattr(suite, "_create", lambda s, d: (created.append(s.external_id), 101)[1])
    monkeypatch.setattr(
        suite,
        "_maybe_assign_project_on_create",
        lambda spec, assigner, result, dry_run: result.update({"mapped": 101}),
    )

    result = suite._process_spec(
        spec=spec,
        existing=[],
        prev_hashes={},
        dry_run=True,
        update=True,
        respect_status=True,
        project_assigner=_StubAssigner(),
    )

    assert result["created"] is True
    assert created == ["frontier-apex"]


def test_process_spec_update_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = _write_basic_config(tmp_path)
    issues_path = tmp_path / "ISSUES.md"
    issues_path.write_text(
        textwrap.dedent(
            """
            ## [slug: frontier-apex]

            ```yaml
            title: Frontier Apex launch
            labels: [governance]
            body: |
              Finalize blueprint
            ```
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    suite = IssueSuite.from_config_path(config_path)
    spec = _make_spec()
    match = {"number": 42, "state": "OPEN"}
    monkeypatch.setattr(suite, "_match", lambda s, existing: match)
    monkeypatch.setattr("issuesuite.core.needs_update", lambda s, issue, prev: True)
    updated: list[int] = []
    monkeypatch.setattr(suite, "_update", lambda s, issue, dry_run: updated.append(issue["number"]))

    result = suite._process_spec(
        spec=spec,
        existing=[match],
        prev_hashes={},
        dry_run=False,
        update=True,
        respect_status=True,
        project_assigner=_StubAssigner(),
    )

    assert result["updated"]["number"] == 42
    assert updated == [42]


def test_process_spec_close_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = _write_basic_config(tmp_path)
    issues_path = tmp_path / "ISSUES.md"
    issues_path.write_text(
        textwrap.dedent(
            """
            ## [slug: frontier-apex]

            ```yaml
            title: Frontier Apex launch
            labels: [governance]
            body: |
              Finalize blueprint
            ```
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    suite = IssueSuite.from_config_path(config_path)
    spec = _make_spec()
    spec.status = "closed"
    match = {"number": 7, "state": "OPEN"}
    monkeypatch.setattr(suite, "_match", lambda s, existing: match)
    monkeypatch.setattr("issuesuite.core.needs_update", lambda s, issue, prev: False)
    closed: list[int] = []
    monkeypatch.setattr(suite, "_close", lambda issue, dry_run: closed.append(issue["number"]))

    result = suite._process_spec(
        spec=spec,
        existing=[match],
        prev_hashes={},
        dry_run=False,
        update=True,
        respect_status=True,
        project_assigner=_StubAssigner(),
    )

    assert result["closed"]["number"] == 7
    assert closed == [7]


def test_process_spec_skip_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = _write_basic_config(tmp_path)
    issues_path = tmp_path / "ISSUES.md"
    issues_path.write_text(
        textwrap.dedent(
            """
            ## [slug: frontier-apex]

            ```yaml
            title: Frontier Apex launch
            labels: [governance]
            body: |
              Finalize blueprint
            ```
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    suite = IssueSuite.from_config_path(config_path)
    spec = _make_spec()
    match = {"number": 9, "state": "CLOSED"}
    monkeypatch.setattr(suite, "_match", lambda s, existing: match)
    monkeypatch.setattr("issuesuite.core.needs_update", lambda s, issue, prev: False)

    result = suite._process_spec(
        spec=spec,
        existing=[match],
        prev_hashes={},
        dry_run=True,
        update=False,
        respect_status=True,
        project_assigner=_StubAssigner(),
    )

    assert result["skipped"] is True


def test_prune_unmatched_closes_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    suite = IssueSuite.from_config_path(_write_basic_config(tmp_path))
    closed: list[int] = []
    monkeypatch.setattr(suite, "_close", lambda issue, dry_run: closed.append(issue["number"]))
    existing = [{"number": 5}, {"number": 6}]
    processed = [{"result": {"mapped": 5}}, {"result": {"mapped": 4}}]

    suite._prune_unmatched(existing, processed, dry_run=False)

    assert closed == [6]


def test_maybe_assign_project_on_create_mock_mode(tmp_path: Path) -> None:
    suite = IssueSuite.from_config_path(_write_basic_config(tmp_path))
    suite._mock = True
    suite.cfg.project_enable = True
    spec = IssueSpec(
        external_id="123",
        title="Numeric",
        labels=[],
        milestone=None,
        body="",
    )
    result: dict[str, Any] = {}

    suite._maybe_assign_project_on_create(spec, _StubAssigner(), result, dry_run=False)

    assert result["mapped"] == 123


def test_match_prefers_marker(tmp_path: Path) -> None:
    suite = IssueSuite.from_config_path(_write_basic_config(tmp_path))
    spec = _make_spec()
    existing = [{"body": "<!-- issuesuite:slug=frontier-apex -->\nHello"}]

    match = suite._match(spec, existing)

    assert match is existing[0]


def test_load_and_save_hash_state(tmp_path: Path) -> None:
    suite = IssueSuite.from_config_path(_write_basic_config(tmp_path))
    specs = [_make_spec()]
    specs[0].hash = "abc123"
    suite._save_hash_state(specs)

    loaded = suite._load_hash_state()

    assert loaded == {"frontier-apex": "abc123"}


def test_existing_issues_uses_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    suite = IssueSuite.from_config_path(_write_basic_config(tmp_path))
    suite._mock = True  # ensure _gh_auth short-circuits

    class _StubClient:
        def list_existing(self) -> list[dict[str, Any]]:
            return [{"number": 1}]

    monkeypatch.setattr(suite, "_build_issues_client", lambda dry_run: _StubClient())

    assert suite._existing_issues() == [{"number": 1}]


def test_gh_auth_without_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    suite = IssueSuite.from_config_path(_write_basic_config(tmp_path))
    suite._mock = False
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    assert suite._gh_auth() is False


def test_gh_auth_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    suite = IssueSuite.from_config_path(_write_basic_config(tmp_path))
    suite._mock = False
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gh")
    monkeypatch.setattr(subprocess, "check_output", lambda args, stderr: b"ok")

    assert suite._gh_auth() is True


def test_aggregate_results_compiles_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    suite = IssueSuite.from_config_path(_write_basic_config(tmp_path))
    specs = [_make_spec(), _make_spec(), _make_spec(), _make_spec()]
    specs[1].external_id = "frontier-two"
    specs[2].external_id = "frontier-three"
    specs[3].external_id = "frontier-four"
    results = [
        {"created": True, "mapped": 5},
        {"updated": {"number": 2}},
        {"closed": {"number": 3}},
        {"skipped": True},
    ]

    summary = suite._aggregate_results(specs, results, dry_run=True)

    assert summary["totals"] == {
        "specs": 4,
        "created": 1,
        "updated": 1,
        "closed": 1,
        "skipped": 1,
    }
    assert summary["mapping"]["frontier-apex"] == 5


@pytest.mark.asyncio
async def test_process_specs_async_sequential(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    suite = IssueSuite.from_config_path(_write_basic_config(tmp_path))
    suite.cfg.concurrency_enabled = False
    spec = _make_spec()
    monkeypatch.setattr(
        suite,
        "_process_spec",
        lambda spec, existing, prev_hashes, dry_run, update, respect_status, project_assigner: {"created": True},
    )

    results = await suite._process_specs_async(
        [spec], [], {}, True, False, True, _StubAssigner()
    )

    assert results == [{"created": True}]


@pytest.mark.asyncio
async def test_process_specs_async_concurrent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    suite = IssueSuite.from_config_path(_write_basic_config(tmp_path))
    suite.cfg.concurrency_enabled = True
    suite.cfg.concurrency_max_workers = 2
    specs = [_make_spec(), _make_spec()]

    class _StubProcessor:
        async def process_specs_concurrent(self, specs, func, *args):  # noqa: ANN001
            return [{"created": True} for _ in specs]

    monkeypatch.setattr(
        "issuesuite.core.create_concurrent_processor", lambda config, mock: _StubProcessor()
    )

    results = await suite._process_specs_async(
        specs, [], {}, True, False, True, _StubAssigner()
    )

    assert results == [{"created": True}, {"created": True}]


@pytest.mark.asyncio
async def test_fetch_existing_async_with_concurrency(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    suite = IssueSuite.from_config_path(_write_basic_config(tmp_path))
    suite.cfg.concurrency_enabled = True
    monkeypatch.setattr(suite, "_gh_auth", lambda: True)

    async def _fake_existing() -> list[dict[str, Any]]:
        return [{"number": 9}]

    monkeypatch.setattr(suite, "_get_existing_issues_async", _fake_existing)

    existing = await suite._fetch_existing_async()

    assert existing == [{"number": 9}]


@pytest.mark.asyncio
async def test_sync_async_flow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    suite = IssueSuite.from_config_path(_write_basic_config(tmp_path))
    spec = _make_spec()
    monkeypatch.setattr(suite, "parse", lambda: [spec])
    adjusted: list[int] = []
    monkeypatch.setattr(suite, "_adjust_concurrency_if_needed", lambda count: adjusted.append(count))
    preflight_calls: list[int] = []
    monkeypatch.setattr(suite, "_preflight", lambda specs: preflight_calls.append(len(specs)))
    monkeypatch.setattr(suite, "_build_project_assigner", lambda: _StubAssigner())
    async def _fake_fetch() -> list[dict[str, Any]]:
        return []

    async def _fake_process(
        specs: list[IssueSpec],
        existing: list[dict[str, Any]],
        prev_hashes: dict[str, str],
        dry_run: bool,
        update: bool,
        respect_status: bool,
        assigner: Any,
    ) -> list[dict[str, Any]]:
        return [{"created": True}]

    monkeypatch.setattr(suite, "_fetch_existing_async", _fake_fetch)
    monkeypatch.setattr(suite, "_process_specs_async", _fake_process)
    monkeypatch.setattr(
        suite,
        "_aggregate_results",
        lambda specs, results, dry_run: {
            "totals": {"specs": 1, "created": 1, "updated": 0, "closed": 0, "skipped": 0}
        },
    )

    summary = await suite.sync_async(dry_run=True, update=False, respect_status=True, preflight=True)

    assert summary["totals"]["created"] == 1
    assert adjusted == [1]
    assert preflight_calls == [1]
