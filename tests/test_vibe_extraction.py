"""
Tests for the Taste Graph vibe extraction system

Tests the core components without requiring external API calls.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import numpy as np

# Add parent directory to path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from taste_graph.core.vibe_extractor import VibeExtractor, VibeProfile
from taste_graph.core.taste_engine import TasteEngine, UserTasteProfile, TasteMatch
from taste_graph.core.relationship_mapper import RelationshipMapper, RestaurantRelationship


class TestVibeExtractor(unittest.TestCase):
    """Test the vibe extraction functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the Anthropic client
        self.mock_api_key = "test_api_key"
        
        with patch('taste_graph.core.vibe_extractor.anthropic.Anthropic'):
            self.extractor = VibeExtractor(self.mock_api_key)
    
    def test_vibe_taxonomy_loaded(self):
        """Test that vibe taxonomy is properly loaded."""
        self.assertIn('atmosphere', self.extractor.vibe_taxonomy)
        self.assertIn('casual', self.extractor.vibe_taxonomy['atmosphere'])
        self.assertIn('energy', self.extractor.vibe_taxonomy)
    
    def test_parse_response(self):
        """Test JSON response parsing."""
        # Test valid JSON
        response = '{"primary_vibes": [{"vibe": "casual", "score": 0.8}], "energy_level": 0.6}'
        parsed = self.extractor._parse_response(response)
        
        self.assertEqual(parsed['primary_vibes'][0]['vibe'], 'casual')
        self.assertEqual(parsed['energy_level'], 0.6)
        
        # Test JSON with extra text
        response_with_text = 'Here is the analysis: {"primary_vibes": [{"vibe": "upscale", "score": 0.9}]}'
        parsed = self.extractor._parse_response(response_with_text)
        
        self.assertEqual(parsed['primary_vibes'][0]['vibe'], 'upscale')
    
    def test_validate_vibes(self):
        """Test vibe validation against taxonomy."""
        extracted_data = {
            "primary_vibes": [
                {"vibe": "casual", "score": 0.8},
                {"vibe": "invalid_vibe", "score": 0.5},
                {"vibe": "trendy", "score": 1.5}  # Score out of range
            ],
            "secondary_vibes": [
                {"vibe": "romantic", "score": 0.6}
            ],
            "energy_level": 0.7,
            "formality_level": 0.3
        }
        
        validated = self.extractor._validate_vibes(extracted_data)
        
        # Check that invalid vibe was removed
        vibe_names = [v['vibe'] for v in validated['primary']]
        self.assertIn('casual', vibe_names)
        self.assertNotIn('invalid_vibe', vibe_names)
        
        # Check that score was clamped
        trendy_vibe = next(v for v in validated['primary'] if v['vibe'] == 'trendy')
        self.assertEqual(trendy_vibe['score'], 1.0)
    
    def test_calculate_confidence(self):
        """Test confidence calculation."""
        # Complete data
        complete_data = {
            "description": "A great restaurant",
            "reviews": ["Review 1", "Review 2", "Review 3", "Review 4", "Review 5"]
        }
        
        validated_vibes = {
            "primary": [{"vibe": "casual", "score": 0.9}],
            "secondary": [{"vibe": "lively", "score": 0.7}]
        }
        
        confidence = self.extractor._calculate_confidence(complete_data, validated_vibes)
        self.assertGreater(confidence, 0.5)
        
        # Minimal data
        minimal_data = {"description": ""}
        confidence_minimal = self.extractor._calculate_confidence(minimal_data, validated_vibes)
        self.assertLess(confidence_minimal, confidence)


