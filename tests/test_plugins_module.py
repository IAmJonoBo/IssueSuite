from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

from issuesuite import plugins


def test_load_plugins_respects_extensions_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        plugins,
        "_load_entry_point_plugins",
        lambda: [plugins.PluginHook("entry", lambda ctx: None)],
    )
    module = ModuleType("fake_mod")

    def env_cb(
        ctx: plugins.PluginContext,
    ) -> None:  # pragma: no cover - invoked via invoke_plugins
        raise AssertionError("should not run")

    module.plugin_cb = env_cb  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fake_mod", module)
    monkeypatch.setenv(plugins.ENV_PLUGIN_SPEC, "fake_mod:plugin_cb")

    cfg = SimpleNamespace(extensions_enabled=True, extensions_disabled=("entry",))
    hooks = plugins.load_plugins(cfg)
    assert all(hook.name != "entry" for hook in hooks)

    monkeypatch.delenv(plugins.ENV_PLUGIN_SPEC, raising=False)


def test_invoke_plugins_runs_entry_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def entry_callback(ctx: plugins.PluginContext) -> None:
        calls.append(("entry", ctx.command))

    def env_callback(ctx: plugins.PluginContext) -> None:
        calls.append(("env", ctx.command))

    monkeypatch.setattr(
        plugins,
        "_load_entry_point_plugins",
        lambda: [plugins.PluginHook(name="entry", callback=entry_callback)],
    )
    module = ModuleType("fake_env_mod")
    module.plugin_cb = env_callback  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fake_env_mod", module)
    monkeypatch.setenv(plugins.ENV_PLUGIN_SPEC, "fake_env_mod:plugin_cb")

    cfg = SimpleNamespace(extensions_enabled=True, extensions_disabled=())
    hooks = plugins.load_plugins(cfg)
    assert {hook.name for hook in hooks} == {"entry", "env:fake_env_mod:plugin_cb"}

    plugins.invoke_plugins(cfg, "sync", {"ok": True})
    assert ("entry", "sync") in calls and ("env", "sync") in calls

    monkeypatch.delenv(plugins.ENV_PLUGIN_SPEC, raising=False)
