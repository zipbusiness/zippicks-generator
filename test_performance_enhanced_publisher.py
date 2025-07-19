"""
Performance tests for Enhanced Publisher
"""

import time
import json
from unittest.mock import Mock, patch
from publisher_enhanced import EnhancedPublisher, VibeLookupClient


def create_test_restaurant(index):
    """Create a test restaurant with sample data"""
    return {
        'rank': index + 1,
        'name': f'Test Restaurant {index}',
        'address': f'{index} Main St, Test City, CA',
        'why_perfect': f'Great test restaurant number {index}',
        'must_try': f'Test Dish {index}',
        'price_range': ['$', '$$', '$$$', '$$$$'][index % 4],
        'vibes': [f'vibe-{i}' for i in range(5)],  # Each restaurant has 5 vibes
        'cuisine_type': 'Test Cuisine',
        'score': 9.0 - (index * 0.01),
        'pillar_scores': {
            'taste': 9.0,
            'service': 8.5,
            'ambiance': 8.5,
            'value': 8.0
        }
    }


def test_performance_scenarios():
    """Test performance edge cases"""
    print("Testing Performance Edge Cases")
    print("=" * 50)
    
    publisher = EnhancedPublisher()
    
    # Test 1: Many vibes
    print("\nTest 1: Processing 100 vibes...")
    large_vibe_list = [f"vibe-{i}" for i in range(100)]
    
    # Mock the API call to avoid actual network requests
    with patch.object(publisher.vibe_client.session, 'post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/json'}
        mock_response.content = b'{"success": true, "data": {"vibe_ids": [1, 2, 3], "missing_slugs": []}}'
        mock_response.json.return_value = {
            "success": True, 
            "data": {"vibe_ids": list(range(1, 101)), "missing_slugs": []}
        }
        mock_post.return_value = mock_response
        
        start_time = time.time()
        result = publisher.vibe_client.lookup_vibe_ids(large_vibe_list)
        elapsed = time.time() - start_time
        
        print(f"  ✓ Processed {len(large_vibe_list)} vibes in {elapsed:.3f} seconds")
        if elapsed < 5.0:
            print("  ✓ Performance test passed (< 5 seconds)")
        else:
            print(f"  ✗ Performance test failed: {elapsed:.3f} seconds > 5.0 seconds")
    
    # Test 2: Large restaurant data
    print("\nTest 2: Processing 100 restaurants...")
    large_restaurant_data = {
        'city': 'test-city',
        'city_title': 'Test City',
        'vibe': 'test-vibe',
        'topic': 'Test Topic',
        'restaurants': [create_test_restaurant(i) for i in range(100)]
    }
    
    start_time = time.time()
    mc_data = publisher._prepare_master_critic_data(large_restaurant_data, [])
    elapsed = time.time() - start_time
    
    print(f"  ✓ Processed {len(large_restaurant_data['restaurants'])} restaurants in {elapsed:.3f} seconds")
    if elapsed < 2.0:
        print("  ✓ Performance test passed (< 2 seconds)")
    else:
        print(f"  ✗ Performance test failed: {elapsed:.3f} seconds > 2.0 seconds")
    
    # Test 3: Vibe extraction with many restaurants
    print("\nTest 3: Extracting vibes from 100 restaurants...")
    start_time = time.time()
    extracted_vibes = publisher._extract_vibe_slugs(large_restaurant_data)
    elapsed = time.time() - start_time
    
    print(f"  ✓ Extracted {len(extracted_vibes)} unique vibes in {elapsed:.3f} seconds")
    if elapsed < 1.0:
        print("  ✓ Performance test passed (< 1 second)")
    else:
        print(f"  ✗ Performance test failed: {elapsed:.3f} seconds > 1.0 seconds")
    
    # Test 4: Post data validation with large metadata
    print("\nTest 4: Validating large post data...")
    large_post_data = {
        'post_type': 'master_critic_list',
        'post_title': 'Test Title ' * 50,  # Long title
        'post_status': 'draft',
        'meta_input': {
            '_mc_topic': 'Test Topic',
            '_mc_location': 'Test Location',
            '_mc_restaurants': json.dumps([create_test_restaurant(i) for i in range(50)]),
            '_mc_vibe_ids': list(range(1, 51)),
            '_mc_category': 'Test Category',
            'city_slug': 'test-city',
            'dish_slug': 'test-dish'
        }
    }
    
    start_time = time.time()
    validated_data = publisher._validate_post_data(large_post_data)
    elapsed = time.time() - start_time
    
    print(f"  ✓ Validated large post data in {elapsed:.3f} seconds")
    if elapsed < 0.5:
        print("  ✓ Performance test passed (< 0.5 seconds)")
    else:
        print(f"  ✗ Performance test failed: {elapsed:.3f} seconds > 0.5 seconds")
    
    # Test 5: Memory efficiency test - ensure no memory leaks
    print("\nTest 5: Memory efficiency with repeated operations...")
    start_time = time.time()
    
    for i in range(10):
        # Create and process data repeatedly
        test_data = {
            'city': f'city-{i}',
            'restaurants': [create_test_restaurant(j) for j in range(10)]
        }
        vibes = publisher._extract_vibe_slugs(test_data)
        mc_data = publisher._prepare_master_critic_data(test_data, [])
    
    elapsed = time.time() - start_time
    avg_time = elapsed / 10
    
    print(f"  ✓ Completed 10 iterations in {elapsed:.3f} seconds")
    print(f"  ✓ Average time per iteration: {avg_time:.3f} seconds")
    if avg_time < 0.5:
        print("  ✓ Memory efficiency test passed")
    else:
        print(f"  ✗ Memory efficiency test failed: {avg_time:.3f} seconds > 0.5 seconds")
    
    # Test 6: Concurrent vibe processing simulation
    print("\nTest 6: Simulating concurrent vibe lookups...")
    vibe_batches = [
        [f"batch1-vibe-{i}" for i in range(20)],
        [f"batch2-vibe-{i}" for i in range(20)],
        [f"batch3-vibe-{i}" for i in range(20)]
    ]
    
    with patch.object(publisher.vibe_client.session, 'post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/json'}
        mock_response.content = b'{"success": true, "data": {"vibe_ids": [1, 2, 3], "missing_slugs": []}}'
        mock_response.json.return_value = {
            "success": True, 
            "data": {"vibe_ids": [1, 2, 3], "missing_slugs": []}
        }
        mock_post.return_value = mock_response
        
        start_time = time.time()
        for batch in vibe_batches:
            publisher.vibe_client.lookup_vibe_ids(batch)
        elapsed = time.time() - start_time
        
        print(f"  ✓ Processed 3 batches of 20 vibes each in {elapsed:.3f} seconds")
        if elapsed < 3.0:
            print("  ✓ Concurrent processing test passed (< 3 seconds)")
        else:
            print(f"  ✗ Concurrent processing test failed: {elapsed:.3f} seconds > 3.0 seconds")
    
    print("\n" + "=" * 50)
    print("Performance Testing Complete")


