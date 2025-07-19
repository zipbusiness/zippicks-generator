"""
Edge case tests for Enhanced Publisher
"""

import json
from unittest.mock import Mock, patch
from publisher_enhanced import EnhancedPublisher, VibeLookupClient, VibeLookupValidationError


def test_edge_cases():
    """Test edge cases and boundary conditions"""
    print("Testing Edge Cases and Boundary Conditions")
    print("=" * 50)
    
    publisher = EnhancedPublisher()
    
    # Test 1: Empty data
    print("\nTest 1: Empty data handling...")
    empty_result = publisher._extract_vibe_slugs({})
    assert empty_result == []
    print("  ✓ Empty dict returns empty list")
    
    # Test 2: Malformed data
    print("\nTest 2: Malformed data handling...")
    malformed_data = {
        'vibes': 'not-a-list',
        'restaurants': [{'vibes': 'also-not-a-list'}]
    }
    result = publisher._extract_vibe_slugs(malformed_data)
    assert isinstance(result, list)
    print("  ✓ Malformed vibes handled gracefully")
    
    # Test 3: Unicode handling
    print("\nTest 3: Unicode handling...")
    unicode_data = {
        'vibes': ['café-français', 'résumé-worthy'],
        'restaurants': [{'name': 'Café François'}]
    }
    result = publisher._extract_vibe_slugs(unicode_data)
    assert all(isinstance(v, str) for v in result)
    print("  ✓ Unicode vibes handled correctly")
    
    # Test 4: Duplicate vibes
    print("\nTest 4: Duplicate vibe handling...")
    duplicate_data = {
        'vibes': ['vibe1', 'vibe1', 'VIBE1'],
        'restaurants': [
            {'vibes': ['vibe1', 'vibe2']},
            {'vibes': ['vibe2', 'vibe1']}
        ]
    }
    result = publisher._extract_vibe_slugs(duplicate_data)
    # Should have unique vibes, all lowercase
    assert len(result) == 2  # vibe1 and vibe2
    assert 'vibe1' in result
    assert 'vibe2' in result
    print("  ✓ Duplicates removed, case normalized")
    
    # Test 5: Very long vibes
    print("\nTest 5: Very long vibe names...")
    long_vibe = 'a' * 1000
    long_data = {
        'vibes': [long_vibe],
        'restaurants': [{'vibes': [long_vibe]}]
    }
    result = publisher._extract_vibe_slugs(long_data)
    assert long_vibe in result
    print("  ✓ Long vibe names handled")
    
    # Test 6: Special characters in vibes
    print("\nTest 6: Special characters in vibes...")
    special_data = {
        'vibes': ['vibe-with-dash', 'vibe_with_underscore', 'vibe.with.dot'],
        'restaurants': [{'vibes': ['vibe/with/slash', 'vibe@with@at']}]
    }
    result = publisher._extract_vibe_slugs(special_data)
    assert len(result) == 5
    print("  ✓ Special characters preserved")
    
    # Test 7: Null and None values
    print("\nTest 7: Null and None value handling...")
    null_data = {
        'vibes': [None, 'valid-vibe', None],
        'vibe': None,
        'restaurants': [
            {'vibes': None},
            {'vibes': [None, 'another-valid']},
            None  # Null restaurant
        ]
    }
    result = publisher._extract_vibe_slugs(null_data)
    assert None not in result
    assert 'valid-vibe' in result
    assert 'another-valid' in result
    print("  ✓ Null values filtered out")
    
    # Test 8: Mixed data types
    print("\nTest 8: Mixed data types...")
    mixed_data = {
        'vibes': ['string', 123, 45.67, True, False, {'dict': 'value'}, ['list']],
        'restaurants': [
            {'vibes': ['valid', 999, None]}
        ]
    }
    result = publisher._extract_vibe_slugs(mixed_data)
    # Only string values should be included
    assert 'string' in result
    assert 'valid' in result
    assert len(result) == 2
    print("  ✓ Only string vibes extracted")
    
    # Test 9: Whitespace handling
    print("\nTest 9: Whitespace handling...")
    whitespace_data = {
        'vibes': ['  leading-space', 'trailing-space  ', '  both  ', '\t\ttab', '\n\nnewline'],
        'restaurants': [{'vibes': ['   ', '', '    valid-vibe    ']}]
    }
    result = publisher._extract_vibe_slugs(whitespace_data)
    assert 'leading-space' in result
    assert 'trailing-space' in result
    assert 'both' in result
    assert 'tab' in result
    assert 'newline' in result
    assert 'valid-vibe' in result
    assert '' not in result
    assert '   ' not in result
    print("  ✓ Whitespace trimmed correctly")
    
    # Test 10: Circular reference protection
    print("\nTest 10: Circular reference handling...")
    circular_data = {
        'vibes': ['normal-vibe'],
        'restaurants': []
    }
    # Add circular reference
    circular_data['self_ref'] = circular_data
    try:
        result = publisher._extract_vibe_slugs(circular_data)
        assert 'normal-vibe' in result
        print("  ✓ Circular references handled")
    except RecursionError:
        print("  ✗ Failed to handle circular reference")
    
    # Test 11: Empty strings and edge values
    print("\nTest 11: Empty strings and edge values...")
    edge_data = {
        'vibes': ['', ' ', '  ', '\t', '\n', 'valid'],
        'vibe': '',
        'restaurants': [
            {'vibes': ['', 'another-valid', '   ']}
        ]
    }
    result = publisher._extract_vibe_slugs(edge_data)
    assert '' not in result
    assert 'valid' in result
    assert 'another-valid' in result
    print("  ✓ Empty strings filtered out")
    
    # Test 12: Maximum nesting depth
    print("\nTest 12: Deep nesting...")
    deep_data = {
        'vibes': ['top-level'],
        'restaurants': []
    }
    # Create deeply nested restaurant structure
    for i in range(100):
        deep_data['restaurants'].append({
            'name': f'Restaurant {i}',
            'vibes': [f'nested-{i}'],
            'metadata': {
                'extra': {
                    'deep': {
                        'vibes': ['should-not-extract']  # Not at expected location
                    }
                }
            }
        })
    result = publisher._extract_vibe_slugs(deep_data)
    assert 'top-level' in result
    assert all(f'nested-{i}' in result for i in range(100))
    assert 'should-not-extract' not in result  # Should not extract from deep nesting
    print("  ✓ Deep nesting handled correctly")
    
    # Test 13: Boundary conditions for prepare_master_critic_data
    print("\nTest 13: Prepare data boundary conditions...")
    
    # Test with exactly one restaurant
    single_restaurant = {
        'city': 'Test City',
        'restaurants': [{'name': 'Single Restaurant'}]
    }
    try:
        mc_data = publisher._prepare_master_critic_data(single_restaurant, [])
        assert len(mc_data['restaurants']) == 1
        print("  ✓ Single restaurant handled")
    except Exception as e:
        print(f"  ✗ Failed with single restaurant: {e}")
    
    # Test with maximum vibe IDs
    max_vibes = list(range(1, 1001))  # 1000 vibe IDs
    try:
        mc_data = publisher._prepare_master_critic_data(single_restaurant, max_vibes)
        assert mc_data['vibe_ids'] == max_vibes
        print("  ✓ Large vibe ID list handled")
    except Exception as e:
        print(f"  ✗ Failed with large vibe list: {e}")
    
    print("\n" + "=" * 50)
    print("Edge Case Testing Complete")


