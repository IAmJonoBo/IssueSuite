from pathlib import Path

import pytest

from issuesuite.parser import ParseError, parse_issues

SIMPLE_MD = """\
# Roadmap

## [slug: first-feature]
```yaml
title: First Feature
body: |
  Line one\n  Line two
labels: [enhancement, P2-enhancement]
status: open
```

## [slug: second]
```yaml
title: Second Item
body: Second body line
labels: bug
milestone: M1
```
"""

MISSING_FENCE_MD = """\
# Only heading
## [slug: broken]
Title without fence
"""

LEGACY_NUMERIC_MD = """\
## 001 | Old style
Something
"""


def test_parse_happy_path(tmp_path: Path) -> None:
    md = tmp_path / 'ISSUES.md'
    md.write_text(SIMPLE_MD)
    specs = parse_issues(md.read_text().splitlines())
    expected_count = 2
    assert len(specs) == expected_count
    first = specs[0]
    assert first.external_id == 'first-feature'
    assert first.title == 'First Feature'
    assert 'enhancement' in first.labels
    assert first.body.startswith('<!-- issuesuite:slug=first-feature -->')
    # hash should be 16 hex chars
    hash_length = 16
    assert first.hash and len(first.hash) == hash_length


def test_parse_missing_fence_raises(tmp_path: Path) -> None:
    md = tmp_path / 'ISSUES.md'
    md.write_text(MISSING_FENCE_MD)
    with pytest.raises(ParseError):
        parse_issues(md.read_text().splitlines())


def test_parse_legacy_numeric_detected(tmp_path: Path) -> None:
    md = tmp_path / 'ISSUES.md'
    md.write_text(LEGACY_NUMERIC_MD)
    with pytest.raises(ParseError):
        parse_issues(md.read_text().splitlines())
