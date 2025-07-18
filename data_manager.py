"""
Data Manager - Handles restaurant data loading and filtering
"""

import pandas as pd
import json
from json import JSONDecodeError
import pickle
import re
import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from functools import lru_cache
import yaml
import logging

logger = logging.getLogger(__name__)


class DataManager:
    def __init__(self, data_file: str = "data/restaurants.csv", 
                 cache_ttl: int = 3600, max_cache_size_mb: int = 100):
        self.data_file = Path(data_file)
        self.cache_dir = Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache configuration
        self.cache_ttl = cache_ttl  # Cache time-to-live in seconds
        self.max_cache_size_mb = max_cache_size_mb
        
        # In-memory cache for frequently accessed data
        self._memory_cache = {}
        self._cache_timestamps = {}
        
        # Load configuration
        self.vibes = self._load_vibes()
        self.cities = self._load_cities()
        
        # Clean up old cache files on initialization
        self._cleanup_old_cache()
        
    def _load_vibes(self) -> Dict:
        """Load vibe definitions from config"""
        vibe_file = Path("config/vibes.yaml")
        if vibe_file.exists():
            with open(vibe_file, 'r') as f:
                data = yaml.safe_load(f)
                
            # Validate structure
            if not isinstance(data, dict):
                raise ValueError(f"Invalid vibes.yaml format: expected dictionary, got {type(data).__name__}")
            
            vibes = data.get('vibes', {})
            if not isinstance(vibes, dict):
                raise ValueError(f"Invalid 'vibes' section: expected dictionary, got {type(vibes).__name__}")
            
            # Validate each vibe entry
            for vibe_name, vibe_data in vibes.items():
                if not isinstance(vibe_data, dict):
                    raise ValueError(f"Invalid vibe '{vibe_name}': expected dictionary, got {type(vibe_data).__name__}")
            
            return vibes
        return {}
    
    def _load_cities(self) -> Dict:
        """Load city configurations"""
        cities_file = Path("config/cities.yaml")
        if cities_file.exists():
            with open(cities_file, 'r') as f:
                data = yaml.safe_load(f)
                
            # Validate structure
            if not isinstance(data, dict):
                raise ValueError(f"Invalid cities.yaml format: expected dictionary, got {type(data).__name__}")
            
            cities = data.get('cities', {})
            if not isinstance(cities, dict):
                raise ValueError(f"Invalid 'cities' section: expected dictionary, got {type(cities).__name__}")
            
            # Validate each city entry
            for city_name, city_data in cities.items():
                if not isinstance(city_data, dict):
                    raise ValueError(f"Invalid city '{city_name}': expected dictionary, got {type(city_data).__name__}")
            
            return cities
        return {}
    
    def _cleanup_old_cache(self):
        """Clean up old cache files based on TTL and size limits"""
        try:
            total_size = 0
            cache_files = []
            
            # Collect all cache files with their stats
            for cache_file in self.cache_dir.glob("*.pkl"):
                stat = cache_file.stat()
                age = time.time() - stat.st_mtime
                
                # Remove files older than TTL
                if age > self.cache_ttl:
                    cache_file.unlink()
                    logger.info(f"Removed expired cache file: {cache_file.name}")
                else:
                    cache_files.append((cache_file, stat.st_mtime, stat.st_size))
                    total_size += stat.st_size
            
            # If cache is too large, remove oldest files
            max_size_bytes = self.max_cache_size_mb * 1024 * 1024
            if total_size > max_size_bytes:
                # Sort by modification time (oldest first)
                cache_files.sort(key=lambda x: x[1])
                
                while total_size > max_size_bytes and cache_files:
                    file_to_remove, _, size = cache_files.pop(0)
                    file_to_remove.unlink()
                    total_size -= size
                    logger.info(f"Removed cache file to free space: {file_to_remove.name}")
                    
        except Exception as e:
            logger.warning(f"Error cleaning cache: {e}")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if a cache entry is still valid"""
        if cache_key in self._cache_timestamps:
            age = time.time() - self._cache_timestamps[cache_key]
            return age < self.cache_ttl
        return False
    
    @lru_cache(maxsize=32)
    def _get_file_mtime(self, file_path: Path) -> float:
        """Get file modification time with caching"""
        return file_path.stat().st_mtime if file_path.exists() else 0
    
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
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize restaurant data using vectorized operations"""
        
        # Ensure required columns exist
        required_columns = ['name', 'address', 'city', 'yelp_rating']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Add Unicode normalization for all text columns
        text_columns = df.select_dtypes(include=['object']).columns
        
        for col in text_columns:
            # Ensure proper Unicode handling
            df[col] = df[col].astype(str).str.normalize('NFKD')
            # Remove any non-printable characters
            df[col] = df[col].str.encode('utf-8', errors='ignore').str.decode('utf-8')
            # Strip extra whitespace
            df[col] = df[col].str.strip()
        
        # Vectorized operations for better performance
        # Clean city names (standardize format) - vectorized
        df['city_slug'] = df['city'].str.lower().str.strip().str.replace(' ', '-', regex=False)
        
        # Convert ratings to float - already vectorized
        df['yelp_rating'] = pd.to_numeric(df['yelp_rating'], errors='coerce')
        
        # Filter out invalid ratings using boolean indexing - more efficient
        valid_mask = df['yelp_rating'].notna() & (df['yelp_rating'] > 0)
        df = df[valid_mask].copy()
        
        # Ensure price range is present
        if 'price_range' not in df.columns:
            df['price_range'] = '$'
        
        # Vectorized price range normalization
        df['price_range'] = df['price_range'].fillna('$')
        
        # Use vectorized operations instead of apply
        df['price_range'] = self._normalize_price_vectorized(df['price_range'])
        
        return df
    
    def _normalize_price_vectorized(self, price_series: pd.Series) -> pd.Series:
        """Vectorized price normalization for better performance"""
        # Count dollar signs using vectorized string operations
        dollar_counts = price_series.str.count('\\$')
        
        # Create normalized prices using numpy where for vectorization
        normalized = pd.Series('$', index=price_series.index)
        normalized[dollar_counts == 2] = '$$'
        normalized[dollar_counts == 3] = '$$$'
        normalized[dollar_counts >= 4] = '$$$$'
        normalized[price_series.isna() | (dollar_counts == 0)] = '$'
        
        return normalized
    
    def _normalize_price(self, price: str) -> str:
        """Normalize price range to $, $$, $$$, or $$$$"""
        if pd.isna(price):
            return '$'
        
        # Count dollar signs
        dollar_count = price.count('$')
        
        if dollar_count == 0:
            return '$'
        elif dollar_count > 4:
            return '$$$$'
        else:
            return '$' * dollar_count
    
    def _sanitize_cache_key(self, value: Optional[str]) -> str:
        """Sanitize input value for safe use in cache key/filename"""
        if not value:
            return ""
        
        # Remove or replace potentially dangerous characters
        # Allow only alphanumeric, hyphens, and underscores
        sanitized = re.sub(r'[^a-zA-Z0-9\-_]', '_', value)
        
        # Remove any leading/trailing dots or slashes that might remain
        sanitized = sanitized.strip('._/')
        
        # Prevent empty strings
        return sanitized or "default"
    
    def load_city_restaurants(self, city: str, vibe: Optional[str] = None, 
                            min_rating: float = 4.3) -> pd.DataFrame:
        """Load restaurants for a specific city and optionally filter by vibe"""
        
        # Sanitize inputs for safe cache key generation
        safe_city = self._sanitize_cache_key(city)
        safe_vibe = self._sanitize_cache_key(vibe) if vibe else None
        
        # Check in-memory cache first
        cache_key = f"{safe_city}_{safe_vibe}_{min_rating}" if safe_vibe else f"{safe_city}_all_{min_rating}"
        
        if cache_key in self._memory_cache and self._is_cache_valid(cache_key):
            logger.debug(f"Returning data from memory cache for {cache_key}")
            return self._memory_cache[cache_key]
        
        # Check disk cache
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        if cache_file.exists():
            try:
                # Check if cache file is still valid
                file_age = time.time() - cache_file.stat().st_mtime
                if file_age < self.cache_ttl:
                    df = pd.read_pickle(cache_file)
                    # Store in memory cache for faster access
                    self._memory_cache[cache_key] = df
                    self._cache_timestamps[cache_key] = time.time()
                    logger.debug(f"Loaded from disk cache: {cache_key}")
                    return df
                else:
                    # Remove expired cache file
                    cache_file.unlink()
                    logger.debug(f"Removed expired cache file: {cache_key}")
            except (pickle.UnpicklingError, EOFError, FileNotFoundError) as e:
                logger.warning(f"Error reading cache file {cache_key}: {e}")
                if cache_file.exists():
                    cache_file.unlink()
        
        # Load all restaurants
        df = self.load_all_restaurants()
        
        # Filter by city
        city_df = df[df['city_slug'] == city].copy()
        
        if city_df.empty:
            # Try alternative city names from config
            city_config = self.cities.get(city, {})
            alt_names = city_config.get('alt_names', [])
            
            for alt_name in alt_names:
                city_df = df[df['city_slug'] == alt_name].copy()
                if not city_df.empty:
                    break
        
        # Filter by rating
        city_df = city_df[city_df['yelp_rating'] >= min_rating]
        
        # Apply vibe filters if specified
        if vibe and vibe in self.vibes:
            city_df = self._apply_vibe_filters(city_df, vibe)
        
        # Sort by rating and review count
        if 'yelp_review_count' in city_df.columns:
            city_df['yelp_review_count'] = pd.to_numeric(city_df['yelp_review_count'], errors='coerce').fillna(0)
            city_df = city_df.sort_values(['yelp_rating', 'yelp_review_count'], ascending=[False, False])
        else:
            city_df = city_df.sort_values('yelp_rating', ascending=False)
        
        # Limit to top restaurants
        max_restaurants = 50  # Provide enough options for Claude
        city_df = city_df.head(max_restaurants)
        
        # Cache the result both to disk and memory
        city_df.to_pickle(cache_file)
        self._memory_cache[cache_key] = city_df
        self._cache_timestamps[cache_key] = time.time()
        
        # Clean up memory cache if it's getting too large
        self._cleanup_memory_cache()
        
        return city_df
    
    def _cleanup_memory_cache(self):
        """Remove old entries from memory cache if it's getting too large"""
        # Estimate memory usage (rough approximation)
        max_entries = 20  # Keep max 20 DataFrames in memory
        
        if len(self._memory_cache) > max_entries:
            # Remove oldest entries
            sorted_keys = sorted(self._cache_timestamps.items(), key=lambda x: x[1])
            keys_to_remove = [k for k, _ in sorted_keys[:len(sorted_keys) - max_entries]]
            
            for key in keys_to_remove:
                self._memory_cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
                logger.debug(f"Removed {key} from memory cache")
    
    def _apply_vibe_filters(self, df: pd.DataFrame, vibe: str) -> pd.DataFrame:
        """Apply vibe-specific filters to restaurant data"""
        
        vibe_config = self.vibes.get(vibe, {})
        filters = vibe_config.get('filters', {})
        
        # Apply cuisine filters
        if 'cuisines' in filters and 'cuisine_type' in df.columns:
            cuisines = filters['cuisines']
            if cuisines:
                # Create regex pattern for cuisine matching
                pattern = '|'.join(re.escape(cuisine) for cuisine in cuisines)
                df = df[df['cuisine_type'].str.contains(pattern, case=False, na=False)]
        
        # Apply price range filters
        if 'price_ranges' in filters:
            price_ranges = filters['price_ranges']
            if price_ranges:
                df = df[df['price_range'].isin(price_ranges)]
        
        # Apply keyword filters (in name or description)
        if 'keywords' in filters:
            keywords = filters['keywords']
            if keywords:
                pattern = '|'.join(re.escape(keyword) for keyword in keywords)
                
                # Check in name
                name_match = df['name'].str.contains(pattern, case=False, na=False)
                
                # Check in description if available
                if 'description' in df.columns:
                    desc_match = df['description'].str.contains(pattern, case=False, na=False)
                    df = df[name_match | desc_match]
                else:
                    df = df[name_match]
        
        # Apply vibe attributes if available
        if 'vibe_attributes' in df.columns:
            vibe_attrs = vibe_config.get('attributes', [])
            if vibe_attrs:
                # Parse vibe attributes (assuming JSON string)
                def check_attributes(attrs_str):
                    if pd.isna(attrs_str):
                        return False
                    try:
                        attrs = json.loads(attrs_str)
                        return any(attrs.get(attr, False) for attr in vibe_attrs)
                    except JSONDecodeError:
                        return False
                
                df = df[df['vibe_attributes'].apply(check_attributes)]
        
        return df
    
    def get_restaurant_details(self, restaurant_name: str, city: str) -> Optional[Dict]:
        """Get detailed information about a specific restaurant"""
        
        df = self.load_city_restaurants(city)
        
        # Find restaurant (case-insensitive)
        restaurant = df[df['name'].str.lower() == restaurant_name.lower()]
        
        if restaurant.empty:
            return None
        
        # Return first match as dictionary
        return restaurant.iloc[0].to_dict()
    
    def get_available_cities(self) -> List[str]:
        """Get list of cities with restaurant data"""
        
        df = self.load_all_restaurants()
        cities = df['city_slug'].unique().tolist()
        
        # Add configured cities
        configured_cities = list(self.cities.keys())
        
        # Combine and deduplicate
        all_cities = list(set(cities + configured_cities))
        all_cities.sort()
        
        return all_cities
    
    def get_city_stats(self, city: str) -> Dict:
        """Get statistics for a city using optimized vectorized operations"""
        
        df = self.load_city_restaurants(city)
        
        if df.empty:
            return {'total_restaurants': 0, 'avg_rating': 0}
        
        # Vectorized operations for better performance
        stats = {
            'total_restaurants': len(df),
            'avg_rating': df['yelp_rating'].mean(),
            'price_distribution': df['price_range'].value_counts().to_dict()
        }
        
        # Optimize cuisine processing using vectorized operations
        if 'cuisine_type' in df.columns:
            # More efficient cuisine extraction using str methods
            cuisines = df['cuisine_type'].str.split(',').explode()
            cuisines = cuisines.str.strip()
            stats['top_cuisines'] = cuisines.value_counts().head(10).to_dict()
        
        # Add rating distribution using vectorized binning
        stats['rating_distribution'] = pd.cut(
            df['yelp_rating'], 
            bins=[0, 3, 3.5, 4, 4.5, 5],
            labels=['<3', '3-3.5', '3.5-4', '4-4.5', '4.5-5']
        ).value_counts().to_dict()
        
        return stats
    
    def clear_cache(self):
        """Clear all cached data"""
        
        # Clear disk cache
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
        
        # Clear memory cache
        self._memory_cache.clear()
        self._cache_timestamps.clear()
        
        logger.info(f"Cleared cache directory: {self.cache_dir}")


if __name__ == "__main__":
    # Test the data manager
    dm = DataManager()
    
    # Test loading cities
    cities = dm.get_available_cities()
    print(f"Available cities: {len(cities)}")
    
    if cities:
        # Test loading restaurants for first city
        test_city = cities[0]
        restaurants = dm.load_city_restaurants(test_city)
        print(f"\n{test_city}: {len(restaurants)} restaurants")
        
        if not restaurants.empty:
            print("\nSample restaurant:")
            print(restaurants.iloc[0][['name', 'yelp_rating', 'price_range', 'address']].to_dict())