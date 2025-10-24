"""
Generic API rate limiter service.

Provides rate limiting functionality to prevent exceeding API request limits.
Uses a sliding window approach to track requests and automatically throttles
when approaching the rate limit.
"""

import asyncio
import time


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
