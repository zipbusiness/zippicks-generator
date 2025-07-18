"""
Publisher - Handles publishing to WordPress with SEO and schema markup
"""

import json
import logging
import os
import requests
from datetime import datetime
from typing import Dict, List, Optional
import yaml
from pathlib import Path
from schema_builder import SchemaBuilder
from utils.rate_limiter import wordpress_rate_limiter, rate_limit, RateLimiter

# Set up logging
logger = logging.getLogger(__name__)


class Publisher:
    """Handles publishing restaurant lists to WordPress with full SEO optimization"""
    
    def __init__(self, config_file: str = "config/wp_config.yaml"):
        self.config = self._load_config(config_file)
        self.schema_builder = SchemaBuilder()
        self.session = requests.Session()
        
        # Load rate limiting config
        self.rate_limiter = self._configure_rate_limiting()
        
        # Set up authentication using environment variables
        auth_type = os.getenv('WP_AUTH_TYPE', self.config.get('auth_type', 'basic'))
        
        if auth_type == 'basic':
            # Use environment variables for credentials, fall back to config only if not set
            username = os.getenv('WP_USERNAME', self.config.get('username'))
            password = os.getenv('WP_PASSWORD', self.config.get('password'))
            
            if not username or not password:
                logger.warning("WordPress credentials not found in environment variables. Set WP_USERNAME and WP_PASSWORD.")
            
            self.session.auth = (username, password)
        elif auth_type == 'application':
            # Use environment variable for API key
            api_key = os.getenv('WP_API_KEY', self.config.get('api_key'))
            
            if not api_key:
                logger.warning("WordPress API key not found in environment. Set WP_API_KEY.")
                
            self.session.headers['Authorization'] = f"Bearer {api_key}"
    
    def _load_config(self, config_file: str) -> Dict:
        """Load WordPress configuration (non-sensitive settings only)"""
        config_path = Path(config_file)
        
        # Default configuration with environment variable fallbacks
        default_config = {
            'site_url': os.getenv('WP_SITE_URL', 'https://your-site.com'),
            'api_endpoint': os.getenv('WP_API_ENDPOINT', '/wp-json/wp/v2'),
            'auth_type': 'application',
            # Note: credentials should ONLY come from environment variables
        }
        
        if not config_path.exists():
            return default_config
        
        with open(config_path, 'r') as f:
            file_config = yaml.safe_load(f)
            
        # Merge configs, but never include sensitive data from file
        config = default_config.copy()
        
        # Only copy non-sensitive configuration from file
        safe_keys = ['site_url', 'api_endpoint', 'auth_type', 'category_mapping', 'tag_mapping']
        for key in safe_keys:
            if key in file_config:
                config[key] = file_config[key]
                
        # Log warning if credentials found in config file
        if any(key in file_config for key in ['username', 'password', 'api_key']):
            logger.warning("Credentials found in config file. These will be ignored. Use environment variables instead.")
            
        return config
    
    @wordpress_rate_limiter
    def publish_to_wordpress(self, data: Dict) -> Optional[int]:
        """
        Publish a restaurant list to WordPress (rate-limited)
        
        Args:
            data: Validated restaurant data with city, vibe, and restaurants
            
        Returns:
            Post ID if successful, None otherwise
        """
        
        try:
            # Generate content
            content = self._generate_content(data)
            
            # Generate schema markup
            schema_markup = self.schema_builder.generate_restaurant_list_schema(
                data['restaurants'],
                data['city_title'],
                data['vibe_title']
            )
            
            # Prepare post data
            post_data = {
                'title': self._generate_title(data),
                'content': content,
                'status': self.config.get('default_status', 'draft'),
                'categories': self._get_categories(data),
                'tags': self._get_tags(data),
                'meta': {
                    'schema_markup': json.dumps(schema_markup),
                    'city': data['city'],
                    'vibe': data['vibe'],
                    'restaurant_count': len(data['restaurants']),
                    'generated_date': data.get('validated_at', datetime.now().isoformat())
                }
            }
            
            # Add SEO fields if Yoast is installed
            if self.config.get('yoast_enabled', True):
                post_data['yoast_meta'] = self._generate_yoast_meta(data)
            
            # Make API request
            api_url = f"{self.config['site_url']}{self.config['api_endpoint']}/posts"
            response = self.session.post(api_url, json=post_data)
            
            if response.status_code in [200, 201]:
                post_id = response.json().get('id')
                print(f"✅ Published successfully! Post ID: {post_id}")
                return post_id
            else:
                print(f"❌ Failed to publish: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error publishing to WordPress: {str(e)}")
            return None
    
    def _generate_title(self, data: Dict) -> str:
        """Generate SEO-optimized title"""
        
        templates = {
            'date-night': "Top 10 {city} Date Night Restaurants {year} - Perfect Romantic Spots",
            'family-friendly': "Best Family Restaurants in {city} {year} - Top 10 Kid-Friendly Spots",
            'quick-lunch': "Top 10 Quick Lunch Spots in {city} - Best Fast Casual {year}",
            'trendy-vibes': "{city}'s Trendiest Restaurants {year} - Top 10 Hot Spots",
            'late-night': "Best Late Night Eats in {city} - Top 10 After Hours Spots {year}",
            'hidden-gems': "{city} Hidden Gem Restaurants - Top 10 Local Secrets {year}",
            'outdoor-dining': "Best Outdoor Dining in {city} - Top 10 Patio Restaurants {year}"
        }
        
        template = templates.get(data['vibe'], "Top 10 {vibe} Restaurants in {city} {year}")
        
        return template.format(
            city=data['city_title'],
            vibe=data['vibe_title'],
            year=datetime.now().year
        )
    
    def _generate_content(self, data: Dict) -> str:
        """Generate the full post content with schema markup"""
        
        # Start with schema markup
        schema_markup = self.schema_builder.generate_restaurant_list_schema(
            data['restaurants'],
            data['city_title'],
            data['vibe_title']
        )
        
        content = f"""<script type="application/ld+json">
{json.dumps(schema_markup, indent=2)}
</script>

"""
        
        # Add introduction
        content += self._generate_introduction(data)
        
        # Add restaurant list
        for restaurant in data['restaurants']:
            content += self._format_restaurant_entry(restaurant, data['city_title'])
        
        # Add conclusion
        content += self._generate_conclusion(data)
        
        return content
    
    def _generate_introduction(self, data: Dict) -> str:
        """Generate post introduction"""
        
        intros = {
            'date-night': f"Looking for the perfect romantic restaurant in {data['city_title']}? We've curated the top 10 date night spots that offer intimate atmospheres, exceptional cuisine, and memorable experiences for couples.",
            'family-friendly': f"Finding restaurants that welcome kids while serving great food can be challenging. Here are {data['city_title']}'s top 10 family-friendly restaurants where both parents and children can enjoy a fantastic meal.",
            'quick-lunch': f"Short on time but craving quality food? These top 10 {data['city_title']} restaurants offer quick, delicious lunch options without sacrificing flavor or freshness.",
            'trendy-vibes': f"Stay ahead of the dining curve with our guide to {data['city_title']}'s hottest restaurants. These 10 trendy spots are where locals go to see and be seen.",
            'late-night': f"When hunger strikes after hours, {data['city_title']} has you covered. Here are the top 10 late-night restaurants serving delicious food well past midnight.",
            'hidden-gems': f"Discover {data['city_title']}'s best-kept culinary secrets. These 10 hidden gem restaurants may fly under the radar, but they're beloved by locals for good reason.",
            'outdoor-dining': f"Enjoy {data['city_title']}'s beautiful weather while dining at these top 10 outdoor restaurants. From rooftop terraces to garden patios, these spots offer the best al fresco experiences."
        }
        
        intro = intros.get(data['vibe'], f"Discover the best {data['vibe_title']} restaurants in {data['city_title']}. We've carefully selected these top 10 spots based on atmosphere, quality, and local recommendations.")
        
        return f"<p>{intro}</p>\n\n"
    
    def _format_restaurant_entry(self, restaurant: Dict, city: str) -> str:
        """Format a single restaurant entry with schema-friendly markup"""
        
        # Generate individual restaurant schema
        restaurant_schema = self.schema_builder.generate_restaurant_schema(
            restaurant,
            city
        )
        
        entry = f"""
<div class="restaurant-entry" itemscope itemtype="https://schema.org/Restaurant">
<script type="application/ld+json">
{json.dumps(restaurant_schema, indent=2)}
</script>

<h2>{restaurant['rank']}. <span itemprop="name">{restaurant['name']}</span></h2>

<div class="restaurant-details">
<p><strong>Why It's Perfect:</strong> {restaurant['why_perfect']}</p>

<p><strong>Must-Try:</strong> <span itemprop="servesCuisine">{restaurant['must_try']}</span></p>

<div itemprop="address" itemscope itemtype="https://schema.org/PostalAddress">
<p><strong>Address:</strong> <span itemprop="streetAddress">{restaurant['address']}</span></p>
</div>

<p><strong>Price Range:</strong> <span itemprop="priceRange">{restaurant['price_range']}</span></p>
</div>
</div>

"""
        return entry
    
    def _generate_conclusion(self, data: Dict) -> str:
        """Generate post conclusion with local SEO keywords"""
        
        conclusions = {
            'date-night': f"These romantic {data['city_title']} restaurants offer everything you need for an unforgettable date night. From intimate candlelit dinners to scenic rooftop views, each spot provides a unique atmosphere for couples.",
            'family-friendly': f"With these family-friendly {data['city_title']} restaurants, dining out with kids becomes a pleasure rather than a challenge. Each location offers a welcoming atmosphere and menus that appeal to all ages.",
            'quick-lunch': f"Whether you're a busy professional or just need a quick bite, these {data['city_title']} lunch spots deliver on both speed and quality. Perfect for midday meetings or solo lunch breaks.",
            'trendy-vibes': f"Stay connected to {data['city_title']}'s dynamic dining scene with these trendy restaurants. Each offers Instagram-worthy dishes and cutting-edge culinary experiences.",
            'late-night': f"No matter what time hunger strikes, these {data['city_title']} late-night restaurants have you covered. From post-concert meals to midnight cravings, you'll find quality food at any hour.",
            'hidden-gems': f"These hidden {data['city_title']} restaurants prove that the best dining experiences often come from unexpected places. Support local businesses and discover your new favorite spot.",
            'outdoor-dining': f"Make the most of {data['city_title']}'s weather at these outdoor dining destinations. Whether you prefer garden patios or rooftop terraces, these restaurants offer the perfect al fresco experience."
        }
        
        conclusion = conclusions.get(data['vibe'], f"These top 10 {data['vibe_title']} restaurants showcase the best of {data['city_title']}'s dining scene. Each offers a unique experience worth exploring.")
        
        # Add call-to-action
        cta = f"\n\n<p><em>Have you visited any of these {data['city_title']} restaurants? Share your favorites in the comments below!</em></p>"
        
        return f"\n<p>{conclusion}</p>{cta}\n"
    
    def _get_categories(self, data: Dict) -> List[int]:
        """Get WordPress category IDs based on city and vibe"""
        
        # Map vibes to category IDs (configure based on your WordPress setup)
        category_map = self.config.get('category_map', {})
        
        categories = []
        
        # Add city category
        city_cat = category_map.get('cities', {}).get(data['city'])
        if city_cat:
            categories.append(city_cat)
        
        # Add vibe category
        vibe_cat = category_map.get('vibes', {}).get(data['vibe'])
        if vibe_cat:
            categories.append(vibe_cat)
        
        # Add default category if none found
        if not categories:
            default_cat = category_map.get('default', 1)
            categories.append(default_cat)
        
        return categories
    
    def _get_tags(self, data: Dict) -> List[str]:
        """Generate tags for the post"""
        
        tags = [
            data['city_title'],
            f"{data['city_title']} restaurants",
            data['vibe_title'],
            f"{data['vibe_title']} restaurants",
            "top 10 restaurants",
            f"best {data['vibe']} spots"
        ]
        
        # Add year tag
        tags.append(f"{datetime.now().year} restaurant guide")
        
        # Add cuisine-specific tags based on restaurants
        cuisines = set()
        for restaurant in data['restaurants']:
            # Extract cuisine from must-try if possible
            must_try = restaurant.get('must_try', '').lower()
            
            # Common cuisine indicators
            if any(word in must_try for word in ['pasta', 'italian', 'pizza']):
                cuisines.add('italian restaurants')
            elif any(word in must_try for word in ['sushi', 'ramen', 'japanese']):
                cuisines.add('japanese restaurants')
            elif any(word in must_try for word in ['taco', 'mexican', 'margarita']):
                cuisines.add('mexican restaurants')
            elif any(word in must_try for word in ['burger', 'american', 'steak']):
                cuisines.add('american restaurants')
        
        tags.extend(list(cuisines))
        
        return tags
    
    def _generate_yoast_meta(self, data: Dict) -> Dict:
        """Generate Yoast SEO metadata"""
        
        # Meta description templates
        desc_templates = {
            'date-night': "Discover the top 10 romantic restaurants in {city} perfect for date nights. From intimate bistros to upscale dining, find your ideal spot for a memorable evening.",
            'family-friendly': "Find the best family-friendly restaurants in {city}. Our top 10 list features kid-approved menus, spacious seating, and welcoming atmospheres for the whole family.",
            'quick-lunch': "Need a quick lunch in {city}? Check out our top 10 fast casual restaurants offering delicious meals without the wait. Perfect for busy professionals.",
            'trendy-vibes': "Explore {city}'s hottest dining scene with our top 10 trendy restaurants. Instagram-worthy dishes, innovative menus, and the places to see and be seen.",
            'late-night': "Hungry after midnight in {city}? Our top 10 late-night restaurants serve delicious food well past regular hours. Find your perfect after-hours spot.",
            'hidden-gems': "Uncover {city}'s best-kept dining secrets. These 10 hidden gem restaurants offer authentic experiences and incredible food away from tourist crowds.",
            'outdoor-dining': "Enjoy al fresco dining in {city} at these top 10 outdoor restaurants. From rooftop bars to garden patios, find the perfect spot for dining under the stars."
        }
        
        meta_desc = desc_templates.get(
            data['vibe'],
            "Discover the top 10 {vibe} restaurants in {city}. Expert-curated list featuring the best spots for {vibe} dining experiences."
        ).format(city=data['city_title'], vibe=data['vibe_title'])
        
        # Focus keyword
        focus_keyword = f"{data['city_title']} {data['vibe_title']} restaurants"
        
        return {
            '_yoast_wpseo_metadesc': meta_desc[:155],  # Limit to 155 chars
            '_yoast_wpseo_focuskw': focus_keyword,
            '_yoast_wpseo_title': self._generate_title(data),
            '_yoast_wpseo_linkdex': '80',  # Default good score
            '_yoast_wpseo_content_score': '80'
        }
    
    @wordpress_rate_limiter
    def update_post(self, post_id: int, data: Dict) -> bool:
        """Update an existing WordPress post (rate-limited)"""
        
        try:
            content = self._generate_content(data)
            
            update_data = {
                'content': content,
                'modified': datetime.now().isoformat()
            }
            
            api_url = f"{self.config['site_url']}{self.config['api_endpoint']}/posts/{post_id}"
            response = self.session.put(api_url, json=update_data)
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error updating post: {str(e)}")
            return False
    
    @rate_limit(2.0)  # 2 calls per second
    def get_published_posts(self, city: Optional[str] = None, vibe: Optional[str] = None) -> List[Dict]:
        """Get list of published posts, optionally filtered (rate-limited)"""
        
        try:
            api_url = f"{self.config['site_url']}{self.config['api_endpoint']}/posts"
            params = {
                'per_page': 100,
                'status': 'publish,draft'
            }
            
            # Add meta queries if filters provided
            if city:
                # Use separate parameters for safe meta queries
                params['meta_key'] = 'city'
                params['meta_value'] = city
            elif vibe:
                # WordPress REST API typically only supports one meta query at a time
                params['meta_key'] = 'vibe'
                params['meta_value'] = vibe
            
            # Note: For complex meta queries, consider using the filter parameter
            # with proper JSON encoding or implementing server-side custom endpoints
            
            response = self.session.get(api_url, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get posts: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting posts: {str(e)}")
            return []
    
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


if __name__ == "__main__":
    # Test publisher
    publisher = Publisher()
    
    # Test data
    test_data = {
        'city': 'san-francisco',
        'city_title': 'San Francisco',
        'vibe': 'date-night',
        'vibe_title': 'Date Night',
        'validated_at': datetime.now().isoformat(),
        'restaurants': [
            {
                'rank': 1,
                'name': 'Test Restaurant',
                'why_perfect': 'Perfect for romantic dinners with candlelit ambiance.',
                'must_try': 'Tasting menu with wine pairing',
                'address': '123 Main St, San Francisco, CA 94102',
                'price_range': '$$$'
            }
        ]
    }
    
    # Test content generation
    content = publisher._generate_content(test_data)
    print("Generated content preview:")
    print(content[:500] + "...")
    print(f"\nTotal content length: {len(content)} characters")