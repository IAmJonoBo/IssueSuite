import os

from issuesuite import get_ai_context, load_config

SAMPLE_ISSUES = """\
## [slug: acp-alpha]
```yaml
title: ACP Alpha
labels: [x]
status: open
body: |
  Body A
```

## [slug: acp-beta]
```yaml
title: ACP Beta
labels: [y]
status: closed
body: |
  Body B
```
"""

MIN_CONFIG = """\
version: 1
source:
  file: ISSUES.md
  id_pattern: "^[a-z0-9][a-z0-9-_]*$"
  milestone_required: false
behavior:
  truncate_body_diff: 40
ai:
  schema_version: 1
"""


EXPECTED_COUNT = 2


def test_get_ai_context_structure(tmp_path):  # type: ignore[no-untyped-def]
    (tmp_path / 'ISSUES.md').write_text(SAMPLE_ISSUES)
    (tmp_path / 'issue_suite.config.yaml').write_text(MIN_CONFIG)

    env = os.environ.copy()
    env['ISSUES_SUITE_MOCK'] = '1'

    cfg = load_config(tmp_path / 'issue_suite.config.yaml')
    ctx = get_ai_context(cfg, preview=2)

    # Required top-level keys
    for key in [
        'schemaVersion',
        'type',
        'spec_count',
        'preview',
        'mapping',
        'config',
        'env',
        'recommended',
    ]:
        assert key in ctx, f"Missing key: {key}"

    assert ctx['type'] == 'issuesuite.ai-context'
    assert ctx['spec_count'] == EXPECTED_COUNT
    assert len(ctx['preview']) == EXPECTED_COUNT

    # Mapping shape sanity
    mapping = ctx['mapping']
    assert 'present' in mapping and 'size' in mapping
    assert isinstance(mapping['present'], bool)
    assert isinstance(mapping['size'], int)

    # Recommended section sanity: ensure core recommendation keys present
    for rec_key in ['safe_sync', 'export', 'summary', 'usage', 'env']:
        assert rec_key in ctx['recommended']
