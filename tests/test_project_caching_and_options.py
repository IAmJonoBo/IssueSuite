import os
from types import SimpleNamespace

from issuesuite.project import GitHubProjectAssigner, ProjectConfig, build_project_assigner


def test_project_field_cache_reuse(monkeypatch, tmp_path):  # type: ignore
    """Second assign should not refetch fields (cache hit)."""
    monkeypatch.setenv('ISSUES_SUITE_MOCK', '1')
    os.chdir(tmp_path)
    cfg = ProjectConfig(enabled=True, number=42, field_mappings={'labels': 'Status'})
    assigner = build_project_assigner(cfg)
    assert isinstance(assigner, GitHubProjectAssigner)

    spec = SimpleNamespace(labels=['Todo'])
    assigner.assign(1, spec)
    # After first assign cache populated
    assert assigner._field_cache
    # Capture identity of dict to ensure reuse
    cache_id = id(assigner._field_cache)
    assigner.assign(2, spec)
    assert id(assigner._field_cache) == cache_id


def test_single_select_option_name_case_insensitive(monkeypatch, tmp_path):  # type: ignore
    """Lower/upper/mixed case option value should resolve to option id in mock mode."""
    monkeypatch.setenv('ISSUES_SUITE_MOCK', '1')
    os.chdir(tmp_path)
    cfg = ProjectConfig(enabled=True, number=1, field_mappings={'labels': 'Status'})
    assigner = build_project_assigner(cfg)
    assert isinstance(assigner, GitHubProjectAssigner)

    # Provide lowercase version of 'Todo' to test mapping
    spec = SimpleNamespace(labels=['todo'])
    assigner.assign(10, spec)
    # Validate that cache exists and contains the expected option mapping
    status_field = assigner._field_cache.get('Status')
    assert status_field and 'options' in status_field
    # Ensure expected option id present
    assert 'opt_status_todo' in status_field['options'].values()