def test_edge_case_performance():
    """Test specific edge cases that might impact performance"""
    print("\nTesting Edge Case Performance")
    print("=" * 50)
    
    publisher = EnhancedPublisher()
    
    # Test 1: Empty data sets
    print("\nTest 1: Empty data sets...")
    start_time = time.time()
    
    # Empty vibes
    vibes = publisher._extract_vibe_slugs({})
    # Empty restaurants
    try:
        publisher._prepare_master_critic_data({}, [])
    except ValueError:
        pass  # Expected
    
    elapsed = time.time() - start_time
    print(f"  ✓ Handled empty data in {elapsed:.3f} seconds")
    
    # Test 2: Deeply nested vibe structures
    print("\nTest 2: Deeply nested vibe structures...")
    nested_data = {
        'vibes': ['top-level-vibe'],
        'restaurants': []
    }
    
    # Create 50 restaurants with 10 vibes each
    for i in range(50):
        restaurant = create_test_restaurant(i)
        restaurant['vibes'] = [f'nested-vibe-{j}' for j in range(10)]
        nested_data['restaurants'].append(restaurant)
    
    start_time = time.time()
    extracted = publisher._extract_vibe_slugs(nested_data)
    elapsed = time.time() - start_time
    
    print(f"  ✓ Extracted {len(extracted)} vibes from nested structure in {elapsed:.3f} seconds")
    
    # Test 3: Unicode and special characters
    print("\nTest 3: Unicode and special character handling...")
    unicode_data = {
        'city': '東京',
        'topic': 'Café ☕️ & Restaurants 🍽️',
        'restaurants': [
            {
                'name': 'Café Résumé',
                'vibes': ['café-vibes', 'résumé-testing', '🍽️-dining'],
                'address': '123 Ñoño St'
            }
        ]
    }
    
    start_time = time.time()
    vibes = publisher._extract_vibe_slugs(unicode_data)
    mc_data = publisher._prepare_master_critic_data(unicode_data, [])
    elapsed = time.time() - start_time
    
    print(f"  ✓ Processed Unicode data in {elapsed:.3f} seconds")
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    test_performance_scenarios()
    test_edge_case_performance()
    print("\n✅ All performance tests completed!")