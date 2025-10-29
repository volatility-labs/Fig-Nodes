"""
Generic API rate limiter service.

Provides rate limiting functionality to prevent exceeding API request limits.
Uses a sliding window approach to track requests and automatically throttles
when approaching the rate limit.

Also provides a generic worker pool pattern for concurrent processing with rate limiting.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class RateLimiter:
    """
    Simple rate limiter to stay under API request limits.

    Tracks requests within a rolling time window and automatically throttles
    when approaching the configured limit. Thread-safe for concurrent use.

    Example:
        ```python
        rate_limiter = RateLimiter(max_per_second=100)

        async def make_request():
            await rate_limiter.acquire()
            # Make your API request here
            return await api_call()
        ```
    """

    def __init__(self, max_per_second: int = 100):
        """
        Initialize the rate limiter.

        Args:
            max_per_second: Maximum number of requests allowed per second.
                           Defaults to 100 for Polygon API compatibility.
        """
        self.max_per_second = max_per_second
        self.requests: list[float] = []
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Wait if necessary to stay under the rate limit.

        Call this method before making an API request. It will automatically
        sleep if needed to ensure the rate limit is not exceeded.

        Raises:
            RuntimeError: If max_per_second is less than 1.
        """
        if self.max_per_second < 1:
            raise RuntimeError("max_per_second must be at least 1")

        async with self.lock:
            now = time.time()

            # Remove requests older than 1 second
            self.requests = [req_time for req_time in self.requests if now - req_time < 1.0]

            # If we're at the limit, wait until we can make another request
            if len(self.requests) >= self.max_per_second:
                oldest_request = min(self.requests)
                sleep_time = 1.0 - (now - oldest_request)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    # Refresh the list after sleeping
                    now = time.time()
                    self.requests = [req_time for req_time in self.requests if now - req_time < 1.0]

            # Record this request
            self.requests.append(now)

    def reset(self) -> None:
        """
        Reset the rate limiter, clearing all tracked requests.

        Useful for testing or when you need to reset the limiter state.
        """
        self.requests.clear()

    def get_current_rate(self) -> float:
        """
        Get the current requests per second based on tracked requests.

        Returns:
            Current requests per second as a float.
        """
        now = time.time()
        recent_requests = [req_time for req_time in self.requests if now - req_time < 1.0]
        return len(recent_requests)


async def process_with_worker_pool(
    items: list[T],
    worker_func: Callable[[T], Awaitable[R]],
    rate_limiter: RateLimiter,
    max_concurrent: int = 5,
    progress_callback: Callable[[float, str], None] | None = None,
    stop_flag: Callable[[], bool] | None = None,
    logger_instance: logging.Logger | None = None,
) -> list[R]:
    """
    Process items concurrently using a worker pool with rate limiting.

    Creates multiple worker tasks that pull items from a queue, acquire rate limits,
    and process items concurrently. Handles cancellation and errors gracefully.

    Args:
        items: List of items to process
        worker_func: Async function that processes a single item and returns a result
        rate_limiter: RateLimiter instance to control API request rate
        max_concurrent: Maximum number of concurrent workers (default: 5)
        progress_callback: Optional callback(progress: float, text: str) for progress updates
        stop_flag: Optional callable that returns True if processing should stop
        logger_instance: Optional logger instance for debug messages

    Returns:
        List of results from worker_func (order may not match input order)

    Raises:
        asyncio.CancelledError: If processing is cancelled
    """
    if not items:
        return []

    if logger_instance is None:
        logger_instance = logger

    total_items = len(items)
    results: list[R] = []
    completed_count = 0
    result_lock = asyncio.Lock()

    # Use a bounded worker pool to avoid creating one task per item
    queue: asyncio.Queue[T] = asyncio.Queue()
    for item in items:
        queue.put_nowait(item)

    async def worker(worker_id: int):
        nonlocal completed_count
        while True:
            # Check for cancellation before processing next item
            if stop_flag and stop_flag():
                logger_instance.debug(f"Worker {worker_id} stopped due to stop flag")
                break

            try:
                try:
                    item = queue.get_nowait()
                except asyncio.QueueEmpty:
                    logger_instance.debug(f"Worker {worker_id} queue empty, finishing")
                    break

                try:
                    # Respect rate limit
                    await rate_limiter.acquire()

                    # Check for cancellation again after rate limiting
                    if stop_flag and stop_flag():
                        logger_instance.debug(f"Worker {worker_id} stopped after rate limiting")
                        break

                    # Emit progress to reflect work starting
                    if progress_callback:
                        try:
                            progress_pre = (
                                (completed_count / total_items) * 100 if total_items else 0.0
                            )
                            progress_text_pre = f"{completed_count}/{total_items}"
                            progress_callback(progress_pre, progress_text_pre)
                        except Exception:
                            logger_instance.debug("Progress pre-update failed; continuing")

                    # Process item with error handling
                    try:
                        result = await worker_func(item)
                        async with result_lock:
                            results.append(result)
                            completed_count += 1

                        if progress_callback:
                            try:
                                progress = (completed_count / total_items) * 100
                                progress_text = f"{completed_count}/{total_items}"
                                progress_callback(progress, progress_text)
                            except Exception:
                                logger_instance.debug("Progress update failed; continuing")
                    except asyncio.CancelledError:
                        raise  # Propagate cancellation
                    except Exception as e:
                        logger_instance.error(
                            f"Error processing item {item}: {str(e)}", exc_info=True
                        )
                        # Continue without adding result, but still increment count
                        async with result_lock:
                            completed_count += 1
                            if progress_callback:
                                try:
                                    progress = (completed_count / total_items) * 100
                                    progress_text = f"{completed_count}/{total_items}"
                                    progress_callback(progress, progress_text)
                                except Exception:
                                    pass
                finally:
                    queue.task_done()
            except asyncio.CancelledError:
                # Also catch cancellations from rate limiter or queue ops
                raise

    # Create worker tasks
    effective_concurrency = min(max_concurrent, total_items)
    workers = [asyncio.create_task(worker(i)) for i in range(effective_concurrency)]

    # Gather workers: swallow regular exceptions to allow partial success, but
    # propagate cancellations to honor caller's intent.
    if workers:
        worker_results = await asyncio.gather(*workers, return_exceptions=True)
        for res in worker_results:
            if isinstance(res, asyncio.CancelledError):
                # Re-raise cancellation so upstream can handle it
                raise res
            if isinstance(res, Exception):
                logger_instance.error(f"Worker task error: {res}", exc_info=True)

    return results
