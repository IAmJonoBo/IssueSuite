from __future__ import annotations

from importlib import import_module
from typing import Any

import pytest


def test_issue_suite_dunder_all_exports() -> None:
    module = import_module("issuesuite")
    exported = set(module.__all__)
    expected = {
        "load_config",
        "SuiteConfig",
        "IssueSuite",
        "IssueSpec",
        "get_ai_context",
        "__version__",
    }
    assert expected <= exported


@pytest.mark.parametrize(
    "attribute, expected_type",
    [
        ("load_config", "function"),
        ("SuiteConfig", "type"),
        ("IssueSuite", "type"),
        ("IssueSpec", "type"),
    ],
)
def test_dunder_getattr_lazy_loading(attribute: str, expected_type: str) -> None:
    module = import_module("issuesuite")
    value: Any = getattr(module, attribute)
    if expected_type == "function":
        assert callable(value)
    else:
        assert isinstance(value, type)


def test_module_main_run_invokes_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    module = import_module("issuesuite.__main__")
    called: dict[str, Any] = {}

    def fake_main(argv: Any) -> int:
        called["argv"] = argv
        return 123

    monkeypatch.setattr(module, "main", fake_main)

    result = module.run()
    assert called["argv"] is None
    assert result == 123