class TestTasteEngine(unittest.TestCase):
    """Test the taste engine functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = TasteEngine()
        
        # Create test user data
        self.test_user_data = {
            "user_id": "test_user_123",
            "preferred_vibes": {"casual": 0.8, "lively": 0.6},
            "avoided_vibes": {"formal": 0.7, "loud": 0.9},
            "cuisine_preferences": {"italian": 0.9, "thai": 0.7, "mexican": 0.8},
            "social_style": "couples",
            "history": [
                {
                    "cuisine": "italian",
                    "rating": 5,
                    "vibes": ["romantic", "upscale"],
                    "price_range": 3
                },
                {
                    "cuisine": "thai",
                    "rating": 4,
                    "vibes": ["casual", "lively"],
                    "price_range": 2
                }
            ]
        }
        
        # Create test restaurant data
        self.test_restaurant = {
            "id": "rest_123",
            "name": "Test Restaurant",
            "cuisine": "italian",
            "price_range": 3,
            "vibe_profile": {
                "primary_vibes": [
                    {"vibe": "casual", "score": 0.8},
                    {"vibe": "romantic", "score": 0.7}
                ],
                "secondary_vibes": [
                    {"vibe": "intimate", "score": 0.5}
                ],
                "energy_level": 0.4,
                "formality_level": 0.6
            }
        }
    
    def test_create_taste_profile(self):
        """Test creating a user taste profile."""
        profile = self.engine.create_taste_profile(self.test_user_data)
        
        self.assertEqual(profile.user_id, "test_user_123")
        self.assertIn("casual", profile.preferred_vibes)
        self.assertIn("italian", profile.cuisine_preferences)
        self.assertEqual(profile.social_dining_style, "couples")
    
    def test_calculate_vibe_alignment(self):
        """Test vibe alignment calculation."""
        preferred = {"casual": 0.8, "romantic": 0.6}
        avoided = {"loud": 0.9, "crowded": 0.7}
        restaurant_vibes = {"casual": 0.8, "romantic": 0.7, "intimate": 0.5}
        
        alignment = self.engine._calculate_vibe_alignment(preferred, avoided, restaurant_vibes)
        
        # Should have high alignment due to matching preferred vibes
        self.assertGreater(alignment, 0.7)
    
    def test_calculate_cuisine_match(self):
        """Test cuisine matching."""
        preferences = {"italian": 0.9, "french": 0.7, "japanese": 0.5}
        
        # Exact match
        match_exact = self.engine._calculate_cuisine_match(preferences, "italian")
        self.assertEqual(match_exact, 0.9)
        
        # Similar cuisine (european)
        match_similar = self.engine._calculate_cuisine_match(preferences, "spanish")
        self.assertGreater(match_similar, 0.3)
        
        # Unknown cuisine
        match_unknown = self.engine._calculate_cuisine_match(preferences, "ethiopian")
        self.assertLess(match_unknown, 0.5)
    
    def test_calculate_price_match(self):
        """Test price matching based on sensitivity."""
        # High sensitivity (prefers cheap)
        match_sensitive = self.engine._calculate_price_match(0.8, 4)  # $$$$ restaurant
        self.assertLess(match_sensitive, 0.5)
        
        # Low sensitivity (doesn't care about price)
        match_insensitive = self.engine._calculate_price_match(0.2, 4)
        self.assertGreater(match_insensitive, 0.7)
        
        # Medium sensitivity with medium price
        match_medium = self.engine._calculate_price_match(0.5, 2)  # $$ restaurant
        self.assertGreater(match_medium, 0.8)
    
    def test_calculate_match(self):
        """Test overall match calculation."""
        profile = self.engine.create_taste_profile(self.test_user_data)
        
        # Test with context
        context = {
            "time": "dinner",
            "weather": "rain",
            "occasion": "date",
            "group_size": 2
        }
        
        match = self.engine.calculate_match(profile, self.test_restaurant, context)
        
        self.assertIsInstance(match, TasteMatch)
        self.assertEqual(match.restaurant_id, "rest_123")
        self.assertGreater(match.match_score, 0)
        self.assertLessEqual(match.match_score, 1)
        
        # Check that all component scores are calculated
        self.assertIsNotNone(match.vibe_alignment)
        self.assertIsNotNone(match.cuisine_match)
        self.assertIsNotNone(match.price_match)
        self.assertIsNotNone(match.context_score)


class TestRelationshipMapper(unittest.TestCase):
    """Test the relationship mapping functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mapper = RelationshipMapper()
        
        # Create test restaurants
        self.test_restaurants = [
            {
                "id": "rest_1",
                "name": "Italian Bistro",
                "cuisine": "italian",
                "price_range": 3,
                "location": {"city": "New York", "neighborhood": "SoHo"},
                "vibe_profile": {
                    "primary_vibes": [
                        {"vibe": "romantic", "score": 0.8},
                        {"vibe": "upscale", "score": 0.7}
                    ],
                    "secondary_vibes": [{"vibe": "intimate", "score": 0.6}],
                    "energy_level": 0.3,
                    "formality_level": 0.8
                }
            },
            {
                "id": "rest_2",
                "name": "French Restaurant",
                "cuisine": "french",
                "price_range": 3,
                "location": {"city": "New York", "neighborhood": "SoHo"},
                "vibe_profile": {
                    "primary_vibes": [
                        {"vibe": "romantic", "score": 0.9},
                        {"vibe": "elegant", "score": 0.8}
                    ],
                    "secondary_vibes": [{"vibe": "upscale", "score": 0.7}],
                    "energy_level": 0.2,
                    "formality_level": 0.9
                }
            },
            {
                "id": "rest_3",
                "name": "Taco Joint",
                "cuisine": "mexican",
                "price_range": 1,
                "location": {"city": "New York", "neighborhood": "East Village"},
                "vibe_profile": {
                    "primary_vibes": [
                        {"vibe": "casual", "score": 0.9},
                        {"vibe": "lively", "score": 0.8}
                    ],
                    "secondary_vibes": [{"vibe": "vibrant", "score": 0.7}],
                    "energy_level": 0.8,
                    "formality_level": 0.1
                }
            }
        ]
    
    def test_build_vibe_vector(self):
        """Test vibe vector construction."""
        vibe_profile = self.test_restaurants[0]["vibe_profile"]
        vector = self.mapper._build_vibe_vector(vibe_profile)
        
        self.assertIsInstance(vector, np.ndarray)
        self.assertGreater(len(vector), 0)
        
        # Check that energy and formality are included
        self.assertEqual(vector[-2], vibe_profile["energy_level"])
        self.assertEqual(vector[-1], vibe_profile["formality_level"])
    
    def test_calculate_cuisine_similarity(self):
        """Test cuisine similarity calculation."""
        # Same cuisine
        sim_same = self.mapper._calculate_cuisine_similarity("italian", "italian")
        self.assertEqual(sim_same, 1.0)
        
        # Related cuisines (both European)
        sim_related = self.mapper._calculate_cuisine_similarity("italian", "french")
        self.assertGreater(sim_related, 0.5)
        
        # Unrelated cuisines
        sim_unrelated = self.mapper._calculate_cuisine_similarity("italian", "thai")
        self.assertLess(sim_unrelated, 0.5)
    
    def test_calculate_price_similarity(self):
        """Test price similarity calculation."""
        # Same price
        sim_same = self.mapper._calculate_price_similarity(2, 2)
        self.assertEqual(sim_same, 1.0)
        
        # One level difference
        sim_close = self.mapper._calculate_price_similarity(2, 3)
        self.assertEqual(sim_close, 0.7)
        
        # Large difference
        sim_far = self.mapper._calculate_price_similarity(1, 4)
        self.assertEqual(sim_far, 0.0)
    
    def test_map_restaurant_relationships(self):
        """Test mapping relationships between restaurants."""
        relationships = self.mapper.map_restaurant_relationships(
            self.test_restaurants,
            max_relationships=2
        )
        
        # Check that relationships were created
        self.assertIn("rest_1", relationships)
        self.assertGreater(len(relationships["rest_1"]), 0)
        
        # Check relationship structure
        first_rel = relationships["rest_1"][0]
        self.assertIsInstance(first_rel, RestaurantRelationship)
        self.assertIn(first_rel.restaurant_b_id, ["rest_2", "rest_3"])
        
        # Italian and French restaurants should be more similar than Italian and Taco
        italian_rels = relationships["rest_1"]
        french_rel = next((r for r in italian_rels if r.restaurant_b_id == "rest_2"), None)
        taco_rel = next((r for r in italian_rels if r.restaurant_b_id == "rest_3"), None)
        
        if french_rel and taco_rel:
            self.assertGreater(french_rel.similarity_score, taco_rel.similarity_score)
    
    def test_find_vibe_clusters(self):
        """Test vibe clustering."""
        clusters = self.mapper.find_vibe_clusters(self.test_restaurants, min_cluster_size=1)
        
        # Should have at least some clusters
        self.assertGreater(len(clusters), 0)
        
        # Check that restaurants are in appropriate clusters
        for cluster_name, restaurant_ids in clusters.items():
            self.assertIsInstance(restaurant_ids, list)
            self.assertGreater(len(restaurant_ids), 0)


