# Handoff: Remaining Optimizations for ZipPicks Generator

## Overview
This document outlines the implementation details for the two remaining optimizations from the Code Rabbit recommendations that have not yet been implemented.

## 1. Unicode Handling Implementation

### Current State
- The system currently relies on pandas' default UTF-8 handling
- Some files attempt multiple encodings when reading CSVs
- No explicit Unicode normalization or cleaning is performed

### Recommended Implementation

#### A. Add Unicode Handling to data_manager.py

```python
# In data_manager.py, update the _clean_data method:

def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize restaurant data using vectorized operations"""
    
    # ... existing code ...
    
    # Add Unicode normalization for all text columns
    text_columns = df.select_dtypes(include=['object']).columns
    
    for col in text_columns:
        # Ensure proper Unicode handling
        df[col] = df[col].astype(str).str.normalize('NFKD')
        # Remove any non-printable characters
        df[col] = df[col].str.encode('utf-8', errors='ignore').str.decode('utf-8')
        # Strip extra whitespace
        df[col] = df[col].str.strip()
    
    # ... rest of existing code ...
```

#### B. Add Unicode utilities module

Create a new file `utils/unicode_handler.py`:

```python
"""
Unicode handling utilities for consistent text processing
"""

import unicodedata
import re
from typing import Optional

def clean_unicode_text(text: Optional[str]) -> str:
    """Clean and normalize Unicode text"""
    if not text or not isinstance(text, str):
        return ""
    
    # Normalize Unicode (NFKD = compatibility decomposition)
    text = unicodedata.normalize('NFKD', text)
    
    # Remove non-printable characters except newlines and tabs
    text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in '\n\t')
    
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    return text.strip()

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system usage"""
    # Remove Unicode characters that might cause issues in filenames
    filename = unicodedata.normalize('NFKD', filename)
    filename = filename.encode('ascii', 'ignore').decode('ascii')
    
    # Replace problematic characters
    filename = re.sub(r'[^\w\s\-_.]', '', filename)
    filename = re.sub(r'[-\s]+', '-', filename)
    
    return filename.strip('-')
```

#### C. Update CSV reading to handle BOM

```python
# In data_manager.py load_all_restaurants method:

def load_all_restaurants(self) -> pd.DataFrame:
    """Load all restaurant data"""
    if not self.data_file.exists():
        raise FileNotFoundError(f"Restaurant data not found: {self.data_file}")
    
    # Try different encodings with BOM handling
    encodings = [
        ('utf-8-sig', {}),  # Handles UTF-8 with BOM
        ('utf-8', {}),
        ('latin-1', {}),
        ('iso-8859-1', {}),
        ('cp1252', {})  # Windows encoding
    ]
    
    for encoding, kwargs in encodings:
        try:
            df = pd.read_csv(self.data_file, encoding=encoding, **kwargs)
            logger.info(f"Successfully read CSV with {encoding} encoding")
            return self._clean_data(df)
        except (UnicodeDecodeError, UnicodeError) as e:
            logger.debug(f"Failed to read with {encoding}: {e}")
            continue
    
    raise ValueError("Could not read CSV file with any supported encoding")
```

### Testing Unicode Handling

Add test cases for:
- Emoji handling: 🍕🍔🌮
- Accented characters: café, naïve, piñata
- Asian characters: 中文, 日本語, 한국어
- Special symbols: ™, ®, €, £

## 2. Rate Limiting Implementation

### Current State
- No rate limiting exists for API calls
- WordPress API calls are made without throttling
- No protection against overwhelming external services

### Recommended Implementation

#### A. Create rate_limiter.py module

```python
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
```

#### B. Apply rate limiting to publisher.py

