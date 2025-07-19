"""
Enhanced Publisher - Integrates with Master Critic plugin and vibe lookup API
"""

import json
import logging
import os
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import yaml
from pathlib import Path
from urllib.parse import urlparse
from functools import wraps
from schema_builder import SchemaBuilder
from utils.rate_limiter import wordpress_rate_limiter, rate_limit, RateLimiter

# Set up logging
logger = logging.getLogger(__name__)


# Custom exceptions
class VibeLookupError(Exception):
    """Custom exception for vibe lookup errors"""
    pass


class VibeLookupNetworkError(VibeLookupError):
    """Network-related vibe lookup errors"""
    pass


class VibeLookupValidationError(VibeLookupError):
    """Validation-related vibe lookup errors"""
    pass


def retry_on_failure(max_retries=3, delay=1.0):
    """Decorator for retrying API calls"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                        time.sleep(delay * (2 ** attempt))  # Exponential backoff
                    else:
                        logger.error(f"All {max_retries} attempts failed")
                        raise
                except Exception as e:
                    # Don't retry on other exceptions
                    raise
                    
            raise last_exception
        return wrapper
    return decorator


class VibeLookupClient:
    """Client for looking up vibe IDs from WordPress"""
    
    def __init__(self, site_url: str, auth: Optional[Tuple[str, str]] = None):
        self.site_url = self._validate_and_sanitize_url(site_url)
        self.endpoint = f"{self.site_url}/wp-json/zippicks/v1/vibes/lookup"
        self.auth = auth
        self.session = requests.Session()
        if auth:
            self.session.auth = auth
    
    def _validate_and_sanitize_url(self, url: str) -> str:
        """Validate and sanitize site URL"""
        if not url:
            raise ValueError("Site URL cannot be empty")
        
        # Remove trailing slash and validate format
        url = url.rstrip('/')
        
        if not url.startswith(('http://', 'https://')):
            raise ValueError("Site URL must start with http:// or https://")
        
        # Additional validation
        parsed = urlparse(url)
        if not parsed.netloc:
            raise ValueError("Invalid site URL format")
        
        # Check for path traversal attempts
        if '..' in url or '//' in url[8:]:  # Skip protocol //
            raise ValueError("URL contains suspicious characters")
        
        # Only allow alphanumeric, dash, dot, colon for domain
        if parsed.path and any(c in parsed.path for c in ['..', '<', '>', '"', "'", '\\', '|', '*', '?']):
            raise ValueError("URL path contains invalid characters")
        
        return url
    
    def _validate_api_response(self, response: requests.Response) -> dict:
        """Validate API response with security checks"""
        
        # Check status code
        if response.status_code not in [200, 201]:
            raise requests.exceptions.HTTPError(
                f"API returned status {response.status_code}: {response.text[:200]}"
            )
        
        # Check content type
        content_type = response.headers.get('content-type', '')
        if 'application/json' not in content_type:
            raise ValueError(f"Expected JSON response, got {content_type}")
        
        # Parse JSON with size limit
        if len(response.content) > 1024 * 1024:  # 1MB limit
            raise ValueError("Response too large")
        
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {e}")
        
        return data
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def lookup_vibe_ids(self, vibe_slugs: List[str]) -> Tuple[List[int], List[str]]:
        """
        Lookup vibe IDs from slugs
        
        Returns:
            Tuple of (vibe_ids, missing_slugs)
        """
        if not vibe_slugs:
            return [], []
        
        try:
            response = self.session.post(
                self.endpoint,
                json={'slugs': vibe_slugs},
                timeout=10
            )
            
            # Validate response
            data = self._validate_api_response(response)
            
            if data.get('success'):
                return (
                    data['data'].get('vibe_ids', []),
                    data['data'].get('missing_slugs', [])
                )
            else:
                logger.error(f"Vibe lookup failed: {data}")
                return [], vibe_slugs
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error during vibe lookup: {e}")
            raise VibeLookupNetworkError(f"Failed to connect to vibe API: {e}")
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout during vibe lookup: {e}")
            raise VibeLookupNetworkError(f"Vibe API timeout: {e}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error during vibe lookup: {e}")
            raise VibeLookupError(f"Vibe API HTTP error: {e}")
        except ValueError as e:
            logger.error(f"Validation error during vibe lookup: {e}")
            raise VibeLookupValidationError(f"Invalid vibe data: {e}")


class EnhancedPublisher:
    """Enhanced publisher that integrates with Master Critic plugin"""
    
    def __init__(self, config_file: str = "config/wp_config.yaml"):
        self.config = self._load_config(config_file)
        self.schema_builder = SchemaBuilder()
        self.session = requests.Session()
        
        # Load rate limiting config
        self.rate_limiter = self._configure_rate_limiting()
        
        # Set up authentication
        self._setup_authentication()
        
        # Initialize vibe lookup client
        auth = None
        if hasattr(self.session, 'auth') and self.session.auth:
            auth = self.session.auth
        elif 'Authorization' in self.session.headers:
            # For application passwords, WordPress expects basic auth
            api_key = os.getenv('WP_API_KEY', '')
            if api_key:
                auth = ('api', api_key)
        
        self.vibe_client = VibeLookupClient(
            self.config.get('site_url', os.getenv('WP_SITE_URL', '')),
            auth
        )
    
    def _setup_authentication(self):
        """Set up WordPress authentication"""
        auth_type = os.getenv('WP_AUTH_TYPE', self.config.get('auth_type', 'application'))
        
        if auth_type == 'basic':
            username = os.getenv('WP_USERNAME')
            password = os.getenv('WP_PASSWORD')
            
            if username and password:
                self.session.auth = (username, password)
            else:
                logger.warning("WordPress credentials not found in environment variables.")
                
        elif auth_type == 'application':
            api_key = os.getenv('WP_API_KEY')
            
            if api_key:
                # For application passwords, use basic auth
                self.session.auth = ('api', api_key)
            else:
                logger.warning("WordPress API key not found in environment.")
    
    def _load_config(self, config_file: str) -> Dict:
        """Load WordPress configuration"""
        config_path = Path(config_file)
        
        # Default configuration
        default_config = {
            'site_url': os.getenv('WP_SITE_URL', 'https://your-site.com'),
            'api_endpoint': os.getenv('WP_API_ENDPOINT', '/wp-json/wp/v2'),
            'auth_type': 'application',
            'default_status': 'draft',
            'yoast_enabled': True,
            'schema_enabled': True
        }
        
        if not config_path.exists():
            return default_config
        
        with open(config_path, 'r') as f:
            file_config = yaml.safe_load(f)
        
        # Merge configs
        config = default_config.copy()
        safe_keys = ['site_url', 'api_endpoint', 'auth_type', 'default_status', 
                     'category_map', 'tag_settings', 'yoast_enabled', 'schema_enabled']
        
        for key in safe_keys:
            if key in file_config:
                config[key] = file_config[key]
        
        return config
    
    def _extract_vibe_slugs(self, data: Dict) -> List[str]:
        """Extract all unique vibe slugs with validation"""
        vibe_slugs = []
        
        # Validate input
        if not isinstance(data, dict):
            logger.warning("Invalid data type for vibe extraction")
            return []
        
        # Extract from multiple sources with validation
        sources = [
            data.get('vibes', []) if isinstance(data.get('vibes'), list) else [],
            [data.get('vibe')] if data.get('vibe') else [],
        ]
        
        # Extract from restaurants with careful null checking
        restaurants = data.get('restaurants', [])
        if isinstance(restaurants, list):
            for r in restaurants:
                if r and isinstance(r, dict) and 'vibes' in r:
                    if isinstance(r['vibes'], list):
                        sources.append(r['vibes'])
        
        # Flatten and validate
        for source in sources:
            for vibe in source:
                if isinstance(vibe, str) and vibe.strip():
                    vibe_slugs.append(vibe.strip().lower())
        
        return list(set(filter(None, vibe_slugs)))
    
    def _prepare_master_critic_data(self, data: Dict, vibe_ids: List[int]) -> Dict:
        """Prepare data for Master Critic post type with validation"""
        
        # Validate inputs
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
        
        if not isinstance(vibe_ids, list):
            raise ValueError("vibe_ids must be a list")
        
        # Validate each vibe ID
        for vibe_id in vibe_ids:
            if not isinstance(vibe_id, int) or vibe_id <= 0:
                raise ValueError(f"Invalid vibe ID: {vibe_id}")
        
        # Validate required fields
        if not data.get('restaurants'):
            raise ValueError("No restaurants found in data")
        
        # Extract topic from title or vibe
        topic = data.get('topic', data.get('vibe_title', data.get('vibe', '')))
        
        # Extract location
        location = data.get('city_title', data.get('city', ''))
        
        # Format restaurants for Master Critic
        mc_restaurants = []
        for i, restaurant in enumerate(data.get('restaurants', [])):
            mc_restaurant = {
                'rank': restaurant.get('rank', i + 1),
                'name': restaurant.get('name', ''),
                'address': restaurant.get('address', ''),
                'summary': restaurant.get('why_perfect', restaurant.get('description', '')),
                'score': restaurant.get('score', 9.0),  # Default score if not provided
                'must_try_dish': restaurant.get('must_try', ''),
                'price_range': restaurant.get('price_range', '$$'),
                'cuisine_type': restaurant.get('cuisine_type', ''),
                'vibes': restaurant.get('vibes', [])
            }
            
            # Add pillar scores if available
            if 'pillar_scores' in restaurant:
                mc_restaurant['pillar_scores'] = restaurant['pillar_scores']
            else:
                # Default pillar scores
                mc_restaurant['pillar_scores'] = {
                    'taste': 9.0,
                    'service': 8.5,
                    'ambiance': 8.5,
                    'value': 8.0
                }
            
            mc_restaurants.append(mc_restaurant)
        
        return {
            'topic': topic,
            'location': location,
            'restaurants': mc_restaurants,
            'vibe_ids': vibe_ids,
            'category': data.get('category', topic),
            'city_slug': data.get('city', '').lower().replace(' ', '-'),
            'dish_slug': topic.lower().replace(' ', '-')
        }
    
    def _validate_post_data(self, post_data: dict) -> dict:
        """Validate post data before sending"""
        
        # Check required fields
        required_fields = ['post_type', 'post_title', 'post_status']
        for field in required_fields:
            if field not in post_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate post_type
        allowed_post_types = ['master_critic_list', 'post']
        if post_data['post_type'] not in allowed_post_types:
            raise ValueError(f"Invalid post type: {post_data['post_type']}")
        
        # Sanitize title length
        if len(post_data['post_title']) > 200:
            post_data['post_title'] = post_data['post_title'][:200]
        
        # Validate meta_input
        if 'meta_input' in post_data:
            meta_input = post_data['meta_input']
            
            # Validate vibe_ids
            if '_mc_vibe_ids' in meta_input:
                vibe_ids = meta_input['_mc_vibe_ids']
                if not isinstance(vibe_ids, list):
                    raise ValueError("vibe_ids must be a list")
                
                # Validate each vibe ID
                for vibe_id in vibe_ids:
                    if not isinstance(vibe_id, int) or vibe_id <= 0:
                        raise ValueError(f"Invalid vibe ID: {vibe_id}")
        
        return post_data
    
    @wordpress_rate_limiter
    def publish_to_wordpress(self, data: Dict) -> Optional[int]:
        """
        Publish a restaurant list to WordPress as a Master Critic post
        
        Args:
            data: Validated restaurant data with city, vibe, and restaurants
            
        Returns:
            Post ID if successful, None otherwise
        """
        try:
            # Extract vibe slugs
            vibe_slugs = self._extract_vibe_slugs(data)
            logger.info(f"Extracted vibe slugs: {vibe_slugs}")
            
            # Lookup vibe IDs
            vibe_ids = []
            missing_vibes = []
            
            if vibe_slugs:
                try:
                    vibe_ids, missing_vibes = self.vibe_client.lookup_vibe_ids(vibe_slugs)
                    
                    if missing_vibes:
                        logger.warning(f"Vibes not found in database: {missing_vibes}")
                    
                    if vibe_ids:
                        logger.info(f"Found vibe IDs: {vibe_ids}")
                    else:
                        logger.warning("No vibe IDs found - continuing without vibes")
                except VibeLookupNetworkError as e:
                    logger.warning(f"Network error looking up vibes, continuing without: {e}")
                    # Continue without vibes on network errors
                except VibeLookupValidationError as e:
                    logger.error(f"Invalid vibe data, aborting: {e}")
                    raise  # Re-raise validation errors as they indicate bad data
                except VibeLookupError as e:
                    logger.warning(f"Vibe lookup error, continuing without vibes: {e}")
                    # Continue without vibes on general errors
            
            # Prepare Master Critic data
            mc_data = self._prepare_master_critic_data(data, vibe_ids)
            
            # Generate title
            title = self._generate_title(data)
            
            # Generate content (optional - Master Critic may generate its own)
            content = self._generate_basic_content(data)
            
            # Prepare post data for Master Critic post type
            post_data = {
                'post_type': 'master_critic_list',
                'post_title': title,
                'post_content': content,
                'post_status': self.config.get('default_status', 'draft'),
                'meta_input': {
                    '_mc_topic': mc_data['topic'],
                    '_mc_location': mc_data['location'],
                    '_mc_restaurants': json.dumps(mc_data['restaurants']),
                    '_mc_vibe_ids': mc_data['vibe_ids'],
                    '_mc_category': mc_data['category'],
                    '_mc_list_category': mc_data['category'],
                    'city_slug': mc_data['city_slug'],
                    'dish_slug': mc_data['dish_slug'],
                    '_mc_ai_provider': 'zippicks_generator',
                    '_mc_generation_date': datetime.now().isoformat()
                }
            }
            
            # Add SEO metadata if enabled
            if self.config.get('yoast_enabled', True):
                yoast_meta = self._generate_yoast_meta(data)
                post_data['meta_input'].update(yoast_meta)
            
            # Validate post data before sending
            post_data = self._validate_post_data(post_data)
            
            # Make API request
            api_url = f"{self.config['site_url']}{self.config['api_endpoint']}/master_critic_list"
            
            # First try Master Critic endpoint
            response = self.session.post(api_url, json=post_data)
            
            # If Master Critic endpoint doesn't exist, fall back to regular posts endpoint
            if response.status_code == 404:
                logger.info("Master Critic endpoint not found, using regular posts endpoint")
                api_url = f"{self.config['site_url']}{self.config['api_endpoint']}/posts"
                response = self.session.post(api_url, json=post_data)
            
            if response.status_code in [200, 201]:
                post_id = response.json().get('id')
                logger.info(f"✅ Published successfully! Post ID: {post_id}")
                
                # Log vibe integration status
                if vibe_ids:
                    logger.info(f"✅ Integrated with {len(vibe_ids)} vibes")
                if missing_vibes:
                    logger.warning(f"⚠️  {len(missing_vibes)} vibes not found: {missing_vibes}")
                
                return post_id
            else:
                logger.error(f"❌ Failed to publish: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error publishing to WordPress: {str(e)}")
            return None
    
    def _generate_title(self, data: Dict) -> str:
        """Generate SEO-optimized title for Master Critic post"""
        city = data.get('city_title', data.get('city', ''))
        topic = data.get('topic', data.get('vibe_title', data.get('vibe', '')))
        
        # Common title patterns
        title_patterns = [
            f"Top 10 {topic} in {city}",
            f"Best {topic} in {city} - Top 10",
            f"{city}'s Top 10 {topic}",
            f"10 Best {topic} in {city}"
        ]
        
        # Use first pattern by default
        return title_patterns[0]
    
    def _generate_basic_content(self, data: Dict) -> str:
        """Generate basic content for the post (Master Critic will enhance)"""
        city = data.get('city_title', data.get('city', ''))
        topic = data.get('topic', data.get('vibe_title', ''))
        
        content = f"<p>Discover the top 10 {topic} in {city}. "
        content += "This carefully curated list features the best options based on "
        content += "quality, atmosphere, and local recommendations.</p>\n\n"
        
        # Add a simple list
        content += "<ol>\n"
        for restaurant in data.get('restaurants', [])[:10]:
            name = restaurant.get('name', 'Restaurant')
            content += f"<li>{name}</li>\n"
        content += "</ol>\n"
        
        return content
    
    def _generate_yoast_meta(self, data: Dict) -> Dict:
        """Generate Yoast SEO metadata"""
        city = data.get('city_title', '')
        topic = data.get('topic', data.get('vibe_title', ''))
        
        meta_desc = f"Discover the top 10 {topic} in {city}. "
        meta_desc += f"Expert-curated list of the best {topic} restaurants and venues. "
        meta_desc += f"Updated {datetime.now().strftime('%B %Y')}."
        
        return {
            '_yoast_wpseo_metadesc': meta_desc[:155],
            '_yoast_wpseo_focuskw': f"{city} {topic}",
            '_yoast_wpseo_title': self._generate_title(data)
        }
    
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
            return RateLimiter(calls=10, period=1.0)


# For backward compatibility, create an alias
Publisher = EnhancedPublisher


if __name__ == "__main__":
    # Test the enhanced publisher
    import logging
    logging.basicConfig(level=logging.INFO)
    
    publisher = EnhancedPublisher()
    
    # Test data with vibes
    test_data = {
        'city': 'san-francisco',
        'city_title': 'San Francisco',
        'vibe': 'date-night',
        'vibe_title': 'Date Night',
        'topic': 'Romantic Restaurants',
        'vibes': ['anniversary-worthy', 'adults-only-escape'],
        'validated_at': datetime.now().isoformat(),
        'restaurants': [
            {
                'rank': 1,
                'name': 'The French Laundry',
                'why_perfect': 'Michelin three-star dining with impeccable service.',
                'must_try': 'Oysters and Pearls',
                'address': '6640 Washington St, Yountville, CA 94599',
                'price_range': '$$$$',
                'vibes': ['anniversary-worthy', 'special-occasion'],
                'cuisine_type': 'French',
                'score': 9.8,
                'pillar_scores': {
                    'taste': 10.0,
                    'service': 10.0,
                    'ambiance': 9.5,
                    'value': 8.5
                }
            },
            {
                'rank': 2,
                'name': 'Gary Danko',
                'why_perfect': 'Sophisticated dining with a view of the bay.',
                'must_try': 'Glazed Oysters with Osetra Caviar',
                'address': '800 North Point St, San Francisco, CA 94109',
                'price_range': '$$$$',
                'vibes': ['adults-only-escape'],
                'cuisine_type': 'Contemporary American',
                'score': 9.5
            }
        ]
    }
    
    # Test vibe extraction
    vibe_slugs = publisher._extract_vibe_slugs(test_data)
    print(f"Extracted vibes: {vibe_slugs}")
    
    # Test vibe lookup
    if vibe_slugs:
        vibe_ids, missing = publisher.vibe_client.lookup_vibe_ids(vibe_slugs)
        print(f"Vibe IDs: {vibe_ids}")
        print(f"Missing vibes: {missing}")
    
    # Test data preparation
    mc_data = publisher._prepare_master_critic_data(test_data, [102, 108])
    print(f"\nMaster Critic data:")
    print(json.dumps(mc_data, indent=2))