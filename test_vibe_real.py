#!/usr/bin/env python3
"""Test the vibe API with actual vibe slugs from the database"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Get credentials
site_url = os.getenv('WP_SITE_URL', '').rstrip('/')
api_key = os.getenv('WP_API_KEY', '')

endpoint = f"{site_url}/wp-json/zippicks/v1/vibes/lookup"

# Test with actual slugs from your database
test_slugs = [
    'adults-only-escape',
    'after-school-special', 
    'all-you-can-eat',
    'anniversary-worthy',
    'art-gallery-eats',
    'bachelor-party-approved',
    'date-night',  # This might not exist, but let's test
    'family-friendly'  # This might not exist, but let's test
]

auth = ('api', api_key)

print(f"Testing vibe API with real slugs from database\n")
print(f"Endpoint: {endpoint}")
print(f"Test slugs: {test_slugs}\n")

response = requests.post(
    endpoint,
    json={'slugs': test_slugs},
    auth=auth,
    timeout=10
)

print(f"Response Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    if data['success']:
        print("✅ Success!\n")
        print(f"Found {data['data']['found_count']} vibes")
        print(f"Vibe IDs: {data['data']['vibe_ids']}")
        print(f"Missing slugs: {data['data']['missing_slugs']}")
        
        print("\nVibe Mapping:")
        mapping = data['data']['mapping']
        if isinstance(mapping, dict):
            for slug, info in mapping.items():
                print(f"  {slug}: ID={info['id']}, Name='{info['name']}'")
    else:
        print(f"❌ API Error: {data.get('message')}")
else:
    print(f"❌ HTTP Error: {response.status_code}")
    print(f"Response: {response.text}")