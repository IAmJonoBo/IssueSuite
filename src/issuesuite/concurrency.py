"""Concurrency support for IssueSuite.

Provides async processing capabilities for large roadmaps with
configurable parallelism and batching.
"""

from __future__ import annotations

import asyncio
import functools
import json
import subprocess
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from types import TracebackType
from typing import Any, TypeVar

from .logging import get_logger

T = TypeVar('T')
R = TypeVar('R')


class ConcurrencyConfig:
    """Configuration for concurrency settings."""

    def __init__(self, enabled: bool = False, max_workers: int = 4, batch_size: int = 10):
        self.enabled = enabled
        self.max_workers = max_workers
        self.batch_size = batch_size


class AsyncGitHubClient:
    """Async wrapper for GitHub CLI operations."""

    def __init__(self, concurrency_config: ConcurrencyConfig, mock: bool = False):
        self.config = concurrency_config
        self.mock = mock
        self.logger = get_logger()
        self._executor: ThreadPoolExecutor | None = None

    def __enter__(self) -> AsyncGitHubClient:
        if self.config.enabled:
            self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._executor:
            self._executor.shutdown(wait=True)

    async def __aenter__(self) -> AsyncGitHubClient:
        # Delegate to sync __enter__ to avoid duplicate logic
        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        # Delegate to sync __exit__ to avoid duplicate logic
        self.__exit__(exc_type, exc_val, exc_tb)

    async def _run_command_async(self, cmd: list[str]) -> tuple[bool, str]:
        """Run a command asynchronously."""
        if self.mock:
            # Simulate some work
            await asyncio.sleep(0.01)
            return True, f"MOCK: {' '.join(cmd)}"

        if not self.config.enabled or not self._executor:
            # Fallback to background thread to avoid blocking event loop
            loop = asyncio.get_event_loop()
            try:
                result = await loop.run_in_executor(
                    None,
                    functools.partial(
                        subprocess.run,
                        cmd,
                        capture_output=True,
                        text=True,
                        check=True,
                    ),
                )
                return True, result.stdout
            except subprocess.CalledProcessError as e:
                return False, f"Error: {e}"

        # Run in thread pool
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                functools.partial(subprocess.run, cmd, capture_output=True, text=True, check=True),
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, f"Error: {e}"

    async def create_issue_async(
        self, title: str, body: str, labels: list[str] | None = None, milestone: str | None = None
    ) -> tuple[bool, str]:
        """Create an issue asynchronously."""
        cmd = ['gh', 'issue', 'create', '--title', title, '--body', body]
        if labels:
            cmd += ['--label', ','.join(labels)]
        if milestone:
            cmd += ['--milestone', milestone]

        self.logger.debug("Creating issue async", title=title[:50])
        return await self._run_command_async(cmd)

    async def update_issue_async(
        self,
        issue_number: int,
        body: str | None = None,
        labels: list[str] | None = None,
        milestone: str | None = None,
    ) -> tuple[bool, str]:
        """Update an issue asynchronously."""
        success = True
        messages = []

        if labels:
            cmd = ['gh', 'issue', 'edit', str(issue_number), '--add-label', ','.join(labels)]
            result, msg = await self._run_command_async(cmd)
            success = success and result
            messages.append(msg)

        if milestone:
            cmd = ['gh', 'issue', 'edit', str(issue_number), '--milestone', milestone]
            result, msg = await self._run_command_async(cmd)
            success = success and result
            messages.append(msg)

        if body:
            cmd = [
                'gh',
                'api',
                f'repos/:owner/:repo/issues/{issue_number}',
                '--method',
                'PATCH',
                '-f',
                f'body={body}',
            ]
            result, msg = await self._run_command_async(cmd)
            success = success and result
            messages.append(msg)

        return success, '\n'.join(messages)

    async def close_issue_async(self, issue_number: int) -> tuple[bool, str]:
        """Close an issue asynchronously."""
        cmd = ['gh', 'issue', 'close', str(issue_number)]
        return await self._run_command_async(cmd)

    async def get_issues_async(self) -> tuple[bool, list[dict[str, Any]]]:
        """Get all issues asynchronously."""
        cmd = [
            'gh',
            'issue',
            'list',
            '--state',
            'all',
            '--limit',
            '1000',
            '--json',
            'number,title,body,labels,milestone,state',
        ]

        success, output = await self._run_command_async(cmd)
        if success and not self.mock:
            try:
                issues = json.loads(output)
                return True, issues
            except json.JSONDecodeError:
                return False, []
        elif self.mock:
            # Return mock issues
            return True, []
        else:
            return False, []


