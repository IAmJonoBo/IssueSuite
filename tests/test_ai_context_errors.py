from __future__ import annotations

from pathlib import Path

from issuesuite import get_ai_context, load_config


def test_ai_context_includes_errors_section(tmp_path: Path, monkeypatch):
    # Minimal ISSUES.md
    (tmp_path / "ISSUES.md").write_text(
        "## [slug: ex]\n\n```yaml\ntitle: Example\nlabels: [x]\n```\n"
    )
    (tmp_path / "issue_suite.config.yaml").write_text("version: 1\nsource:\n  file: ISSUES.md\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ISSUESUITE_RETRY_ATTEMPTS", "5")
    monkeypatch.setenv("ISSUESUITE_RETRY_BASE", "0.75")

    cfg = load_config("issue_suite.config.yaml")
    doc = get_ai_context(cfg, preview=1)

    assert "errors" in doc
    errs = doc["errors"]
    assert "categories" in errs and isinstance(errs["categories"], list)
    assert {"github.rate_limit", "github.abuse", "network", "parse", "generic"} <= set(
        errs["categories"]
    )
    retry = errs["retry"]
    assert retry["attempts_env"] == "5"
    assert retry["base_env"] == "0.75"
    assert retry["strategy"] == "exponential_backoff_with_jitter"
