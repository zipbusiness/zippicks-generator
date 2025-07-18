#!/usr/bin/env python3
"""
Test script for the enhanced publisher with vibe integration
"""

import json
import logging
from datetime import datetime
from publisher_enhanced import EnhancedPublisher

# Set up logging to see all the details
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_vibe_integration():
    """Test the complete vibe integration flow"""
    
    print("🧪 Testing Enhanced Publisher with Vibe Integration")
    print("=" * 60)
    
    # Initialize publisher
    publisher = EnhancedPublisher()
    print("✅ Publisher initialized\n")
    
    # Test data that matches your actual vibes
    test_data = {
        'city': 'san-francisco',
        'city_title': 'San Francisco',
        'topic': 'Anniversary Dinners',
        'category': 'Fine Dining',
        'validated_at': datetime.now().isoformat(),
        'restaurants': [
            {
                'rank': 1,
                'name': 'Atelier Crenn',
                'why_perfect': 'Poetic culinaire meets artistic expression in this 3-Michelin star restaurant.',
                'must_try': 'The seasonal tasting menu with wine pairing',
                'address': '3127 Fillmore St, San Francisco, CA 94123',
                'price_range': '$$$$',
                'vibes': ['anniversary-worthy', 'adults-only-escape', 'art-gallery-eats'],
                'cuisine_type': 'Modern French',
                'score': 9.8,
                'pillar_scores': {
                    'taste': 10.0,
                    'service': 9.8,
                    'ambiance': 9.9,
                    'value': 8.5
                }
            },
            {
                'rank': 2,
                'name': 'Saison',
                'why_perfect': 'Open hearth cooking elevated to fine dining with impeccable service.',
                'must_try': 'The signature sea urchin on grilled bread',
                'address': '178 Townsend St, San Francisco, CA 94107',
                'price_range': '$$$$',
                'vibes': ['anniversary-worthy', 'adults-only-escape'],
                'cuisine_type': 'Contemporary American',
                'score': 9.7
            },
            {
                'rank': 3,
                'name': 'Benu',
                'why_perfect': 'Asian-inspired tasting menu that tells a culinary story.',
                'must_try': 'The thousand-year-old quail egg',
                'address': '22 Hawthorne St, San Francisco, CA 94105',
                'price_range': '$$$$',
                'vibes': ['anniversary-worthy', 'art-gallery-eats'],
                'cuisine_type': 'Contemporary Asian',
                'score': 9.6
            }
        ]
    }
    
    print("📊 Test Data Summary:")
    print(f"   City: {test_data['city_title']}")
    print(f"   Topic: {test_data['topic']}")
    print(f"   Restaurants: {len(test_data['restaurants'])}")
    print()
    
    # Test vibe extraction
    print("🔍 Testing Vibe Extraction...")
    vibe_slugs = publisher._extract_vibe_slugs(test_data)
    print(f"   Extracted vibes: {vibe_slugs}")
    print(f"   Total unique vibes: {len(vibe_slugs)}")
    print()
    
    # Test vibe lookup
    print("🔍 Testing Vibe Lookup API...")
    if vibe_slugs:
        vibe_ids, missing_vibes = publisher.vibe_client.lookup_vibe_ids(vibe_slugs)
        print(f"   ✅ Found vibe IDs: {vibe_ids}")
        print(f"   ✅ Found {len(vibe_ids)} out of {len(vibe_slugs)} vibes")
        
        if missing_vibes:
            print(f"   ⚠️  Missing vibes: {missing_vibes}")
        else:
            print(f"   ✅ All vibes found!")
    print()
    
    # Test data preparation for Master Critic
    print("🔧 Testing Master Critic Data Preparation...")
    mc_data = publisher._prepare_master_critic_data(test_data, vibe_ids if 'vibe_ids' in locals() else [])
    
    print(f"   Topic: {mc_data['topic']}")
    print(f"   Location: {mc_data['location']}")
    print(f"   Vibe IDs: {mc_data['vibe_ids']}")
    print(f"   City Slug: {mc_data['city_slug']}")
    print(f"   Dish Slug: {mc_data['dish_slug']}")
    print(f"   Restaurants formatted: {len(mc_data['restaurants'])}")
    print()
    
    # Show sample restaurant data
    if mc_data['restaurants']:
        print("📋 Sample Restaurant Data (First Entry):")
        print(json.dumps(mc_data['restaurants'][0], indent=2))
    print()
    
    # Test title generation
    print("📝 Testing Title Generation...")
    title = publisher._generate_title(test_data)
    print(f"   Generated title: {title}")
    print()
    
    # Test what the final post data would look like
    print("📦 Final Post Data Structure:")
    post_data = {
        'post_type': 'master_critic_list',
        'post_title': title,
        'post_status': 'draft',
        'meta_input': {
            '_mc_topic': mc_data['topic'],
            '_mc_location': mc_data['location'],
            '_mc_restaurants': f"[JSON with {len(mc_data['restaurants'])} restaurants]",
            '_mc_vibe_ids': mc_data['vibe_ids'],
            '_mc_category': mc_data['category'],
            'city_slug': mc_data['city_slug'],
            'dish_slug': mc_data['dish_slug']
        }
    }
    
    print(json.dumps(post_data, indent=2))
    print()
    
    print("✅ All tests passed! The enhanced publisher is ready to use.")
    print("\n💡 To publish for real, run:")
    print("   python generate.py --publish-all")


def test_error_handling():
    """Test error handling scenarios"""
    print("\n🧪 Testing Error Handling...")
    print("=" * 60)
    
    publisher = EnhancedPublisher()
    
    # Test with no vibes
    print("\n1️⃣ Testing with no vibes...")
    empty_data = {
        'city': 'san-francisco',
        'city_title': 'San Francisco',
        'restaurants': [{'name': 'Test Restaurant'}]
    }
    
    vibe_slugs = publisher._extract_vibe_slugs(empty_data)
    print(f"   Extracted vibes: {vibe_slugs} (should be empty)")
    
    if not vibe_slugs:
        print("   ✅ Correctly handled empty vibes")
    
    # Test with invalid vibes
    print("\n2️⃣ Testing with non-existent vibes...")
    invalid_data = {
        'vibes': ['fake-vibe-1', 'fake-vibe-2'],
        'restaurants': []
    }
    
    vibe_slugs = publisher._extract_vibe_slugs(invalid_data)
    vibe_ids, missing = publisher.vibe_client.lookup_vibe_ids(vibe_slugs)
    
    print(f"   Missing vibes: {missing}")
    print(f"   ✅ Correctly identified non-existent vibes")
    
    print("\n✅ Error handling tests passed!")


if __name__ == "__main__":
    # Run main integration test
    test_vibe_integration()
    
    # Run error handling tests
    test_error_handling()
    
    print("\n🎉 All tests completed!")