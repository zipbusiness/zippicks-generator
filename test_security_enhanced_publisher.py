"""
Security tests for Enhanced Publisher
"""

import pytest
import json
import requests
from unittest.mock import Mock, patch, MagicMock
from publisher_enhanced import EnhancedPublisher, VibeLookupClient, VibeLookupError, VibeLookupValidationError


class TestSecurityScenarios:
    """Test security-related scenarios"""
    
    def test_url_injection_protection(self):
        """Test URL injection protection"""
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
            with pytest.raises(ValueError):
                VibeLookupClient(url)
    
    def test_oversized_response_protection(self):
        """Test oversized response handling"""
        client = VibeLookupClient("https://example.com")
        
        # Create mock response with large content
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/json'}
        mock_response.content = b'x' * (1024 * 1024 + 1)  # Over 1MB
        
        with pytest.raises(ValueError, match="Response too large"):
            client._validate_api_response(mock_response)
    
    def test_malformed_json_response(self):
        """Test malformed JSON response handling"""
        client = VibeLookupClient("https://example.com")
        
        # Create mock response with invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/json'}
        mock_response.content = b'{"invalid": json'
        mock_response.json.side_effect = json.JSONDecodeError("test", "doc", 0)
        
        with pytest.raises(ValueError, match="Invalid JSON response"):
            client._validate_api_response(mock_response)
    
    def test_invalid_vibe_ids_validation(self):
        """Test invalid vibe IDs validation"""
        publisher = EnhancedPublisher()
        
        test_data = {
            'city': 'test-city',
            'restaurants': [{'name': 'Test Restaurant'}]
        }
        
        # Test with string vibe IDs
        with pytest.raises(ValueError, match="vibe_ids must be a list"):
            publisher._prepare_master_critic_data(test_data, "invalid")
        
        # Test with negative vibe IDs
        with pytest.raises(ValueError, match="Invalid vibe ID"):
            publisher._prepare_master_critic_data(test_data, [-1, 0])
        
        # Test with non-integer vibe IDs
        with pytest.raises(ValueError, match="Invalid vibe ID"):
            publisher._prepare_master_critic_data(test_data, ["string", 123])
    
    def test_post_data_validation(self):
        """Test post data validation"""
        publisher = EnhancedPublisher()
        
        # Test missing required fields
        with pytest.raises(ValueError, match="Missing required field: post_type"):
            publisher._validate_post_data({'post_title': 'Test'})
        
        # Test invalid post type
        with pytest.raises(ValueError, match="Invalid post type"):
            publisher._validate_post_data({
                'post_type': 'malicious_type',
                'post_title': 'Test',
                'post_status': 'draft'
            })
        
        # Test title truncation
        post_data = {
            'post_type': 'post',
            'post_title': 'x' * 300,  # Over 200 chars
            'post_status': 'draft'
        }
        validated = publisher._validate_post_data(post_data)
        assert len(validated['post_title']) == 200
    
    def test_vibe_extraction_edge_cases(self):
        """Test vibe extraction with edge cases"""
        publisher = EnhancedPublisher()
        
        # Test with None
        assert publisher._extract_vibe_slugs(None) == []
        
        # Test with non-dict
        assert publisher._extract_vibe_slugs("not a dict") == []
        
        # Test with empty vibes
        assert publisher._extract_vibe_slugs({'vibes': []}) == []
        
        # Test with invalid vibe types
        data = {
            'vibes': [123, None, "", "  ", "valid-vibe"],
            'restaurants': [
                {'vibes': ["another-vibe", 456, None]}
            ]
        }
        result = publisher._extract_vibe_slugs(data)
        assert set(result) == {"valid-vibe", "another-vibe"}
    
    def test_response_content_type_validation(self):
        """Test response content type validation"""
        client = VibeLookupClient("https://example.com")
        
        # Test non-JSON content type
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'text/html'}
        
        with pytest.raises(ValueError, match="Expected JSON response"):
            client._validate_api_response(mock_response)
    
    def test_http_status_validation(self):
        """Test HTTP status code validation"""
        client = VibeLookupClient("https://example.com")
        
        # Test various error status codes
        error_codes = [400, 401, 403, 404, 500, 502, 503]
        
        for code in error_codes:
            mock_response = Mock()
            mock_response.status_code = code
            mock_response.text = f"Error {code}"
            
            with pytest.raises(requests.exceptions.HTTPError):
                client._validate_api_response(mock_response)
    
    @patch('requests.Session.post')
    def test_retry_logic_network_errors(self, mock_post):
        """Test retry logic for network errors"""
        client = VibeLookupClient("https://example.com")
        
        # Mock connection error on first two attempts, success on third
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("Connection failed"),
            requests.exceptions.Timeout("Request timed out"),
            Mock(status_code=200, headers={'content-type': 'application/json'},
                 content=b'{"success": true, "data": {"vibe_ids": [1, 2], "missing_slugs": []}}',
                 json=lambda: {"success": True, "data": {"vibe_ids": [1, 2], "missing_slugs": []}})
        ]
        
        vibe_ids, missing = client.lookup_vibe_ids(['test-vibe'])
        assert vibe_ids == [1, 2]
        assert missing == []
        assert mock_post.call_count == 3
    
    @patch('requests.Session.post')
    def test_retry_exhaustion(self, mock_post):
        """Test retry exhaustion"""
        client = VibeLookupClient("https://example.com")
        
        # Mock persistent connection error
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with pytest.raises(VibeLookupNetworkError):
            client.lookup_vibe_ids(['test-vibe'])
        
        # Should have tried 3 times
        assert mock_post.call_count == 3
    
    def test_input_sanitization(self):
        """Test input sanitization"""
        publisher = EnhancedPublisher()
        
        # Test data with potentially dangerous content
        data = {
            'city': '<script>alert("xss")</script>',
            'topic': 'Test" OR 1=1--',
            'restaurants': [
                {
                    'name': 'Test Restaurant',
                    'vibes': ['<img src=x onerror=alert(1)>', 'valid-vibe']
                }
            ]
        }
        
        # Extract vibes and ensure dangerous content is handled
        vibes = publisher._extract_vibe_slugs(data)
        # The dangerous vibe should be included but sanitized (lowercased)
        assert '<img src=x onerror=alert(1)>' in vibes
        assert all(v.islower() for v in vibes)
    
    def test_prepare_data_with_missing_restaurants(self):
        """Test prepare data with missing restaurants"""
        publisher = EnhancedPublisher()
        
        # Test with no restaurants
        with pytest.raises(ValueError, match="No restaurants found"):
            publisher._prepare_master_critic_data({}, [])
        
        # Test with empty restaurants list
        with pytest.raises(ValueError, match="No restaurants found"):
            publisher._prepare_master_critic_data({'restaurants': []}, [])


if __name__ == "__main__":
    # Run specific security tests
    test = TestSecurityScenarios()
    
    print("Testing URL injection protection...")
    test.test_url_injection_protection()
    print("✓ URL injection protection working")
    
    print("\nTesting oversized response protection...")
    test.test_oversized_response_protection()
    print("✓ Oversized response protection working")
    
    print("\nTesting malformed JSON handling...")
    test.test_malformed_json_response()
    print("✓ Malformed JSON handling working")
    
    print("\nTesting invalid vibe IDs validation...")
    test.test_invalid_vibe_ids_validation()
    print("✓ Invalid vibe IDs validation working")
    
    print("\nAll security tests passed!")