class TestIntegration(unittest.TestCase):
    """Integration tests for the taste graph system."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the Anthropic client
        with patch('taste_graph.core.vibe_extractor.anthropic.Anthropic'):
            self.extractor = VibeExtractor("test_key")
        
        self.engine = TasteEngine()
        self.mapper = RelationshipMapper()
    
    @patch('taste_graph.core.vibe_extractor.anthropic.Anthropic')
    def test_full_pipeline(self, mock_anthropic):
        """Test the full extraction and matching pipeline."""
        # Mock Claude response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='''
        {
            "primary_vibes": [
                {"vibe": "casual", "score": 0.8},
                {"vibe": "lively", "score": 0.7}
            ],
            "secondary_vibes": [
                {"vibe": "modern", "score": 0.5}
            ],
            "energy_level": 0.7,
            "formality_level": 0.2
        }
        ''')]
        
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client
        
        # Reinitialize extractor with mocked client
        self.extractor = VibeExtractor("test_key")
        
        # Test data
        restaurant_data = {
            "id": "test_restaurant",
            "name": "Test Cafe",
            "cuisine": "american",
            "price_range": 2,
            "description": "A casual neighborhood cafe",
            "reviews": ["Great atmosphere!", "Love the vibe here"]
        }
        
        user_data = {
            "user_id": "test_user",
            "preferred_vibes": {"casual": 0.9, "lively": 0.7},
            "cuisine_preferences": {"american": 0.8}
        }
        
        # Extract vibes
        vibe_profile = self.extractor.extract_vibes(restaurant_data)
        
        # Create user profile
        user_profile = self.engine.create_taste_profile(user_data)
        
        # Prepare restaurant with vibe profile
        restaurant_with_vibes = {
            **restaurant_data,
            "vibe_profile": {
                "primary_vibes": vibe_profile.primary_vibes,
                "secondary_vibes": vibe_profile.secondary_vibes,
                "energy_level": vibe_profile.energy_level,
                "formality_level": vibe_profile.formality_level
            }
        }
        
        # Calculate match
        match = self.engine.calculate_match(user_profile, restaurant_with_vibes)
        
        # Should have high match due to matching vibes and cuisine
        self.assertGreater(match.match_score, 0.7)
        self.assertGreater(match.vibe_alignment, 0.7)
        self.assertGreater(match.cuisine_match, 0.7)


if __name__ == '__main__':
    unittest.main()