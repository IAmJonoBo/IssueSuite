from __future__ import annotations

import subprocess
import time

from issuesuite import retry

# Constants for test expectations
FIRST_SUCCESS_ATTEMPT = 2  # transient once then success
EXPECTED_RETRY_COUNT = 2  # total attempts when one retry occurs


class DummyCalledProcessError(subprocess.CalledProcessError):
    """Helper to craft subprocess errors with custom output."""

    def __init__(self, output: str):
        super().__init__(returncode=1, cmd=['gh', 'dummy'])
        self.output = output


def test_is_transient_tokens():
    assert retry.is_transient('Rate Limit exceeded')
    assert retry.is_transient('secondary rate limit triggered')
    assert retry.is_transient('ABUSE DETECTION mechanism')
    assert not retry.is_transient('some other error')


def test_run_with_retries_transient_then_success():
    attempts: list[int] = []

    def fn():
        attempts.append(1)
        if len(attempts) < FIRST_SUCCESS_ATTEMPT:
            raise DummyCalledProcessError('rate limit exceeded temporarily')
        return 'ok'

    cfg = retry.RetryConfig(attempts=3, base_sleep=0.01)
    start = time.time()
    result = retry.run_with_retries(fn, cfg=cfg)
    elapsed = time.time() - start
    assert result == 'ok'
    assert len(attempts) == EXPECTED_RETRY_COUNT
    assert elapsed >= 0.0


def test_run_with_retries_non_transient():
    attempts: list[int] = []

    def fn():
        attempts.append(1)
        raise DummyCalledProcessError('syntax error from gh cli')

    cfg = retry.RetryConfig(attempts=4, base_sleep=0.01)
    try:
        retry.run_with_retries(fn, cfg=cfg)
    except subprocess.CalledProcessError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError('Expected CalledProcessError')
    assert len(attempts) == 1


def test_run_with_retries_transient_exhausts():
    attempts: list[int] = []

    def fn():
        attempts.append(1)
        raise DummyCalledProcessError('secondary rate limit inner error')

    cfg = retry.RetryConfig(attempts=3, base_sleep=0.0)
    try:
        retry.run_with_retries(fn, cfg=cfg)
    except subprocess.CalledProcessError:
        pass
    else:  # pragma: no cover
        raise AssertionError('Expected CalledProcessError')
    assert len(attempts) == cfg.attempts
