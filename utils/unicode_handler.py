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