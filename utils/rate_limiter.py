"""
Rate limiting utilities for API calls and resource-intensive operations
"""

import time
import threading
from functools import wraps
from collections import deque
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Thread-safe rate limiter using sliding window algorithm"""
    
    def __init__(self, calls: int, period: float):
        """
        Initialize rate limiter
        
        Args:
            calls: Number of allowed calls
            period: Time period in seconds
        """
        self.calls = calls
        self.period = period
        self.calls_made = deque()
        self.lock = threading.Lock()
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator implementation"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            self.wait_if_needed()
            try:
                return func(*args, **kwargs)
            finally:
                self.record_call()
        return wrapper
    
    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        with self.lock:
            now = time.time()
            # Remove old calls outside the window
            while self.calls_made and self.calls_made[0] < now - self.period:
                self.calls_made.popleft()
            
            # If we're at the limit, wait
            if len(self.calls_made) >= self.calls:
                sleep_time = self.period - (now - self.calls_made[0])
                if sleep_time > 0:
                    logger.debug(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                    time.sleep(sleep_time)
    
    def record_call(self):
        """Record that a call was made"""
        with self.lock:
            self.calls_made.append(time.time())


def rate_limit(calls_per_second: float):
    """
    Simple rate limiting decorator
    
    Args:
        calls_per_second: Maximum calls per second allowed
    """
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]
    lock = threading.Lock()
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                elapsed = time.time() - last_called[0]
                left_to_wait = min_interval - elapsed
                if left_to_wait > 0:
                    time.sleep(left_to_wait)
                ret = func(*args, **kwargs)
                last_called[0] = time.time()
                return ret
        return wrapper
    return decorator


# Pre-configured rate limiters for common use cases
wordpress_rate_limiter = RateLimiter(calls=10, period=1.0)  # 10 calls per second
api_rate_limiter = RateLimiter(calls=30, period=60.0)  # 30 calls per minute
heavy_operation_limiter = rate_limit(0.5)  # 1 call per 2 seconds