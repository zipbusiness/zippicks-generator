"""
Manual security tests for Enhanced Publisher
"""

import json
import requests
from unittest.mock import Mock, patch
from publisher_enhanced import EnhancedPublisher, VibeLookupClient, VibeLookupError, VibeLookupValidationError


def test_url_injection_protection():
    """Test URL injection protection"""
    print("Testing URL injection protection...")
    
    # Test various malicious URL patterns
    malicious_urls = [
        "http://evil.com/../../../etc/passwd",
        "https://site.com/wp-json/../../admin",
        "javascript:alert('xss')",
        "file:///etc/passwd",
        "",  # Empty URL
        "not-a-url",  # Invalid URL
        "ftp://site.com",  # Non-HTTP protocol
    ]
    
    for url in malicious_urls:
        try:
            VibeLookupClient(url)
            print(f"  ✗ Failed to catch malicious URL: {url}")
            return False
        except ValueError:
            print(f"  ✓ Caught malicious URL: {url}")
    
    return True


def test_oversized_response_protection():
    """Test oversized response handling"""
    print("\nTesting oversized response protection...")
    
    client = VibeLookupClient("https://example.com")
    
    # Create mock response with large content
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'content-type': 'application/json'}
    mock_response.content = b'x' * (1024 * 1024 + 1)  # Over 1MB
    
    try:
        client._validate_api_response(mock_response)
        print("  ✗ Failed to catch oversized response")
        return False
    except ValueError as e:
        if "Response too large" in str(e):
            print("  ✓ Caught oversized response")
            return True
        print(f"  ✗ Wrong error: {e}")
        return False


def test_malformed_json_response():
    """Test malformed JSON response handling"""
    print("\nTesting malformed JSON response...")
    
    client = VibeLookupClient("https://example.com")
    
    # Create mock response with invalid JSON
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'content-type': 'application/json'}
    mock_response.content = b'{"invalid": json'
    mock_response.json.side_effect = json.JSONDecodeError("test", "doc", 0)
    
    try:
        client._validate_api_response(mock_response)
        print("  ✗ Failed to catch malformed JSON")
        return False
    except ValueError as e:
        if "Invalid JSON response" in str(e):
            print("  ✓ Caught malformed JSON")
            return True
        print(f"  ✗ Wrong error: {e}")
        return False


def test_invalid_vibe_ids_validation():
    """Test invalid vibe IDs validation"""
    print("\nTesting invalid vibe IDs validation...")
    
    publisher = EnhancedPublisher()
    test_data = {
        'city': 'test-city',
        'restaurants': [{'name': 'Test Restaurant'}]
    }
    
    # Test with string vibe IDs
    try:
        publisher._prepare_master_critic_data(test_data, "invalid")
        print("  ✗ Failed to catch string vibe_ids")
        return False
    except ValueError as e:
        if "vibe_ids must be a list" in str(e):
            print("  ✓ Caught string vibe_ids")
        else:
            print(f"  ✗ Wrong error: {e}")
            return False
    
    # Test with negative vibe IDs
    try:
        publisher._prepare_master_critic_data(test_data, [-1, 0])
        print("  ✗ Failed to catch invalid vibe IDs")
        return False
    except ValueError as e:
        if "Invalid vibe ID" in str(e):
            print("  ✓ Caught invalid vibe IDs")
        else:
            print(f"  ✗ Wrong error: {e}")
            return False
    
    return True


def test_vibe_extraction_edge_cases():
    """Test vibe extraction with edge cases"""
    print("\nTesting vibe extraction edge cases...")
    
    publisher = EnhancedPublisher()
    
    # Test with None (should return empty list due to warning log)
    result = publisher._extract_vibe_slugs(None)
    if result == []:
        print("  ✓ Handled None input")
    else:
        print(f"  ✗ Wrong result for None: {result}")
        return False
    
    # Test with non-dict
    result = publisher._extract_vibe_slugs("not a dict")
    if result == []:
        print("  ✓ Handled non-dict input")
    else:
        print(f"  ✗ Wrong result for non-dict: {result}")
        return False
    
    # Test with invalid vibe types
    data = {
        'vibes': [123, None, "", "  ", "valid-vibe"],
        'restaurants': [
            {'vibes': ["another-vibe", 456, None]}
        ]
    }
    result = publisher._extract_vibe_slugs(data)
    if set(result) == {"valid-vibe", "another-vibe"}:
        print("  ✓ Filtered invalid vibe types correctly")
    else:
        print(f"  ✗ Wrong filtering result: {result}")
        return False
    
    return True


def test_post_data_validation():
    """Test post data validation"""
    print("\nTesting post data validation...")
    
    publisher = EnhancedPublisher()
    
    # Test missing required fields
    try:
        publisher._validate_post_data({'post_title': 'Test'})
        print("  ✗ Failed to catch missing required field")
        return False
    except ValueError as e:
        if "Missing required field: post_type" in str(e):
            print("  ✓ Caught missing required field")
        else:
            print(f"  ✗ Wrong error: {e}")
            return False
    
    # Test invalid post type
    try:
        publisher._validate_post_data({
            'post_type': 'malicious_type',
            'post_title': 'Test',
            'post_status': 'draft'
        })
        print("  ✗ Failed to catch invalid post type")
        return False
    except ValueError as e:
        if "Invalid post type" in str(e):
            print("  ✓ Caught invalid post type")
        else:
            print(f"  ✗ Wrong error: {e}")
            return False
    
    # Test title truncation
    post_data = {
        'post_type': 'post',
        'post_title': 'x' * 300,  # Over 200 chars
        'post_status': 'draft'
    }
    validated = publisher._validate_post_data(post_data)
    if len(validated['post_title']) == 200:
        print("  ✓ Title truncated correctly")
    else:
        print(f"  ✗ Title not truncated: {len(validated['post_title'])}")
        return False
    
    return True


def run_all_tests():
    """Run all security tests"""
    print("Running Enhanced Publisher Security Tests")
    print("=" * 50)
    
    tests = [
        test_url_injection_protection,
        test_oversized_response_protection,
        test_malformed_json_response,
        test_invalid_vibe_ids_validation,
        test_vibe_extraction_edge_cases,
        test_post_data_validation
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n✗ Test {test.__name__} failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    if failed == 0:
        print("\n✅ All security tests passed!")
    else:
        print("\n❌ Some tests failed!")


if __name__ == "__main__":
    run_all_tests()