def test_error_conditions():
    """Test error conditions and recovery"""
    print("\nTesting Error Conditions and Recovery")
    print("=" * 50)
    
    publisher = EnhancedPublisher()
    
    # Test 1: Invalid data type for prepare_master_critic_data
    print("\nTest 1: Invalid data types...")
    try:
        publisher._prepare_master_critic_data("not a dict", [])
        print("  ✗ Should have raised ValueError")
    except ValueError as e:
        print(f"  ✓ Caught invalid data type: {e}")
    
    # Test 2: Missing restaurants
    print("\nTest 2: Missing restaurants...")
    try:
        publisher._prepare_master_critic_data({'city': 'Test'}, [])
        print("  ✗ Should have raised ValueError")
    except ValueError as e:
        print(f"  ✓ Caught missing restaurants: {e}")
    
    # Test 3: Invalid vibe IDs
    print("\nTest 3: Invalid vibe IDs...")
    test_data = {'restaurants': [{'name': 'Test'}]}
    
    # String vibe_ids
    try:
        publisher._prepare_master_critic_data(test_data, "not a list")
        print("  ✗ Should have raised ValueError")
    except ValueError as e:
        print(f"  ✓ Caught invalid vibe_ids type: {e}")
    
    # Invalid vibe ID values
    try:
        publisher._prepare_master_critic_data(test_data, [0, -1, 'string'])
        print("  ✗ Should have raised ValueError")
    except ValueError as e:
        print(f"  ✓ Caught invalid vibe ID: {e}")
    
    # Test 4: URL validation edge cases
    print("\nTest 4: URL validation edge cases...")
    
    # Valid edge cases that should pass
    valid_urls = [
        "http://localhost",
        "https://example.com:8080",
        "https://sub.domain.example.com",
        "http://192.168.1.1"
    ]
    
    for url in valid_urls:
        try:
            client = VibeLookupClient(url)
            print(f"  ✓ Accepted valid URL: {url}")
        except ValueError:
            print(f"  ✗ Rejected valid URL: {url}")
    
    # Invalid URLs that should fail
    invalid_urls = [
        "http://",
        "https://",
        "http://example.com/../etc",
        "https://example.com//path",
        "http://example.com/path?../../etc"
    ]
    
    for url in invalid_urls:
        try:
            client = VibeLookupClient(url)
            print(f"  ✗ Accepted invalid URL: {url}")
        except ValueError:
            print(f"  ✓ Rejected invalid URL: {url}")
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    test_edge_cases()
    test_error_conditions()
    print("\n✅ All edge case tests completed!")