from issuesuite.project import NoopProjectAssigner, ProjectConfig, build_project_assigner


def test_build_project_assigner_disabled():
    cfg = ProjectConfig(enabled=False, number=None, field_mappings={})
    assigner = build_project_assigner(cfg)
    assert isinstance(assigner, NoopProjectAssigner)


def test_noop_assigner_does_nothing():
    cfg = ProjectConfig(enabled=False, number=None, field_mappings={})
    assigner = build_project_assigner(cfg)
    # Should not raise when calling assign
    assigner.assign(123, object())
