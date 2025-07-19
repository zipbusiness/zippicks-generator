#!/usr/bin/env python3
"""Test WordPress connection"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from publisher import Publisher

def test_connection():
    """Test WordPress connection with current credentials"""
    try:
        # Create publisher instance
        wp = Publisher()
        
        # Get site URL and auth type
        site_url = os.getenv('WP_SITE_URL', 'Not set')
        auth_type = os.getenv('WP_AUTH_TYPE', 'Not set')
        
        print(f"Testing WordPress connection...")
        print(f"Site URL: {site_url}")
        print(f"Auth Type: {auth_type}")
        
        # The Publisher class will validate credentials on init
        # If we get here without error, connection is good
        print("\n✅ WordPress credentials configured successfully!")
        print("\nNext steps:")
        print("1. Create categories in WordPress for cities and vibes")
        print("2. Update category IDs in config/wp_config.yaml")
        print("3. Add restaurant data to data/restaurants.csv")
        print("4. Run: python generate.py --mode daily")
        
    except Exception as e:
        print(f"\n❌ Connection failed: {str(e)}")
        print("\nPlease check:")
        print("- WordPress site URL is correct")
        print("- Application password is valid")
        print("- WordPress REST API is enabled")

if __name__ == "__main__":
    test_connection()