"""
Example: How to use the WordPress Vibe API endpoint from Python
"""

import requests
import json
from typing import List, Dict, Optional
import os


class VibeIDLookup:
    """Helper class to lookup vibe IDs from WordPress"""
    
    def __init__(self, site_url: str, api_key: Optional[str] = None):
        """
        Initialize the vibe lookup client
        
        Args:
            site_url: WordPress site URL (e.g., 'https://zippicks.com')
            api_key: Optional API key for authentication
        """
        self.site_url = site_url.rstrip('/')
        self.api_key = api_key or os.getenv('ZIPPICKS_VIBE_API_KEY')
        self.endpoint = f"{self.site_url}/wp-json/zippicks/v1/vibes/lookup"
        
        # If using WordPress application password
        self.wp_auth = None
        if os.getenv('WP_API_KEY'):
            # WordPress expects "username:application_password"
            # For application passwords, username can be anything
            self.wp_auth = ('api', os.getenv('WP_API_KEY'))
    
    def lookup_vibe_ids(self, vibe_slugs: List[str]) -> Dict:
        """
        Lookup vibe IDs from their slugs
        
        Args:
            vibe_slugs: List of vibe slugs (e.g., ['date-night', 'family-friendly'])
            
        Returns:
            Dict with vibe_ids list and mapping details
        """
        headers = {
            'Content-Type': 'application/json',
        }
        
        # Add API key if available
        if self.api_key:
            headers['X-ZipPicks-API-Key'] = self.api_key
        
        data = {
            'slugs': vibe_slugs
        }
        
        try:
            response = requests.post(
                self.endpoint,
                json=data,
                headers=headers,
                auth=self.wp_auth,  # Use WordPress auth if available
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('success'):
                return result['data']
            else:
                raise Exception(f"API Error: {result.get('message', 'Unknown error')}")
                
        except requests.exceptions.RequestException as e:
            print(f"Error calling vibe API: {e}")
            return {
                'vibe_ids': [],
                'mapping': {},
                'missing_slugs': vibe_slugs,
                'error': str(e)
            }
    
    def get_vibe_ids_only(self, vibe_slugs: List[str]) -> List[int]:
        """
        Get just the vibe IDs (simplified method)
        
        Args:
            vibe_slugs: List of vibe slugs
            
        Returns:
            List of vibe IDs
        """
        result = self.lookup_vibe_ids(vibe_slugs)
        return result.get('vibe_ids', [])


# Integration with your publisher.py
class EnhancedWordPressPublisher:
    """Example of how to integrate vibe lookups into your publisher"""
    
    def __init__(self):
        self.vibe_lookup = VibeIDLookup(
            site_url=os.getenv('WP_SITE_URL', 'https://zippicks.com')
        )
    
    def prepare_post_data(self, validated_data: Dict) -> Dict:
        """
        Prepare post data with vibe IDs included
        """
        # Extract vibe slugs from your validated data
        vibe_slugs = []
        
        # Option 1: If vibes are at the list level
        if 'vibes' in validated_data:
            vibe_slugs = validated_data['vibes']
        
        # Option 2: If vibes are per-restaurant, aggregate them
        if 'restaurants' in validated_data:
            for restaurant in validated_data['restaurants']:
                if 'vibes' in restaurant:
                    vibe_slugs.extend(restaurant['vibes'])
        
        # Get unique vibes
        vibe_slugs = list(set(vibe_slugs))
        
        # Lookup vibe IDs
        vibe_ids = self.vibe_lookup.get_vibe_ids_only(vibe_slugs)
        
        # Prepare WordPress post data
        post_data = {
            'post_type': 'master_critic_list',
            'post_title': validated_data['title'],
            'post_content': validated_data.get('content', ''),
            'post_status': 'publish',
            'meta_input': {
                '_mc_topic': validated_data.get('topic', ''),
                '_mc_location': validated_data.get('city', ''),
                '_mc_restaurants': json.dumps(validated_data.get('restaurants', [])),
                '_mc_vibe_ids': vibe_ids,  # Include the vibe IDs
                '_mc_category': validated_data.get('category', ''),
                'city_slug': validated_data.get('city_slug', ''),
                'dish_slug': validated_data.get('dish_slug', '')
            }
        }
        
        return post_data


# Example usage
if __name__ == "__main__":
    # Test the vibe lookup
    lookup = VibeIDLookup('https://zippicks.com')
    
    # Example vibe slugs from your system
    test_vibes = ['date-night', 'family-friendly', 'trendy-vibes', 'outdoor-dining']
    
    result = lookup.lookup_vibe_ids(test_vibes)
    
    print("Vibe IDs:", result['vibe_ids'])
    print("Mapping:", result['mapping'])
    print("Missing slugs:", result['missing_slugs'])