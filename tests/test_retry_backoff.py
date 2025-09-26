from __future__ import annotations

import subprocess  # isort:skip
import time  # isort:skip
from typing import Any  # isort:skip

from issuesuite.retry import RetryConfig, run_with_retries  # isort:skip

class DummyCalledProcessError(subprocess.CalledProcessError):
    def __init__(self, output: str, returncode: int = 1):
        super().__init__(returncode, cmd='gh api', output=output)


RETRY_AFTER_SECONDS: float = 7.0
FLOAT_TOL: float = 0.05  # generous tolerance for timing imprecision
TRANSIENT_FAILURE_LIMIT: int = 3  # number of attempts before success in second test
EXPECTED_RETRIES: int = 2  # sleeps expected given two transient failures


def test_retry_honors_retry_after(monkeypatch: Any) -> None:
    sleeps: list[float] = []

    def fake_sleep(sec: float) -> None:
        sleeps.append(sec)

    monkeypatch.setattr(time, 'sleep', fake_sleep)

    # first call raises with Retry-After, second succeeds
    state = {'count': 0}

    def fn() -> str:
        state['count'] += 1
        if state['count'] == 1:
            raise DummyCalledProcessError('Rate limit hit. Retry-After: 7')
        return 'ok'

    res = run_with_retries(fn, cfg=RetryConfig(attempts=3, base_sleep=0.01))
    assert res == 'ok'
    assert len(sleeps) == 1  # exactly one retry
    assert (RETRY_AFTER_SECONDS - FLOAT_TOL) <= sleeps[0] <= (RETRY_AFTER_SECONDS + FLOAT_TOL)


def test_retry_max_sleep_cap(monkeypatch: Any) -> None:
    sleeps: list[float] = []
    monkeypatch.setenv('ISSUESUITE_RETRY_MAX_SLEEP', '0.05')

    def fake_sleep(sec: float) -> None:
        sleeps.append(sec)

    monkeypatch.setattr(time, 'sleep', fake_sleep)

    state = {'count': 0}

    def fn() -> str:
        state['count'] += 1
        if state['count'] < TRANSIENT_FAILURE_LIMIT:
            raise DummyCalledProcessError('Secondary rate limit triggered')
        return 'done'

    res = run_with_retries(fn, cfg=RetryConfig(attempts=4, base_sleep=0.02))
    assert res == 'done'
    # Two sleeps, both should be <= cap
    assert len(sleeps) == EXPECTED_RETRIES
    assert all(s <= 0.05 + 1e-6 for s in sleeps)
