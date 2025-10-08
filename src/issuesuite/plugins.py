"""Plugin discovery and invocation utilities."""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import metadata
from typing import Any, cast

from .config import SuiteConfig

PLUGIN_GROUP = "issuesuite.plugins"
ENV_PLUGIN_SPEC = "ISSUESUITE_PLUGINS"


@dataclass(frozen=True)
class PluginContext:
    command: str
    config: SuiteConfig | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class PluginHook:
    name: str
    callback: Callable[[PluginContext], Any]


def _load_entry_point_plugins() -> list[PluginHook]:
    hooks: list[PluginHook] = []
    try:
        eps = metadata.entry_points()
    except Exception:  # pragma: no cover - importlib metadata edge case
        return hooks
    selected = getattr(eps, "select", None)
    entries: Iterable[Any]
    if callable(selected):
        entries = cast(Iterable[Any], selected(group=PLUGIN_GROUP))
    else:  # Python <3.10 compatibility path
        entries = cast(Iterable[Any], eps.get(PLUGIN_GROUP, []) if isinstance(eps, dict) else [])
    for ep in entries:
        try:
            obj = ep.load()
            if callable(obj):
                hooks.append(PluginHook(name=ep.name, callback=obj))
        except Exception:  # pragma: no cover - plugin load failures shouldn't crash
            continue
    return hooks


def _load_env_plugins() -> list[PluginHook]:
    spec = os.environ.get(ENV_PLUGIN_SPEC)
    if not spec:
        return []
    hooks: list[PluginHook] = []
    for raw_item in spec.split(","):
        item = raw_item.strip()
        if not item:
            continue
        module_name, _, attr = item.partition(":")
        if not module_name or not attr:
            continue
        try:
            module = importlib.import_module(module_name)
            callback = getattr(module, attr)
        except Exception:  # pragma: no cover - malformed plugin spec
            continue
        if callable(callback):
            hooks.append(PluginHook(name=f"env:{item}", callback=callback))
    return hooks


def load_plugins(cfg: SuiteConfig | None) -> list[PluginHook]:
    if cfg and not cfg.extensions_enabled:
        return []
    disabled = set(cfg.extensions_disabled) if cfg else set()
    hooks = _load_entry_point_plugins() + _load_env_plugins()
    filtered: list[PluginHook] = []
    for hook in hooks:
        if hook.name in disabled:
            continue
        filtered.append(hook)
    return filtered


def invoke_plugins(cfg: SuiteConfig | None, command: str, payload: dict[str, Any]) -> None:
    for hook in load_plugins(cfg):
        try:
            hook.callback(PluginContext(command=command, config=cfg, payload=payload))
        except Exception:  # pragma: no cover - plugins must not break core commands
            continue
