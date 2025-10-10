import pytest

from issuesuite import IssueSuite, load_config

CONFIG_WITH_CONCURRENCY = """
version: 1
source:
  file: ISSUES.md
github: {}
defaults:
  inject_labels: []
  ensure_milestones: []
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
output: {}
behavior: {}
ai: {}
logging:
  json_enabled: false
  level: INFO
concurrency:
  enabled: true
  max_workers: 2
"""

CONFIG_WITHOUT_CONCURRENCY = """
version: 1
source:
  file: ISSUES.md
github: {}
defaults:
  inject_labels: []
  ensure_milestones: []
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
output: {}
behavior: {}
ai: {}
logging:
  json_enabled: false
  level: INFO
concurrency:
  enabled: false
  max_workers: 4
"""

# Large roadmap to trigger concurrency
LARGE_ISSUES = """## [slug: first-issue]
```yaml
title: First Issue
labels: [bug]
body: |
  First issue body
```

## [slug: second-issue]
```yaml
title: Second Issue
labels: [enhancement]
body: |
  Second issue body
```

## [slug: third-issue]
```yaml
title: Third Issue
labels: [documentation]
body: |
  Third issue body
```

## [slug: fourth-issue]
```yaml
title: Fourth Issue
labels: [bug, high-priority]
body: |
  Fourth issue body
```

## [slug: fifth-issue]
```yaml
title: Fifth Issue
labels: [enhancement]
body: |
  Fifth issue body
```

## [slug: sixth-issue]
```yaml
title: Sixth Issue
labels: [bug]
body: |
  Sixth issue body
```

## [slug: seventh-issue]
```yaml
title: Seventh Issue
labels: [enhancement]
body: |
  Seventh issue body
```

## [slug: eighth-issue]
```yaml
title: Eighth Issue
labels: [documentation]
body: |
  Eighth issue body
```

## [slug: ninth-issue]
```yaml
title: Ninth Issue
labels: [bug]
body: |
  Ninth issue body
```

## [slug: tenth-issue]
```yaml
title: Tenth Issue
labels: [enhancement]
body: |
  Tenth issue body
```

## [slug: eleventh-issue]
```yaml
title: Eleventh Issue
labels: [bug]
body: |
  Eleventh issue body
```

## [slug: twelfth-issue]
```yaml
title: Twelfth Issue
labels: [enhancement]
body: |
  Twelfth issue body
```
"""

SMALL_ISSUES = """## [slug: single-issue]
```yaml
title: Single Issue
labels: [bug]
body: |
  Single issue body
```
"""


def test_sync_with_concurrency_enabled(monkeypatch, tmp_path):
    """Test sync with concurrency enabled for large roadmap."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    (tmp_path / "ISSUES.md").write_text(LARGE_ISSUES)
    cfg_path.write_text(CONFIG_WITH_CONCURRENCY)

    # Set mock mode to avoid GitHub CLI calls
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    # Verify concurrency config is loaded
    assert cfg.concurrency_enabled is True
    assert cfg.concurrency_max_workers == 2
    assert suite._concurrency_config.enabled is True
    assert suite._concurrency_config.max_workers == 2

    # Run sync - should use async path for large roadmap
    summary = suite.sync(
        dry_run=True, update=False, respect_status=False, preflight=False
    )

    # Should process all 12 specs
    assert summary["totals"]["specs"] == 12
    assert summary["totals"]["created"] == 12


def test_sync_with_concurrency_disabled(monkeypatch, tmp_path):
    """Test sync with concurrency disabled."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    (tmp_path / "ISSUES.md").write_text(LARGE_ISSUES)
    cfg_path.write_text(CONFIG_WITHOUT_CONCURRENCY)

    # Set mock mode to avoid GitHub CLI calls
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    # Verify concurrency is disabled
    assert cfg.concurrency_enabled is False
    assert suite._concurrency_config.enabled is False

    # Run sync - should use sequential path
    summary = suite.sync(
        dry_run=True, update=False, respect_status=False, preflight=False
    )

    # Should still process all specs correctly
    assert summary["totals"]["specs"] == 12
    assert summary["totals"]["created"] == 12


def test_sync_small_roadmap_uses_sequential(monkeypatch, tmp_path):
    """Test that small roadmaps use sequential processing even with concurrency enabled."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    (tmp_path / "ISSUES.md").write_text(SMALL_ISSUES)
    cfg_path.write_text(CONFIG_WITH_CONCURRENCY)

    # Set mock mode to avoid GitHub CLI calls
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    # Verify concurrency is enabled but should fall back to sequential for small roadmap
    assert cfg.concurrency_enabled is True

    # Run sync - should use sequential path for small roadmap
    summary = suite.sync(
        dry_run=True, update=False, respect_status=False, preflight=False
    )

    # Should process the single spec correctly
    assert summary["totals"]["specs"] == 1
    assert summary["totals"]["created"] == 1


@pytest.mark.asyncio
async def test_sync_async_method(monkeypatch, tmp_path):
    """Test the async sync method directly."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    (tmp_path / "ISSUES.md").write_text(LARGE_ISSUES)
    cfg_path.write_text(CONFIG_WITH_CONCURRENCY)

    # Set mock mode to avoid GitHub CLI calls
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    # Call async sync directly
    summary = await suite.sync_async(
        dry_run=True, update=False, respect_status=False, preflight=False
    )

    # Should process all specs with concurrency
    assert summary["totals"]["specs"] == 12
    assert summary["totals"]["created"] == 12


def test_concurrency_config_loading(tmp_path):
    """Test loading concurrency configuration from config file."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(CONFIG_WITH_CONCURRENCY)

    cfg = load_config(cfg_path)

    # Verify concurrency settings are loaded correctly
    assert cfg.concurrency_enabled is True
    assert cfg.concurrency_max_workers == 2


def test_concurrency_config_defaults(tmp_path):
    """Test default concurrency configuration when not specified."""
    config_without_concurrency_section = """
version: 1
source:
  file: ISSUES.md
github: {}
defaults:
  inject_labels: []
  ensure_milestones: []
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
output: {}
behavior: {}
ai: {}
"""

    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(config_without_concurrency_section)

    cfg = load_config(cfg_path)

    # Verify default concurrency settings
    assert cfg.concurrency_enabled is False
    assert cfg.concurrency_max_workers == 4


def test_optimal_worker_adjustment(monkeypatch, tmp_path):
    """Test that sync works with concurrency configuration."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    (tmp_path / "ISSUES.md").write_text(LARGE_ISSUES)
    cfg_path.write_text(CONFIG_WITH_CONCURRENCY)

    # Set mock mode
    monkeypatch.setenv("ISSUES_SUITE_MOCK", "1")

    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)

    # Run sync with a large roadmap
    summary = suite.sync(
        dry_run=True, update=False, respect_status=False, preflight=False
    )

    # Should have processed all specs successfully
    assert summary["totals"]["specs"] == 12
    assert summary["totals"]["created"] == 12
