import asyncio
import os
import pytest
from unittest.mock import MagicMock, patch
from issuesuite.concurrency import (
    ConcurrencyConfig, AsyncGitHubClient, ConcurrentProcessor,
    create_async_github_client, create_concurrent_processor,
    enable_concurrency_for_large_roadmaps, get_optimal_worker_count,
    run_concurrent_sync
)


def test_concurrency_config():
    """Test ConcurrencyConfig initialization."""
    config = ConcurrencyConfig(enabled=True, max_workers=8, batch_size=5)
    
    assert config.enabled is True
    assert config.max_workers == 8
    assert config.batch_size == 5


def test_concurrency_config_defaults():
    """Test ConcurrencyConfig with defaults."""
    config = ConcurrencyConfig()
    
    assert config.enabled is False
    assert config.max_workers == 4
    assert config.batch_size == 10


@pytest.mark.asyncio
async def test_async_github_client_mock():
    """Test AsyncGitHubClient in mock mode."""
    config = ConcurrencyConfig(enabled=True, max_workers=2)
    
    with create_async_github_client(config, mock=True) as client:
        # Test create issue
        success, msg = await client.create_issue_async("Test Issue", "Test body", ["bug"], "Sprint 1")
        assert success is True
        assert "MOCK" in msg
        
        # Test update issue
        success, msg = await client.update_issue_async(123, "New body", ["enhancement"], "Sprint 2")
        assert success is True
        assert "MOCK" in msg
        
        # Test close issue
        success, msg = await client.close_issue_async(456)
        assert success is True
        assert "MOCK" in msg
        
        # Test get issues
        success, issues = await client.get_issues_async()
        assert success is True
        assert isinstance(issues, list)


@pytest.mark.asyncio
async def test_async_github_client_disabled_concurrency():
    """Test AsyncGitHubClient with concurrency disabled."""
    config = ConcurrencyConfig(enabled=False)
    
    with patch('subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = 'success'
        mock_run.return_value = mock_result
        
        with create_async_github_client(config, mock=False) as client:
            success, msg = await client.create_issue_async("Test", "Body")
            assert success is True
            assert msg == 'success'
            mock_run.assert_called_once()


def test_concurrent_processor_creation():
    """Test concurrent processor creation."""
    config = ConcurrencyConfig(enabled=True, max_workers=4)
    processor = create_concurrent_processor(config, mock=True)
    
    assert isinstance(processor, ConcurrentProcessor)
    assert processor.config.enabled is True
    assert processor.config.max_workers == 4
    assert processor.mock is True


@pytest.mark.asyncio
async def test_concurrent_processor_sequential_fallback():
    """Test concurrent processor falls back to sequential for small datasets."""
    config = ConcurrencyConfig(enabled=True, max_workers=4)
    processor = ConcurrentProcessor(config, mock=True)
    
    def simple_processor(item):
        return f"processed_{item}"
    
    items = ["item1"]  # Single item should use sequential processing
    results = await processor.process_specs_concurrent(items, simple_processor)
    
    assert len(results) == 1
    assert results[0] == "processed_item1"


@pytest.mark.asyncio
async def test_concurrent_processor_batch_processing():
    """Test concurrent processor with batch processing."""
    config = ConcurrencyConfig(enabled=True, max_workers=2, batch_size=2)
    processor = ConcurrentProcessor(config, mock=True)
    
    def simple_processor(item):
        return f"processed_{item}"
    
    items = ["item1", "item2", "item3", "item4", "item5"]
    results = await processor.process_specs_concurrent(items, simple_processor)
    
    assert len(results) == 5
    assert all(f"processed_item{i+1}" in results for i in range(5))


@pytest.mark.asyncio
async def test_concurrent_processor_error_handling():
    """Test concurrent processor handles errors gracefully."""
    config = ConcurrencyConfig(enabled=True, max_workers=2)
    processor = ConcurrentProcessor(config, mock=True)
    
    def error_processor(item):
        if item == "error_item":
            raise ValueError("Test error")
        return f"processed_{item}"
    
    items = ["item1", "error_item", "item3"]
    results = await processor.process_specs_concurrent(items, error_processor)
    
    assert len(results) == 3
    assert results[0] == "processed_item1"
    assert isinstance(results[1], dict) and 'error' in results[1]
    assert results[2] == "processed_item3"


@pytest.mark.asyncio
async def test_run_concurrent_sync():
    """Test convenience function for concurrent sync."""
    config = ConcurrencyConfig(enabled=True, max_workers=2)
    
    def processor(item):
        return f"synced_{item}"
    
    items = ["spec1", "spec2", "spec3"]
    results = await run_concurrent_sync(items, processor, config, mock=True)
    
    assert len(results) == 3
    assert all(f"synced_spec{i+1}" in results for i in range(3))


def test_enable_concurrency_for_large_roadmaps():
    """Test concurrency enablement logic."""
    assert enable_concurrency_for_large_roadmaps(5) is False
    assert enable_concurrency_for_large_roadmaps(10) is True
    assert enable_concurrency_for_large_roadmaps(50) is True
    
    # Custom threshold
    assert enable_concurrency_for_large_roadmaps(8, threshold=5) is True
    assert enable_concurrency_for_large_roadmaps(3, threshold=5) is False


def test_get_optimal_worker_count():
    """Test optimal worker count calculation."""
    assert get_optimal_worker_count(3) == 1
    assert get_optimal_worker_count(10) == 2
    assert get_optimal_worker_count(30) == 3
    assert get_optimal_worker_count(100) == 4
    
    # With custom max workers
    assert get_optimal_worker_count(100, max_workers=8) == 8
    assert get_optimal_worker_count(30, max_workers=2) == 2


@pytest.mark.asyncio
async def test_async_github_client_context_manager():
    """Test AsyncGitHubClient context manager."""
    config = ConcurrencyConfig(enabled=True, max_workers=2)
    
    async with create_async_github_client(config, mock=True) as client:
        assert client._executor is not None
        success, _ = await client.create_issue_async("Test", "Body")
        assert success is True
    
    # After context exit, executor should be shut down
    # Note: We can't easily test the executor state since it's internal


@pytest.mark.asyncio
async def test_concurrent_processor_disabled():
    """Test concurrent processor with concurrency disabled."""
    config = ConcurrencyConfig(enabled=False)
    processor = ConcurrentProcessor(config, mock=True)
    
    def simple_processor(item):
        return f"processed_{item}"
    
    items = ["item1", "item2", "item3"]
    results = await processor.process_specs_concurrent(items, simple_processor)
    
    # Should fall back to sequential processing
    assert len(results) == 3
    assert all(f"processed_item{i+1}" in results for i in range(3))


@pytest.mark.asyncio
async def test_async_coroutine_processor():
    """Test concurrent processor with async processor function."""
    config = ConcurrencyConfig(enabled=True, max_workers=2)
    processor = ConcurrentProcessor(config, mock=True)
    
    async def async_processor(item):
        await asyncio.sleep(0.01)  # Simulate async work
        return f"async_processed_{item}"
    
    items = ["item1", "item2"]
    results = await processor.process_specs_concurrent(items, async_processor)
    
    assert len(results) == 2
    assert all("async_processed_" in str(result) for result in results)