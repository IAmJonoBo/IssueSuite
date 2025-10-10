from pathlib import Path

import pytest

from issuesuite import IssueSuite, load_config
from issuesuite.plugins import PluginHook, invoke_plugins


def test_gh_auth_skips_when_cli_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """_gh_auth should not try to spawn the GitHub CLI when it is unavailable."""

    cfg_path = Path(__file__).resolve().parent.parent / "issue_suite.config.yaml"
    cfg = load_config(str(cfg_path))
    suite = IssueSuite(cfg)
    suite._mock = False

    monkeypatch.setattr("issuesuite.core.shutil.which", lambda _: None)

    def _fail(*_: object, **__: object) -> str:
        raise AssertionError(
            "subprocess.check_output should not be invoked when gh is absent"
        )

    monkeypatch.setattr("issuesuite.core.subprocess.check_output", _fail)

    assert suite._gh_auth() is False


def test_invoke_plugins_logs_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plugin failures should be logged so operators can diagnose them."""

    def _broken_plugin(
        context: object,
    ) -> None:  # pragma: no cover - intentional failure path
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "issuesuite.plugins.load_plugins",
        lambda cfg: [PluginHook(name="broken", callback=_broken_plugin)],
    )

    logged_messages: list[str] = []

    class _StubLogger:
        def exception(self, msg: str, *args: object, **kwargs: object) -> None:
            rendered = msg % args if args else msg
            logged_messages.append(rendered)

    monkeypatch.setattr("issuesuite.plugins.logger", _StubLogger())

    invoke_plugins(None, "sync", {"payload": True})

    assert logged_messages
    combined = "\n".join(logged_messages)
    assert "broken" in combined
