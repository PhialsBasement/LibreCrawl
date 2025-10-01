"""Token bucket rate limiter for smooth request distribution"""
import time
import threading


class RateLimiter:
    """
    Token bucket rate limiter that ensures smooth, steady request distribution.
    Prevents bursting by spacing out requests evenly over time.
    """

    def __init__(self, requests_per_second=1.0):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Target request rate (e.g., 1.0 = 1 req/sec, 0.5 = 1 req every 2 sec)
        """
        self.requests_per_second = max(0.01, requests_per_second)  # Minimum rate
        self.min_interval = 1.0 / self.requests_per_second if self.requests_per_second > 0 else 0
        self.last_request_time = 0
        self.lock = threading.Lock()

    def acquire(self):
        """
        Acquire permission to make a request.
        Blocks until enough time has passed since the last request.
        """
        with self.lock:
            now = time.time()
            time_since_last = now - self.last_request_time

            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                time.sleep(sleep_time)
                self.last_request_time = time.time()
            else:
                self.last_request_time = now

    def update_rate(self, requests_per_second):
        """Update the rate limit dynamically"""
        with self.lock:
            self.requests_per_second = max(0.01, requests_per_second)
            self.min_interval = 1.0 / self.requests_per_second if self.requests_per_second > 0 else 0