class ConcurrentProcessor:
    """Processes issue specs concurrently."""

    def __init__(self, concurrency_config: ConcurrencyConfig, mock: bool = False):
        self.config = concurrency_config
        self.mock = mock
        self.logger = get_logger()

    async def process_specs_concurrent(
        self,
        specs: list[Any],
        processor_func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> list[Any]:
        """Process specs concurrently using async processing."""
        if not self.config.enabled or len(specs) <= 1:
            # Fallback to sequential processing
            return [processor_func(spec, *args, **kwargs) for spec in specs]

        # Process in batches to avoid overwhelming the API
        results = []
        batch_size = self.config.batch_size

        self.logger.log_operation(
            "concurrent_processing_start",
            spec_count=len(specs),
            batch_size=batch_size,
            max_workers=self.config.max_workers,
        )

        start_time = time.perf_counter()

        for i in range(0, len(specs), batch_size):
            batch = specs[i : i + batch_size]
            batch_results = await self._process_batch_async(batch, processor_func, *args, **kwargs)
            results.extend(batch_results)

            # Brief pause between batches to be respectful to GitHub API
            if i + batch_size < len(specs):
                await asyncio.sleep(0.1)

        duration_ms = (time.perf_counter() - start_time) * 1000
        self.logger.log_performance(
            "concurrent_processing", duration_ms, spec_count=len(specs), results_count=len(results)
        )

        return results

    async def _process_batch_async(
        self,
        batch: list[Any],
        processor_func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> list[Any]:
        """Process a batch of specs asynchronously."""
        if not self.config.enabled:
            return [processor_func(spec, *args, **kwargs) for spec in batch]

        # Create tasks for concurrent execution
        tasks = []
        for spec in batch:
            task = asyncio.create_task(
                self._run_processor_async(processor_func, spec, *args, **kwargs)
            )
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        processed_results: list[Any] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.log_error(f"Error processing spec {batch[i]}", error=str(result))
                # Return a default failure result
                processed_results.append({'error': str(result), 'spec': batch[i]})
            else:
                processed_results.append(result)

        return processed_results

    async def _run_processor_async(
        self,
        processor_func: Callable[..., Any],
        spec: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Run a processor function asynchronously."""
        # If the processor function is already async, run it directly
        if asyncio.iscoroutinefunction(processor_func):
            return await processor_func(spec, *args, **kwargs)

        # Otherwise, run in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, processor_func, spec, *args, **kwargs)


def create_async_github_client(config: ConcurrencyConfig, mock: bool = False) -> AsyncGitHubClient:
    """Factory function to create async GitHub client."""
    return AsyncGitHubClient(config, mock)


def create_concurrent_processor(
    config: ConcurrencyConfig, mock: bool = False
) -> ConcurrentProcessor:
    """Factory function to create concurrent processor."""
    return ConcurrentProcessor(config, mock)


async def run_concurrent_sync(
    specs: list[Any],
    processor_func: Callable[..., Any],
    concurrency_config: ConcurrencyConfig,
    mock: bool = False,
    *args: Any,
    **kwargs: Any,
) -> list[Any]:
    """Convenience function to run concurrent sync."""
    processor = create_concurrent_processor(concurrency_config, mock)
    return await processor.process_specs_concurrent(specs, processor_func, *args, **kwargs)


# Utility functions for backward compatibility
def enable_concurrency_for_large_roadmaps(spec_count: int, threshold: int = 10) -> bool:
    """Determine if concurrency should be enabled based on roadmap size."""
    return spec_count >= threshold


def get_optimal_worker_count(spec_count: int, max_workers: int = 4) -> int:
    """Get optimal worker count based on spec count."""
    small_threshold = 5
    medium_threshold = 20
    large_threshold = 50
    if spec_count <= small_threshold:
        return 1
    elif spec_count <= medium_threshold:
        return min(2, max_workers)
    elif spec_count <= large_threshold:
        return min(3, max_workers)
    else:
        return max_workers