```python
# In publisher.py, add rate limiting to API calls:

from utils.rate_limiter import wordpress_rate_limiter, rate_limit

class Publisher:
    # ... existing code ...
    
    @wordpress_rate_limiter
    def publish_to_wordpress(self, data: Dict) -> Optional[int]:
        """
        Publish a restaurant list to WordPress (rate-limited)
        """
        # ... existing implementation ...
    
    @wordpress_rate_limiter
    def update_post(self, post_id: int, data: Dict) -> bool:
        """
        Update an existing WordPress post (rate-limited)
        """
        # ... existing implementation ...
    
    @rate_limit(2.0)  # 2 calls per second
    def get_published_posts(self, city: Optional[str] = None, vibe: Optional[str] = None) -> List[Dict]:
        """
        Get list of published posts (rate-limited)
        """
        # ... existing implementation ...
```

#### C. Add rate limiting configuration

Create `config/rate_limits.yaml`:

```yaml
# Rate limiting configuration
rate_limits:
  wordpress:
    calls_per_second: 10
    burst_size: 20
    
  external_apis:
    calls_per_minute: 60
    
  file_operations:
    calls_per_second: 50
    
  heavy_operations:
    calls_per_second: 0.5  # 1 every 2 seconds
    
# Retry configuration
retry:
  max_attempts: 3
  backoff_factor: 2
  max_wait: 60
```

#### D. Add configurable rate limiting

```python
# In publisher.py __init__ method:

def __init__(self, config_file: str = "config/wp_config.yaml"):
    # ... existing code ...
    
    # Load rate limiting config
    self.rate_limiter = self._configure_rate_limiting()

def _configure_rate_limiting(self):
    """Configure rate limiting based on settings"""
    rate_config_path = Path("config/rate_limits.yaml")
    
    if rate_config_path.exists():
        with open(rate_config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        wp_limits = config.get('rate_limits', {}).get('wordpress', {})
        calls_per_second = wp_limits.get('calls_per_second', 10)
        
        return RateLimiter(calls=calls_per_second, period=1.0)
    else:
        # Default rate limiter
        return RateLimiter(calls=10, period=1.0)
```

### Testing Rate Limiting

1. **Unit Tests**:
   ```python
   def test_rate_limiter():
       limiter = RateLimiter(calls=5, period=1.0)
       
       @limiter
       def api_call():
           return time.time()
       
       # Make 10 calls, should take ~2 seconds
       start = time.time()
       times = [api_call() for _ in range(10)]
       duration = time.time() - start
       
       assert duration >= 1.0  # Should take at least 1 second
       assert duration < 3.0   # But not too long
   ```

2. **Integration Tests**:
   - Test WordPress API calls don't exceed limits
   - Verify file operations are throttled appropriately
   - Ensure heavy operations don't overwhelm system

### Additional Considerations

1. **Adaptive Rate Limiting**: Monitor response times and adjust limits dynamically
2. **Circuit Breaker Pattern**: Stop making calls if too many failures occur
3. **Distributed Rate Limiting**: If running multiple instances, use Redis or similar for shared state
4. **Metrics**: Track rate limit hits and wait times for monitoring

## Implementation Priority

1. **Unicode Handling** - Critical for data integrity
   - Implement immediately to prevent data corruption
   - Test with international restaurant names and descriptions

2. **Rate Limiting** - Important for stability
   - Implement before scaling up operations
   - Start with conservative limits and adjust based on monitoring

## Testing Checklist

- [ ] Unicode handling works with all international characters
- [ ] File operations handle Unicode filenames correctly
- [ ] Rate limiting prevents API overwhelm
- [ ] Rate limiting doesn't significantly impact performance
- [ ] Configuration files properly control both features
- [ ] Error handling gracefully manages edge cases
- [ ] Logging provides visibility into both systems

## Files to Modify

1. `data_manager.py` - Add Unicode normalization
2. `utils/unicode_handler.py` - New Unicode utilities (create)
3. `utils/rate_limiter.py` - New rate limiting module (create)
4. `publisher.py` - Apply rate limiting decorators
5. `config/rate_limits.yaml` - Rate limiting configuration (create)
6. `requirements.txt` - No new dependencies needed

## Estimated Effort

- Unicode Handling: 2-3 hours
- Rate Limiting: 3-4 hours
- Testing & Integration: 2-3 hours
- **Total: 7-10 hours**