"""Concurrency tests (synchronous wrappers).

Converted to manual asyncio.run wrappers to avoid reliance on pytest-asyncio
plugin loading in CI (which was causing skips / stalls). We intentionally keep
literal numbers for readability and disable ruff rules for this file.
"""

# ruff: noqa

import asyncio
from typing import Any, List
from unittest.mock import MagicMock, patch

from issuesuite.concurrency import (
    ConcurrencyConfig,
    ConcurrentProcessor,
    create_async_github_client,
    create_concurrent_processor,
    enable_concurrency_for_large_roadmaps,
    get_optimal_worker_count,
    run_concurrent_sync,
)


def test_concurrency_config() -> None:
    config = ConcurrencyConfig(enabled=True, max_workers=8, batch_size=5)
    assert config.enabled is True
    assert config.max_workers == 8
    assert config.batch_size == 5


def test_concurrency_config_defaults() -> None:
    config = ConcurrencyConfig()
    assert config.enabled is False
    assert config.max_workers == 4
    assert config.batch_size == 10


def test_async_github_client_mock() -> None:
    async def _run() -> None:
        config = ConcurrencyConfig(enabled=True, max_workers=2)
        with create_async_github_client(config, mock=True) as client:
            success, msg = await client.create_issue_async(
                "Test Issue", "Test body", ["bug"], "Sprint 1"
            )
            assert success and "MOCK" in msg
            success, msg = await client.update_issue_async(
                123, "New body", ["enhancement"], "Sprint 2"
            )
            assert success and "MOCK" in msg
            success, msg = await client.close_issue_async(456)
            assert success and "MOCK" in msg
            success, issues = await client.get_issues_async()
            assert success and isinstance(issues, list)

    asyncio.run(_run())


def test_async_github_client_disabled_concurrency() -> None:
    async def _run() -> None:
        config = ConcurrencyConfig(enabled=False)
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "success"
            mock_run.return_value = mock_result
            with create_async_github_client(config, mock=False) as client:
                success, msg = await client.create_issue_async("Test", "Body")
                assert success and msg == "success"
                mock_run.assert_called_once()

    asyncio.run(_run())


def test_concurrent_processor_creation() -> None:
    config = ConcurrencyConfig(enabled=True, max_workers=4)
    processor = create_concurrent_processor(config, mock=True)
    assert isinstance(processor, ConcurrentProcessor)
    assert processor.config.enabled is True
    assert processor.config.max_workers == 4
    assert processor.mock is True


def test_concurrent_processor_sequential_fallback() -> None:
    async def _run() -> None:
        config = ConcurrencyConfig(enabled=True, max_workers=4)
        processor = ConcurrentProcessor(config, mock=True)

        def simple_processor(item: str) -> str:
            return f"processed_{item}"

        items = ["item1"]
        results = await processor.process_specs_concurrent(items, simple_processor)
        assert len(results) == 1 and results[0] == "processed_item1"

    asyncio.run(_run())


def test_concurrent_processor_batch_processing() -> None:
    async def _run() -> None:
        config = ConcurrencyConfig(enabled=True, max_workers=2, batch_size=2)
        processor = ConcurrentProcessor(config, mock=True)

        def simple_processor(item: str) -> str:
            return f"processed_{item}"

        items = ["item1", "item2", "item3", "item4", "item5"]
        results = await processor.process_specs_concurrent(items, simple_processor)
        assert len(results) == 5 and all(
            f"processed_item{i + 1}" in results for i in range(5)
        )

    asyncio.run(_run())


def test_concurrent_processor_error_handling() -> None:
    async def _run() -> None:
        config = ConcurrencyConfig(enabled=True, max_workers=2)
        processor = ConcurrentProcessor(config, mock=True)

        def error_processor(item: str) -> Any:
            if item == "error_item":
                raise ValueError("Test error")
            return f"processed_{item}"

        items = ["item1", "error_item", "item3"]
        results = await processor.process_specs_concurrent(items, error_processor)
        assert len(results) == 3
        assert results[0] == "processed_item1"
        assert isinstance(results[1], dict) and "error" in results[1]
        assert results[2] == "processed_item3"

    asyncio.run(_run())


def test_run_concurrent_sync() -> None:
    async def _run() -> None:
        config = ConcurrencyConfig(enabled=True, max_workers=2)

        def processor(item: str) -> str:
            return f"synced_{item}"

        items = ["spec1", "spec2", "spec3"]
        results = await run_concurrent_sync(items, processor, config, mock=True)
        assert len(results) == 3 and all(
            f"synced_spec{i + 1}" in results for i in range(3)
        )

    asyncio.run(_run())


def test_enable_concurrency_for_large_roadmaps() -> None:
    assert enable_concurrency_for_large_roadmaps(5) is False
    assert enable_concurrency_for_large_roadmaps(10) is True
    assert enable_concurrency_for_large_roadmaps(50) is True
    assert enable_concurrency_for_large_roadmaps(8, threshold=5) is True
    assert enable_concurrency_for_large_roadmaps(3, threshold=5) is False


def test_get_optimal_worker_count() -> None:
    assert get_optimal_worker_count(3) == 1
    assert get_optimal_worker_count(10) == 2
    assert get_optimal_worker_count(30) == 3
    assert get_optimal_worker_count(100) == 4
    assert get_optimal_worker_count(100, max_workers=8) == 8
    assert get_optimal_worker_count(30, max_workers=2) == 2


def test_async_github_client_context_manager() -> None:
    async def _run() -> None:
        config = ConcurrencyConfig(enabled=True, max_workers=2)
        async with create_async_github_client(config, mock=True) as client:
            assert client._executor is not None
            success, _ = await client.create_issue_async("Test", "Body")
            assert success is True

    asyncio.run(_run())


def test_concurrent_processor_disabled() -> None:
    async def _run() -> None:
        config = ConcurrencyConfig(enabled=False)
        processor = ConcurrentProcessor(config, mock=True)

        def simple_processor(item: str) -> str:
            return f"processed_{item}"

        items = ["item1", "item2", "item3"]
        results = await processor.process_specs_concurrent(items, simple_processor)
        assert len(results) == 3 and all(
            f"processed_item{i + 1}" in results for i in range(3)
        )

    asyncio.run(_run())


def test_async_coroutine_processor() -> None:
    async def _run() -> None:
        config = ConcurrencyConfig(enabled=True, max_workers=2)
        processor = ConcurrentProcessor(config, mock=True)

        async def async_processor(item: str) -> str:
            await asyncio.sleep(0.01)
            return f"async_processed_{item}"

        items = ["item1", "item2"]
        results = await processor.process_specs_concurrent(items, async_processor)
        assert len(results) == 2 and all("async_processed_" in str(r) for r in results)

    asyncio.run(_run())
