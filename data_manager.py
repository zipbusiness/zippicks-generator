"""
Data Manager - Handles restaurant data loading and filtering
"""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Optional
import yaml


class DataManager:
    def __init__(self, data_file: str = "data/restaurants.csv"):
        self.data_file = Path(data_file)
        self.cache_dir = Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        self.vibes = self._load_vibes()
        self.cities = self._load_cities()
        
    def _load_vibes(self) -> Dict:
        """Load vibe definitions from config"""
        vibe_file = Path("config/vibes.yaml")
        if vibe_file.exists():
            with open(vibe_file, 'r') as f:
                return yaml.safe_load(f).get('vibes', {})
        return {}
    
    def _load_cities(self) -> Dict:
        """Load city configurations"""
        cities_file = Path("config/cities.yaml")
        if cities_file.exists():
            with open(cities_file, 'r') as f:
                return yaml.safe_load(f).get('cities', {})
        return {}
    
    def load_all_restaurants(self) -> pd.DataFrame:
        """Load all restaurant data"""
        if not self.data_file.exists():
            raise FileNotFoundError(f"Restaurant data not found: {self.data_file}")
        
        # Try different encodings
        encodings = ['utf-8', 'latin-1', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                df = pd.read_csv(self.data_file, encoding=encoding)
                return self._clean_data(df)
            except UnicodeDecodeError:
                continue
        
        raise ValueError("Could not read CSV file with any encoding")
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize restaurant data"""
        
        # Ensure required columns exist
        required_columns = ['name', 'address', 'city', 'yelp_rating']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Clean city names (standardize format)
        df['city_slug'] = df['city'].str.lower().str.strip().str.replace(' ', '-')
        
        # Convert ratings to float
        df['yelp_rating'] = pd.to_numeric(df['yelp_rating'], errors='coerce')
        
        # Filter out invalid ratings
        df = df[df['yelp_rating'].notna()]
        df = df[df['yelp_rating'] > 0]
        
        # Ensure price range is present
        if 'price_range' not in df.columns:
            df['price_range'] = '$'
        
        # Clean price range
        df['price_range'] = df['price_range'].fillna('$')
        df['price_range'] = df['price_range'].apply(self._normalize_price)
        
        return df
    
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
    
    def load_city_restaurants(self, city: str, vibe: Optional[str] = None, 
                            min_rating: float = 4.3) -> pd.DataFrame:
        """Load restaurants for a specific city and optionally filter by vibe"""
        
        # Check cache first
        cache_key = f"{city}_{vibe}_{min_rating}" if vibe else f"{city}_all_{min_rating}"
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        if cache_file.exists():
            try:
                return pd.read_pickle(cache_file)
            except:
                pass
        
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
        
        # Cache the result
        city_df.to_pickle(cache_file)
        
        return city_df
    
    def _apply_vibe_filters(self, df: pd.DataFrame, vibe: str) -> pd.DataFrame:
        """Apply vibe-specific filters to restaurant data"""
        
        vibe_config = self.vibes.get(vibe, {})
        filters = vibe_config.get('filters', {})
        
        # Apply cuisine filters
        if 'cuisines' in filters and 'cuisine_type' in df.columns:
            cuisines = filters['cuisines']
            if cuisines:
                # Create regex pattern for cuisine matching
                pattern = '|'.join(cuisines)
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
                pattern = '|'.join(keywords)
                
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
                    except:
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
        """Get statistics for a city"""
        
        df = self.load_city_restaurants(city)
        
        stats = {
            'total_restaurants': len(df),
            'avg_rating': df['yelp_rating'].mean() if not df.empty else 0,
            'price_distribution': df['price_range'].value_counts().to_dict() if not df.empty else {},
        }
        
        # Add cuisine distribution if available
        if 'cuisine_type' in df.columns and not df.empty:
            # Get top 10 cuisines
            cuisines = df['cuisine_type'].str.split(',', expand=True).stack()
            cuisines = cuisines.str.strip().value_counts().head(10)
            stats['top_cuisines'] = cuisines.to_dict()
        
        return stats
    
    def clear_cache(self):
        """Clear all cached data"""
        
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
        
        print(f"✅ Cleared cache directory: {self.cache_dir}")


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