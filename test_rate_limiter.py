#!/usr/bin/env python3
"""
Test rate limiting functionality
"""

import time
from utils.rate_limiter import RateLimiter, rate_limit

def test_rate_limiter_class():
    """Test RateLimiter class"""
    print("Testing RateLimiter class...")
    
    # Create a rate limiter that allows 5 calls per second
    limiter = RateLimiter(calls=5, period=1.0)
    
    @limiter
    def api_call(i):
        return time.time()
    
    # Make 10 calls - should take about 2 seconds
    print("Making 10 API calls with limit of 5 per second...")
    start_time = time.time()
    times = []
    
    for i in range(10):
        call_time = api_call(i)
        times.append(call_time)
        print(f"  Call {i+1} at {call_time - start_time:.2f}s")
    
    total_time = time.time() - start_time
    print(f"\nTotal time for 10 calls: {total_time:.2f}s")
    print(f"Expected time: ~2.0s (should be >= 1.0s)")
    
    # Check that rate limiting worked
    if total_time >= 1.0:
        print("✓ Rate limiting is working correctly")
    else:
        print("✗ Rate limiting failed - calls completed too quickly")

def test_rate_limit_decorator():
    """Test rate_limit decorator"""
    print("\n\nTesting rate_limit decorator...")
    
    # Create a function that can be called 2 times per second
    @rate_limit(2.0)
    def slow_function(i):
        return time.time()
    
    print("Making 5 calls with limit of 2 per second...")
    start_time = time.time()
    
    for i in range(5):
        call_time = slow_function(i)
        elapsed = call_time - start_time
        print(f"  Call {i+1} at {elapsed:.2f}s")
    
    total_time = time.time() - start_time
    print(f"\nTotal time for 5 calls: {total_time:.2f}s")
    print(f"Expected time: ~2.0s")
    
    # Check that rate limiting worked (should take at least 2 seconds)
    if total_time >= 2.0:
        print("✓ Rate limit decorator is working correctly")
    else:
        print("✗ Rate limit decorator failed - calls completed too quickly")

def test_burst_handling():
    """Test that rate limiter handles bursts correctly"""
    print("\n\nTesting burst handling...")
    
    # Create a rate limiter that allows 3 calls per 2 seconds
    limiter = RateLimiter(calls=3, period=2.0)
    
    @limiter
    def bursty_call():
        return time.time()
    
    print("Making 6 rapid calls with limit of 3 per 2 seconds...")
    start_time = time.time()
    
    # Make 6 calls as fast as possible
    times = []
    for i in range(6):
        call_time = bursty_call()
        elapsed = call_time - start_time
        times.append(elapsed)
        print(f"  Call {i+1} at {elapsed:.2f}s")
    
    # Check that first 3 calls were immediate, next 3 were delayed
    print("\nAnalyzing burst behavior:")
    print(f"  First 3 calls completed by: {times[2]:.2f}s")
    print(f"  Next 3 calls started after: {times[3]:.2f}s")
    
    if times[3] >= 2.0:
        print("✓ Burst handling is working correctly")
    else:
        print("✗ Burst handling failed - rate limit not enforced")

if __name__ == "__main__":
    print("=== Rate Limiting Tests ===\n")
    test_rate_limiter_class()
    test_rate_limit_decorator()
    test_burst_handling()
    print("\n=== Tests Complete ===")