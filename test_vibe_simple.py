#!/usr/bin/env python3
"""Simple test of the vibe API to check what vibes exist"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Get credentials
site_url = os.getenv('WP_SITE_URL', '').rstrip('/')
api_key = os.getenv('WP_API_KEY', '')

endpoint = f"{site_url}/wp-json/zippicks/v1/vibes/lookup"

# Test with a few different slug formats
test_sets = [
    # Common vibe names as slugs
    ['date-night', 'family-friendly'],
    # Without hyphens
    ['datenight', 'familyfriendly'],
    # Capitalized
    ['Date-Night', 'Family-Friendly'],
    # Single words
    ['romantic', 'casual', 'upscale'],
    # From your vibes.yaml config
    ['date_night', 'family_friendly', 'quick_lunch', 'trendy_vibes']
]

auth = ('api', api_key)

print(f"Testing vibe API: {endpoint}\n")

for i, slugs in enumerate(test_sets):
    print(f"Test {i+1}: {slugs}")
    
    response = requests.post(
        endpoint,
        json={'slugs': slugs},
        auth=auth,
        timeout=5
    )
    
    if response.status_code == 200:
        data = response.json()
        if data['success']:
            found = data['data']['found_count']
            ids = data['data']['vibe_ids']
            print(f"  ✓ Found {found} vibes: {ids}")
            if data['data']['mapping']:
                print(f"  Mapping: {data['data']['mapping']}")
        else:
            print(f"  ✗ Error: {data.get('message')}")
    else:
        print(f"  ✗ HTTP {response.status_code}")
    
    print()

print("\nNote: If all tests return 0 vibes, the database table might:")
print("- Use different slug formats")
print("- Be empty") 
print("- Have different vibe names than expected")