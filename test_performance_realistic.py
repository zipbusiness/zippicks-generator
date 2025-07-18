"""
Realistic performance tests with actual timing
"""

import time
import json
from publisher_enhanced import EnhancedPublisher


def simulate_processing_delay(seconds=0.001):
    """Simulate a small processing delay"""
    time.sleep(seconds)


def test_realistic_performance():
    """Test with realistic processing times"""
    print("Realistic Performance Tests")
    print("=" * 50)
    
    publisher = EnhancedPublisher()
    
    # Test 1: Large batch vibe extraction
    print("\nTest 1: Extracting vibes from 1000 restaurants...")
    large_data = {
        'vibes': ['main-vibe-1', 'main-vibe-2'],
        'restaurants': []
    }
    
    # Create 1000 restaurants with varying numbers of vibes
    for i in range(1000):
        restaurant = {
            'name': f'Restaurant {i}',
            'vibes': [f'vibe-{j}' for j in range(i % 10)]  # 0-9 vibes per restaurant
        }
        large_data['restaurants'].append(restaurant)
    
    start_time = time.time()
    vibes = publisher._extract_vibe_slugs(large_data)
    elapsed = time.time() - start_time
    
    print(f"  Extracted {len(vibes)} unique vibes from 1000 restaurants")
    print(f"  Time taken: {elapsed:.3f} seconds")
    print(f"  {'✓' if elapsed < 1.0 else '✗'} Performance: {'PASS' if elapsed < 1.0 else 'FAIL'} (target < 1.0s)")
    
    # Test 2: Heavy data preparation
    print("\nTest 2: Preparing data for 500 restaurants...")
    heavy_data = {
        'city': 'San Francisco',
        'topic': 'Best Restaurants',
        'restaurants': []
    }
    
    for i in range(500):
        restaurant = {
            'rank': i + 1,
            'name': f'Restaurant {i}',
            'address': f'{i} Main Street, San Francisco, CA 94102',
            'why_perfect': 'A' * 200,  # Long description
            'must_try': f'Dish {i}',
            'price_range': '$$',
            'vibes': [f'vibe-{j}' for j in range(5)],
            'cuisine_type': 'American',
            'pillar_scores': {
                'taste': 9.0,
                'service': 8.5,
                'ambiance': 8.0,
                'value': 7.5
            }
        }
        heavy_data['restaurants'].append(restaurant)
    
    start_time = time.time()
    mc_data = publisher._prepare_master_critic_data(heavy_data, list(range(1, 11)))
    elapsed = time.time() - start_time
    
    print(f"  Prepared data for {len(heavy_data['restaurants'])} restaurants")
    print(f"  Time taken: {elapsed:.3f} seconds")
    print(f"  {'✓' if elapsed < 2.0 else '✗'} Performance: {'PASS' if elapsed < 2.0 else 'FAIL'} (target < 2.0s)")
    
    # Test 3: Post validation with large JSON
    print("\nTest 3: Validating post with large JSON metadata...")
    large_json_data = {
        'post_type': 'master_critic_list',
        'post_title': 'Test Post with Large Data',
        'post_status': 'draft',
        'meta_input': {
            '_mc_restaurants': json.dumps([{
                'name': f'Restaurant {i}',
                'data': 'x' * 1000  # 1KB per restaurant
            } for i in range(100)]),  # 100KB total
            '_mc_vibe_ids': list(range(1, 101))
        }
    }
    
    start_time = time.time()
    validated = publisher._validate_post_data(large_json_data)
    elapsed = time.time() - start_time
    
    print(f"  Validated post with ~100KB JSON metadata")
    print(f"  Time taken: {elapsed:.3f} seconds")
    print(f"  {'✓' if elapsed < 0.5 else '✗'} Performance: {'PASS' if elapsed < 0.5 else 'FAIL'} (target < 0.5s)")
    
    # Test 4: Repeated operations (memory leak test)
    print("\nTest 4: Repeated operations (1000 iterations)...")
    start_time = time.time()
    
    for i in range(1000):
        small_data = {
            'city': f'city-{i % 10}',
            'restaurants': [{
                'name': f'Restaurant {i}',
                'vibes': ['vibe-1', 'vibe-2']
            }]
        }
        vibes = publisher._extract_vibe_slugs(small_data)
        if i % 100 == 0:
            simulate_processing_delay()  # Simulate some work
    
    elapsed = time.time() - start_time
    avg_time = elapsed / 1000
    
    print(f"  Completed 1000 iterations")
    print(f"  Total time: {elapsed:.3f} seconds")
    print(f"  Average time per iteration: {avg_time * 1000:.3f} ms")
    print(f"  {'✓' if avg_time < 0.01 else '✗'} Performance: {'PASS' if avg_time < 0.01 else 'FAIL'} (target < 10ms/iter)")
    
    # Test 5: Worst case - all different vibes
    print("\nTest 5: Worst case - 10,000 unique vibes...")
    worst_case_data = {
        'restaurants': []
    }
    
    # Create restaurants where each has unique vibes
    for i in range(1000):
        restaurant = {
            'name': f'Restaurant {i}',
            'vibes': [f'unique-vibe-{i}-{j}' for j in range(10)]  # 10 unique vibes per restaurant
        }
        worst_case_data['restaurants'].append(restaurant)
    
    start_time = time.time()
    vibes = publisher._extract_vibe_slugs(worst_case_data)
    elapsed = time.time() - start_time
    
    print(f"  Extracted {len(vibes)} unique vibes")
    print(f"  Time taken: {elapsed:.3f} seconds")
    print(f"  {'✓' if elapsed < 2.0 else '✗'} Performance: {'PASS' if elapsed < 2.0 else 'FAIL'} (target < 2.0s)")
    
    print("\n" + "=" * 50)
    print("Performance Test Summary")
    print("=" * 50)
    print("\nAll tests measure real-world scenarios with actual data processing.")
    print("Targets are based on reasonable expectations for production use.")


if __name__ == "__main__":
    test_realistic_performance()