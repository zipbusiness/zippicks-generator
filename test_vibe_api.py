#!/usr/bin/env python3
"""Test the ZipPicks Vibe API endpoint"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_vibe_api():
    """Test the vibe lookup API endpoint"""
    
    # Get credentials from environment
    site_url = os.getenv('WP_SITE_URL', '').rstrip('/')
    api_key = os.getenv('WP_API_KEY', '')
    
    if not site_url:
        print("❌ Error: WP_SITE_URL not set in .env")
        return
    
    if not api_key:
        print("❌ Error: WP_API_KEY not set in .env")
        return
    
    print(f"Testing vibe API at: {site_url}")
    print("-" * 50)
    
    # Test endpoint
    endpoint = f"{site_url}/wp-json/zippicks/v1/vibes/lookup"
    
    # Test vibes - using common ones from your config
    test_slugs = [
        'date-night',
        'family-friendly',
        'trendy-vibes',
        'outdoor-dining',
        'hidden-gems',
        'invalid-vibe-test'  # This one shouldn't exist
    ]
    
    # Prepare request
    headers = {
        'Content-Type': 'application/json',
    }
    
    # Use Basic auth with application password
    # WordPress expects username:password, but for app passwords, username can be anything
    auth = ('api', api_key)
    
    data = {
        'slugs': test_slugs
    }
    
    print(f"Testing with slugs: {test_slugs}")
    print("-" * 50)
    
    try:
        # Make the request
        response = requests.post(
            endpoint,
            json=data,
            headers=headers,
            auth=auth,
            timeout=10
        )
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success'):
                print("✅ API call successful!")
                print("\nResults:")
                print(f"- Vibe IDs found: {result['data']['vibe_ids']}")
                print(f"- Total found: {result['data']['found_count']}")
                print(f"- Missing slugs: {result['data']['missing_slugs']}")
                
                print("\nVibe Mapping:")
                for slug, info in result['data']['mapping'].items():
                    print(f"  {slug}: ID={info['id']}, Name='{info['name']}'")
                    
            else:
                print(f"❌ API returned error: {result.get('message', 'Unknown error')}")
                
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response body: {e.response.text}")
    
    print("\n" + "-" * 50)
    print("Test complete!")

if __name__ == "__main__":
    test_vibe_api()