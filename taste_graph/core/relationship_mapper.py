"""
Relationship Mapper Module

Maps relationships between restaurants based on vibe similarity,
cuisine connections, and other attributes for discovery and recommendations.
"""

import numpy as np
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import logging
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class RestaurantRelationship:
    """Represents a relationship between two restaurants."""
    restaurant_a_id: str
    restaurant_b_id: str
    similarity_score: float  # Overall similarity 0-1
    vibe_similarity: float  # Vibe profile similarity
    cuisine_similarity: float  # Cuisine type similarity
    price_similarity: float  # Price range similarity
    location_proximity: float  # Geographic closeness
    relationship_type: str  # "similar", "complementary", "alternative"
    confidence: float  # Confidence in relationship
    created_at: datetime


class RelationshipMapper:
    """Maps and analyzes relationships between restaurants."""
    
    def __init__(self):
        """Initialize the relationship mapper."""
        self.vibe_dimensions = self._initialize_vibe_dimensions()
        self.cuisine_relationships = self._initialize_cuisine_relationships()
        self.relationship_cache = {}
        
    def _initialize_vibe_dimensions(self) -> Dict[str, List[str]]:
        """Initialize vibe dimension mappings."""
        return {
            "energy": ["calm", "relaxed", "moderate", "lively", "energetic"],
            "formality": ["casual", "smart-casual", "business", "formal", "black-tie"],
            "ambiance": ["intimate", "cozy", "spacious", "bustling", "vibrant"],
            "style": ["traditional", "classic", "contemporary", "trendy", "avant-garde"],
            "social": ["solo-friendly", "date-night", "groups", "family", "party"]
        }
    
    def _initialize_cuisine_relationships(self) -> Dict[str, Set[str]]:
        """Initialize cuisine relationship mappings."""
        return {
            # Regional relationships
            "italian": {"mediterranean", "french", "spanish"},
            "japanese": {"sushi", "ramen", "korean", "asian-fusion"},
            "chinese": {"taiwanese", "cantonese", "szechuan", "asian"},
            "mexican": {"tex-mex", "latin", "spanish", "southwestern"},
            "thai": {"vietnamese", "malaysian", "southeast-asian"},
            "french": {"italian", "spanish", "european", "bistro"},
            "indian": {"pakistani", "nepalese", "sri-lankan", "south-asian"},
            "greek": {"mediterranean", "middle-eastern", "turkish"},
            # Style relationships
            "steakhouse": {"american", "bbq", "grill"},
            "seafood": {"sushi", "mediterranean", "coastal"},
            "vegetarian": {"vegan", "healthy", "organic"},
            "fusion": {"contemporary", "innovative", "eclectic"}
        }
    
    def map_restaurant_relationships(self, restaurants: List[Dict], 
                                   max_relationships: int = 10) -> Dict[str, List[RestaurantRelationship]]:
        """
        Map relationships between all restaurants.
        
        Args:
            restaurants: List of restaurant dictionaries with vibe profiles
            max_relationships: Maximum relationships to store per restaurant
            
        Returns:
            Dictionary mapping restaurant IDs to their relationships
        """
        relationships = defaultdict(list)
        restaurant_dict = {r["id"]: r for r in restaurants}
        
        # Build vibe vectors for all restaurants
        vibe_vectors = {}
        for restaurant in restaurants:
            if "vibe_profile" in restaurant:
                vibe_vectors[restaurant["id"]] = self._build_vibe_vector(restaurant["vibe_profile"])
        
        # Calculate pairwise relationships
        restaurant_ids = list(vibe_vectors.keys())
        
        for i, rest_a_id in enumerate(restaurant_ids):
            similarities = []
            
            for j, rest_b_id in enumerate(restaurant_ids):
                if i != j:
                    relationship = self._calculate_relationship(
                        restaurant_dict[rest_a_id],
                        restaurant_dict[rest_b_id],
                        vibe_vectors.get(rest_a_id),
                        vibe_vectors.get(rest_b_id)
                    )
                    
                    if relationship.similarity_score > 0.3:  # Minimum threshold
                        similarities.append(relationship)
            
            # Keep top N relationships
            similarities.sort(key=lambda x: x.similarity_score, reverse=True)
            relationships[rest_a_id] = similarities[:max_relationships]
        
        self.relationship_cache = dict(relationships)
        return self.relationship_cache
    
    def find_similar_restaurants(self, restaurant_id: str, 
                                count: int = 5,
                                min_similarity: float = 0.5) -> List[Tuple[str, float]]:
        """
        Find restaurants most similar to the given one.
        
        Args:
            restaurant_id: ID of the restaurant to find similar ones for
            count: Number of similar restaurants to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of tuples (restaurant_id, similarity_score)
        """
        if restaurant_id not in self.relationship_cache:
            return []
        
        relationships = self.relationship_cache[restaurant_id]
        similar = [
            (r.restaurant_b_id, r.similarity_score)
            for r in relationships
            if r.similarity_score >= min_similarity and r.relationship_type == "similar"
        ]
        
        return similar[:count]
    
    def find_complementary_restaurants(self, restaurant_id: str,
                                      count: int = 5) -> List[Tuple[str, float]]:
        """
        Find restaurants that complement the given one (different but compatible).
        
        Args:
            restaurant_id: ID of the restaurant
            count: Number of complementary restaurants to return
            
        Returns:
            List of tuples (restaurant_id, compatibility_score)
        """
        if restaurant_id not in self.relationship_cache:
            return []
        
        relationships = self.relationship_cache[restaurant_id]
        complementary = [
            (r.restaurant_b_id, r.similarity_score)
            for r in relationships
            if r.relationship_type == "complementary"
        ]
        
        return complementary[:count]
    
    def _build_vibe_vector(self, vibe_profile: Dict) -> np.ndarray:
        """Build a numerical vector representation of vibe profile."""
        # Create a comprehensive vibe vocabulary
        all_vibes = set()
        for dimension_vibes in self.vibe_dimensions.values():
            all_vibes.update(dimension_vibes)
        
        # Add any additional vibes from the profile
        for vibe_data in vibe_profile.get("primary_vibes", []):
            all_vibes.add(vibe_data.get("vibe", ""))
        for vibe_data in vibe_profile.get("secondary_vibes", []):
            all_vibes.add(vibe_data.get("vibe", ""))
        
        # Create vector
        vibe_list = sorted(list(all_vibes))
        vector = np.zeros(len(vibe_list))
        
        # Fill vector with vibe scores
        vibe_to_index = {vibe: i for i, vibe in enumerate(vibe_list)}
        
        for vibe_data in vibe_profile.get("primary_vibes", []):
            vibe = vibe_data.get("vibe", "")
            score = vibe_data.get("score", 0)
            if vibe in vibe_to_index:
                vector[vibe_to_index[vibe]] = score
        
        for vibe_data in vibe_profile.get("secondary_vibes", []):
            vibe = vibe_data.get("vibe", "")
            score = vibe_data.get("score", 0) * 0.5  # Secondary vibes have less weight
            if vibe in vibe_to_index:
                vector[vibe_to_index[vibe]] += score
        
        # Add energy and formality levels as additional dimensions
        vector = np.append(vector, [
            vibe_profile.get("energy_level", 0.5),
            vibe_profile.get("formality_level", 0.5)
        ])
        
        return vector
    
    def _calculate_relationship(self, restaurant_a: Dict, restaurant_b: Dict,
                               vibe_vector_a: Optional[np.ndarray],
                               vibe_vector_b: Optional[np.ndarray]) -> RestaurantRelationship:
        """Calculate relationship between two restaurants."""
        # Calculate component similarities
        vibe_sim = self._calculate_vibe_similarity(vibe_vector_a, vibe_vector_b)
        cuisine_sim = self._calculate_cuisine_similarity(
            restaurant_a.get("cuisine", ""),
            restaurant_b.get("cuisine", "")
        )
        price_sim = self._calculate_price_similarity(
            restaurant_a.get("price_range", 2),
            restaurant_b.get("price_range", 2)
        )
        location_prox = self._calculate_location_proximity(
            restaurant_a.get("location", {}),
            restaurant_b.get("location", {})
        )
        
        # Calculate weighted overall similarity
        weights = {
            "vibe": 0.4,
            "cuisine": 0.25,
            "price": 0.15,
            "location": 0.2
        }
        
        overall_similarity = (
            weights["vibe"] * vibe_sim +
            weights["cuisine"] * cuisine_sim +
            weights["price"] * price_sim +
            weights["location"] * location_prox
        )
        
        # Determine relationship type
        relationship_type = self._determine_relationship_type(
            vibe_sim, cuisine_sim, price_sim, overall_similarity
        )
        
        # Calculate confidence based on data completeness
        confidence = self._calculate_confidence(
            restaurant_a, restaurant_b, vibe_vector_a, vibe_vector_b
        )
        
        return RestaurantRelationship(
            restaurant_a_id=restaurant_a["id"],
            restaurant_b_id=restaurant_b["id"],
            similarity_score=overall_similarity,
            vibe_similarity=vibe_sim,
            cuisine_similarity=cuisine_sim,
            price_similarity=price_sim,
            location_proximity=location_prox,
            relationship_type=relationship_type,
            confidence=confidence,
            created_at=datetime.now()
        )
    
    def _calculate_vibe_similarity(self, vector_a: Optional[np.ndarray],
                                  vector_b: Optional[np.ndarray]) -> float:
        """Calculate vibe similarity using cosine similarity."""
        if vector_a is None or vector_b is None:
            return 0.0
        
        # Reshape for sklearn
        vector_a = vector_a.reshape(1, -1)
        vector_b = vector_b.reshape(1, -1)
        
        # Calculate cosine similarity
        similarity = cosine_similarity(vector_a, vector_b)[0][0]
        
        # Ensure non-negative (cosine can be negative)
        return max(0, similarity)
    
    def _calculate_cuisine_similarity(self, cuisine_a: str, cuisine_b: str) -> float:
        """Calculate cuisine similarity based on relationships."""
        if not cuisine_a or not cuisine_b:
            return 0.0
        
        cuisine_a = cuisine_a.lower()
        cuisine_b = cuisine_b.lower()
        
        # Exact match
        if cuisine_a == cuisine_b:
            return 1.0
        
        # Check direct relationships
        if cuisine_a in self.cuisine_relationships:
            if cuisine_b in self.cuisine_relationships[cuisine_a]:
                return 0.8
        
        if cuisine_b in self.cuisine_relationships:
            if cuisine_a in self.cuisine_relationships[cuisine_b]:
                return 0.8
        
        # Check secondary relationships (cuisines that share a common related cuisine)
        related_a = self.cuisine_relationships.get(cuisine_a, set())
        related_b = self.cuisine_relationships.get(cuisine_b, set())
        
        common_related = related_a.intersection(related_b)
        if common_related:
            return 0.6
        
        # Check if they're in the same broad category
        categories = {
            "asian": {"chinese", "japanese", "thai", "vietnamese", "korean", "indian"},
            "european": {"italian", "french", "spanish", "greek", "german"},
            "american": {"american", "bbq", "southern", "tex-mex", "burger"},
            "latin": {"mexican", "peruvian", "brazilian", "argentinian", "cuban"}
        }
        
        for category, cuisines in categories.items():
            if cuisine_a in cuisines and cuisine_b in cuisines:
                return 0.4
        
        return 0.0
    
    def _calculate_price_similarity(self, price_a: int, price_b: int) -> float:
        """Calculate price range similarity."""
        # Price ranges: 1=$, 2=$$, 3=$$$, 4=$$$$
        price_diff = abs(price_a - price_b)
        
        if price_diff == 0:
            return 1.0
        elif price_diff == 1:
            return 0.7
        elif price_diff == 2:
            return 0.3
        else:
            return 0.0
    
    def _calculate_location_proximity(self, location_a: Dict, location_b: Dict) -> float:
        """Calculate location proximity score."""
        # Simple implementation - could be enhanced with actual distance calculation
        if not location_a or not location_b:
            return 0.0
        
        # Check if in same neighborhood/area
        if location_a.get("neighborhood") == location_b.get("neighborhood"):
            return 1.0
        
        # Check if in same city/region
        if location_a.get("city") == location_b.get("city"):
            return 0.5
        
        return 0.0
    
    def _determine_relationship_type(self, vibe_sim: float, cuisine_sim: float,
                                    price_sim: float, overall_sim: float) -> str:
        """Determine the type of relationship between restaurants."""
        # Similar: High overall similarity
        if overall_sim > 0.7:
            return "similar"
        
        # Complementary: Different vibes/cuisine but same price/location
        if vibe_sim < 0.5 and cuisine_sim < 0.5 but price_sim > 0.7:
            return "complementary"
        
        # Alternative: Moderate similarity, good substitute
        if 0.4 < overall_sim < 0.7:
            return "alternative"
        
        return "related"
    
    def _calculate_confidence(self, restaurant_a: Dict, restaurant_b: Dict,
                            vector_a: Optional[np.ndarray],
                            vector_b: Optional[np.ndarray]) -> float:
        """Calculate confidence in the relationship based on data quality."""
        confidence_factors = []
        
        # Check vibe data completeness
        if vector_a is not None and vector_b is not None:
            confidence_factors.append(1.0)
        else:
            confidence_factors.append(0.3)
        
        # Check cuisine data
        if restaurant_a.get("cuisine") and restaurant_b.get("cuisine"):
            confidence_factors.append(1.0)
        else:
            confidence_factors.append(0.5)
        
        # Check location data
        if restaurant_a.get("location") and restaurant_b.get("location"):
            confidence_factors.append(1.0)
        else:
            confidence_factors.append(0.5)
        
        # Check review/rating data
        if restaurant_a.get("rating") and restaurant_b.get("rating"):
            confidence_factors.append(1.0)
        else:
            confidence_factors.append(0.7)
        
        return sum(confidence_factors) / len(confidence_factors)
    
    def get_restaurant_network(self, restaurant_id: str, depth: int = 2) -> Dict[str, Set[str]]:
        """
        Get the network of related restaurants up to a certain depth.
        
        Args:
            restaurant_id: Starting restaurant ID
            depth: How many relationship levels to traverse
            
        Returns:
            Dictionary mapping restaurant IDs to sets of related restaurant IDs
        """
        network = defaultdict(set)
        visited = set()
        to_visit = [(restaurant_id, 0)]
        
        while to_visit:
            current_id, current_depth = to_visit.pop(0)
            
            if current_id in visited or current_depth >= depth:
                continue
            
            visited.add(current_id)
            
            # Get relationships for current restaurant
            if current_id in self.relationship_cache:
                for relationship in self.relationship_cache[current_id]:
                    related_id = relationship.restaurant_b_id
                    network[current_id].add(related_id)
                    
                    if current_depth + 1 < depth:
                        to_visit.append((related_id, current_depth + 1))
        
        return dict(network)
    
    def find_vibe_clusters(self, restaurants: List[Dict], 
                          min_cluster_size: int = 3) -> Dict[str, List[str]]:
        """
        Find clusters of restaurants with similar vibes.
        
        Args:
            restaurants: List of restaurants with vibe profiles
            min_cluster_size: Minimum size for a valid cluster
            
        Returns:
            Dictionary mapping cluster names to restaurant IDs
        """
        # Build vibe vectors
        vibe_vectors = []
        restaurant_ids = []
        
        for restaurant in restaurants:
            if "vibe_profile" in restaurant:
                vector = self._build_vibe_vector(restaurant["vibe_profile"])
                vibe_vectors.append(vector)
                restaurant_ids.append(restaurant["id"])
        
        if not vibe_vectors:
            return {}
        
        # Simple clustering based on primary vibes
        clusters = defaultdict(list)
        
        for i, restaurant in enumerate(restaurants):
            if "vibe_profile" in restaurant:
                primary_vibes = restaurant["vibe_profile"].get("primary_vibes", [])
                if primary_vibes:
                    # Use the highest scoring primary vibe as cluster key
                    primary_vibe = max(primary_vibes, key=lambda x: x.get("score", 0))
                    cluster_name = primary_vibe.get("vibe", "unknown")
                    clusters[cluster_name].append(restaurant["id"])
        
        # Filter out small clusters
        valid_clusters = {
            name: ids for name, ids in clusters.items()
            if len(ids) >= min_cluster_size
        }
        
        return valid_clusters