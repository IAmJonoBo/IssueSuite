from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class _Span:
    name: str
    attributes: dict[str, str] = field(default_factory=dict)

    def set_attribute(self, key: str, value: str) -> None:
        self.attributes[key] = value


class _Tracer:
    def __init__(self, service_name: str) -> None:
        self.service_name = service_name

    @contextmanager
    def start_as_current_span(self, name: str) -> Iterator[_Span]:
        span = _Span(name=name)
        yield span


class _TracerProvider:
    def __init__(self) -> None:
        self._tracers: dict[str, _Tracer] = {}

    def get_tracer(self, service_name: str) -> _Tracer:
        if service_name not in self._tracers:
            self._tracers[service_name] = _Tracer(service_name)
        return self._tracers[service_name]


_state: dict[str, _TracerProvider] = {"provider": _TracerProvider()}


def get_tracer(service_name: str) -> _Tracer:
    return _state["provider"].get_tracer(service_name)


def set_tracer_provider(provider: _TracerProvider) -> None:
    _state["provider"] = provider


def get_tracer_provider() -> _TracerProvider:
    return _state["provider"]


class TracerProvider(_TracerProvider):
    """Callable class matching the real OpenTelemetry API surface."""


__all__ = [
    "TracerProvider",
    "get_tracer",
    "get_tracer_provider",
    "set_tracer_provider",
]
