"""
Taste Engine Module

Core preference matching and taste profile management for personalized
restaurant recommendations.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class UserTasteProfile:
    """Represents a user's dining preferences and taste profile."""
    user_id: str
    preferred_vibes: Dict[str, float]  # {"casual": 0.8, "romantic": 0.6, ...}
    avoided_vibes: Dict[str, float]  # {"loud": 0.9, "crowded": 0.7, ...}
    cuisine_preferences: Dict[str, float]  # {"italian": 0.9, "thai": 0.7, ...}
    price_sensitivity: float  # 0-1 (0=price insensitive, 1=very sensitive)
    adventure_score: float  # 0-1 (0=conservative, 1=adventurous)
    social_dining_style: str  # "solo", "couples", "groups", "family"
    contextual_preferences: Dict[str, Dict]  # Time/occasion specific prefs
    last_updated: datetime
    interaction_history: List[Dict]  # Recent interactions for learning


@dataclass
class TasteMatch:
    """Represents a match between user preferences and restaurant."""
    restaurant_id: str
    match_score: float  # 0-1 overall match
    vibe_alignment: float  # How well vibes match
    cuisine_match: float  # Cuisine preference alignment
    price_match: float  # Price range compatibility
    context_score: float  # Current context relevance
    explanation: Dict[str, str]  # Why this match was made


class TasteEngine:
    """Core engine for taste profile management and matching."""
    
    def __init__(self, decay_rate: float = 0.95):
        """
        Initialize the taste engine.
        
        Args:
            decay_rate: Rate at which old preferences decay (default 0.95)
        """
        self.decay_rate = decay_rate
        self.vibe_weights = self._initialize_vibe_weights()
        
    def _initialize_vibe_weights(self) -> Dict[str, float]:
        """Initialize importance weights for different vibe categories."""
        return {
            "atmosphere": 0.35,
            "energy": 0.25,
            "occasion": 0.25,
            "style": 0.15
        }
    
    def create_taste_profile(self, user_data: Dict) -> UserTasteProfile:
        """
        Create a new user taste profile from initial data.
        
        Args:
            user_data: Dictionary containing user preferences and history
            
        Returns:
            UserTasteProfile object
        """
        # Extract preferences from user data
        preferred_vibes = self._extract_preferred_vibes(user_data)
        avoided_vibes = self._extract_avoided_vibes(user_data)
        cuisine_prefs = self._extract_cuisine_preferences(user_data)
        
        # Calculate derived metrics
        adventure_score = self._calculate_adventure_score(user_data)
        price_sensitivity = self._calculate_price_sensitivity(user_data)
        
        return UserTasteProfile(
            user_id=user_data["user_id"],
            preferred_vibes=preferred_vibes,
            avoided_vibes=avoided_vibes,
            cuisine_preferences=cuisine_prefs,
            price_sensitivity=price_sensitivity,
            adventure_score=adventure_score,
            social_dining_style=user_data.get("social_style", "couples"),
            contextual_preferences=user_data.get("contextual_prefs", {}),
            last_updated=datetime.now(),
            interaction_history=[]
        )
    
    def update_taste_profile(self, profile: UserTasteProfile, 
                           interaction: Dict) -> UserTasteProfile:
        """
        Update user taste profile based on new interaction.
        
        Args:
            profile: Current user taste profile
            interaction: New interaction data (visit, rating, etc.)
            
        Returns:
            Updated UserTasteProfile
        """
        # Add interaction to history
        profile.interaction_history.append({
            **interaction,
            "timestamp": datetime.now()
        })
        
        # Keep only recent interactions (last 100)
        profile.interaction_history = profile.interaction_history[-100:]
        
        # Update preferences based on interaction type
        if interaction["type"] == "visit":
            self._update_from_visit(profile, interaction)
        elif interaction["type"] == "rating":
            self._update_from_rating(profile, interaction)
        elif interaction["type"] == "bookmark":
            self._update_from_bookmark(profile, interaction)
        
        # Apply temporal decay to older preferences
        self._apply_temporal_decay(profile)
        
        profile.last_updated = datetime.now()
        return profile
    
    def calculate_match(self, profile: UserTasteProfile, 
                       restaurant: Dict, context: Optional[Dict] = None) -> TasteMatch:
        """
        Calculate match score between user profile and restaurant.
        
        Args:
            profile: User taste profile
            restaurant: Restaurant data with vibe profile
            context: Optional context (time, weather, occasion, etc.)
            
        Returns:
            TasteMatch object with scoring details
        """
        # Extract restaurant vibes
        restaurant_vibes = self._normalize_restaurant_vibes(restaurant)
        
        # Calculate component scores
        vibe_alignment = self._calculate_vibe_alignment(
            profile.preferred_vibes, 
            profile.avoided_vibes,
            restaurant_vibes
        )
        
        cuisine_match = self._calculate_cuisine_match(
            profile.cuisine_preferences,
            restaurant.get("cuisine", "")
        )
        
        price_match = self._calculate_price_match(
            profile.price_sensitivity,
            restaurant.get("price_range", 2)
        )
        
        context_score = self._calculate_context_score(
            profile.contextual_preferences,
            restaurant,
            context or {}
        )
        
        # Calculate weighted overall score
        weights = {
            "vibe": 0.4,
            "cuisine": 0.3,
            "price": 0.15,
            "context": 0.15
        }
        
        match_score = (
            weights["vibe"] * vibe_alignment +
            weights["cuisine"] * cuisine_match +
            weights["price"] * price_match +
            weights["context"] * context_score
        )
        
        # Generate explanation
        explanation = self._generate_match_explanation(
            profile, restaurant, vibe_alignment, cuisine_match, price_match, context_score
        )
        
        return TasteMatch(
            restaurant_id=restaurant.get("id", restaurant.get("name")),
            match_score=match_score,
            vibe_alignment=vibe_alignment,
            cuisine_match=cuisine_match,
            price_match=price_match,
            context_score=context_score,
            explanation=explanation
        )
    
    def _extract_preferred_vibes(self, user_data: Dict) -> Dict[str, float]:
        """Extract preferred vibes from user data."""
        preferred = {}
        
        # From explicit preferences
        if "preferred_vibes" in user_data:
            preferred.update(user_data["preferred_vibes"])
        
        # From interaction history
        if "history" in user_data:
            for interaction in user_data["history"]:
                if interaction.get("rating", 0) >= 4:
                    for vibe in interaction.get("vibes", []):
                        preferred[vibe] = preferred.get(vibe, 0) + 0.1
        
        # Normalize scores to 0-1 range
        if preferred:
            max_score = max(preferred.values())
            preferred = {k: v/max_score for k, v in preferred.items()}
        
        return preferred
    
    def _extract_avoided_vibes(self, user_data: Dict) -> Dict[str, float]:
        """Extract avoided vibes from user data."""
        avoided = {}
        
        # From explicit preferences
        if "avoided_vibes" in user_data:
            avoided.update(user_data["avoided_vibes"])
        
        # From negative interactions
        if "history" in user_data:
            for interaction in user_data["history"]:
                if interaction.get("rating", 5) <= 2:
                    for vibe in interaction.get("vibes", []):
                        avoided[vibe] = avoided.get(vibe, 0) + 0.1
        
        # Normalize scores
        if avoided:
            max_score = max(avoided.values())
            avoided = {k: v/max_score for k, v in avoided.items()}
        
        return avoided
    
    def _extract_cuisine_preferences(self, user_data: Dict) -> Dict[str, float]:
        """Extract cuisine preferences from user data."""
        cuisines = {}
        
        # From explicit preferences
        if "cuisine_preferences" in user_data:
            cuisines.update(user_data["cuisine_preferences"])
        
        # From interaction history
        if "history" in user_data:
            for interaction in user_data["history"]:
                cuisine = interaction.get("cuisine", "").lower()
                if cuisine:
                    rating = interaction.get("rating", 3)
                    # Weighted by rating (1-5 scale)
                    weight = (rating - 3) / 2  # -1 to 1
                    cuisines[cuisine] = cuisines.get(cuisine, 0) + weight
        
        # Normalize to 0-1 range
        if cuisines:
            min_score = min(cuisines.values())
            max_score = max(cuisines.values())
            if max_score > min_score:
                cuisines = {
                    k: (v - min_score) / (max_score - min_score) 
                    for k, v in cuisines.items()
                }
        
        return cuisines
    
    def _calculate_adventure_score(self, user_data: Dict) -> float:
        """Calculate user's dining adventure score."""
        if "adventure_score" in user_data:
            return user_data["adventure_score"]
        
        # Calculate from cuisine diversity
        cuisines_tried = set()
        if "history" in user_data:
            for interaction in user_data["history"]:
                cuisine = interaction.get("cuisine", "")
                if cuisine:
                    cuisines_tried.add(cuisine.lower())
        
        # More diverse = more adventurous
        diversity_score = min(len(cuisines_tried) / 20, 1.0)
        
        return diversity_score
    
    def _calculate_price_sensitivity(self, user_data: Dict) -> float:
        """Calculate user's price sensitivity."""
        if "price_sensitivity" in user_data:
            return user_data["price_sensitivity"]
        
        # Calculate from history
        price_ratings = []
        if "history" in user_data:
            for interaction in user_data["history"]:
                price = interaction.get("price_range", 0)
                rating = interaction.get("rating", 3)
                if price > 0:
                    price_ratings.append((price, rating))
        
        if not price_ratings:
            return 0.5  # Default medium sensitivity
        
        # Check if higher prices correlate with lower ratings
        prices = [p[0] for p in price_ratings]
        ratings = [p[1] for p in price_ratings]
        
        # Simple correlation check
        avg_price = sum(prices) / len(prices)
        avg_rating = sum(ratings) / len(ratings)
        
        high_price_ratings = [r for p, r in price_ratings if p > avg_price]
        low_price_ratings = [r for p, r in price_ratings if p <= avg_price]
        
        if high_price_ratings and low_price_ratings:
            high_avg = sum(high_price_ratings) / len(high_price_ratings)
            low_avg = sum(low_price_ratings) / len(low_price_ratings)
            
            # If low price has higher ratings, user is price sensitive
            sensitivity = max(0, min(1, (low_avg - high_avg) / 2 + 0.5))
            return sensitivity
        
        return 0.5
    
    def _normalize_restaurant_vibes(self, restaurant: Dict) -> Dict[str, float]:
        """Normalize restaurant vibe data to standard format."""
        vibes = {}
        
        if "vibe_profile" in restaurant:
            profile = restaurant["vibe_profile"]
            
            # Extract primary vibes
            for vibe_data in profile.get("primary_vibes", []):
                vibe = vibe_data.get("vibe", "")
                score = vibe_data.get("score", 0.5)
                vibes[vibe] = score
            
            # Extract secondary vibes with lower weight
            for vibe_data in profile.get("secondary_vibes", []):
                vibe = vibe_data.get("vibe", "")
                score = vibe_data.get("score", 0.5) * 0.5  # Half weight
                vibes[vibe] = vibes.get(vibe, 0) + score
        
        return vibes
    
    def _calculate_vibe_alignment(self, preferred: Dict[str, float],
                                 avoided: Dict[str, float],
                                 restaurant_vibes: Dict[str, float]) -> float:
        """Calculate vibe alignment score."""
        if not restaurant_vibes:
            return 0.5  # Neutral if no vibe data
        
        alignment_score = 0.0
        total_weight = 0.0
        
        # Positive alignment with preferred vibes
        for vibe, pref_score in preferred.items():
            if vibe in restaurant_vibes:
                alignment = pref_score * restaurant_vibes[vibe]
                alignment_score += alignment
                total_weight += pref_score
        
        # Negative alignment with avoided vibes
        for vibe, avoid_score in avoided.items():
            if vibe in restaurant_vibes:
                penalty = avoid_score * restaurant_vibes[vibe]
                alignment_score -= penalty
                total_weight += avoid_score
        
        # Normalize to 0-1 range
        if total_weight > 0:
            normalized_score = (alignment_score / total_weight + 1) / 2
            return max(0, min(1, normalized_score))
        
        return 0.5
    
    def _calculate_cuisine_match(self, preferences: Dict[str, float],
                                cuisine: str) -> float:
        """Calculate cuisine preference match."""
        if not cuisine:
            return 0.5
        
        cuisine_lower = cuisine.lower()
        
        # Direct match
        if cuisine_lower in preferences:
            return preferences[cuisine_lower]
        
        # Check for similar cuisines
        similar_cuisines = self._get_similar_cuisines(cuisine_lower)
        for similar in similar_cuisines:
            if similar in preferences:
                return preferences[similar] * 0.8  # 80% match for similar
        
        # If cuisine not in preferences, use adventure score
        # Adventurous users get higher scores for unknown cuisines
        return 0.3 + (preferences.get("_adventure_score", 0.5) * 0.4)
    
    def _get_similar_cuisines(self, cuisine: str) -> List[str]:
        """Get cuisines similar to the given one."""
        cuisine_groups = {
            "asian": ["chinese", "japanese", "thai", "vietnamese", "korean"],
            "european": ["italian", "french", "spanish", "greek", "german"],
            "latin": ["mexican", "peruvian", "brazilian", "argentinian"],
            "middle_eastern": ["lebanese", "turkish", "persian", "israeli"]
        }
        
        similar = []
        for group, members in cuisine_groups.items():
            if cuisine in members:
                similar.extend([m for m in members if m != cuisine])
        
        return similar
    
    def _calculate_price_match(self, sensitivity: float, price_range: int) -> float:
        """Calculate price range match based on sensitivity."""
        # Price ranges: 1=$, 2=$$, 3=$$$, 4=$$$$
        # High sensitivity = prefer lower prices
        
        if sensitivity > 0.7:  # High sensitivity
            return max(0, 1 - (price_range - 1) * 0.3)
        elif sensitivity < 0.3:  # Low sensitivity
            return 0.8 + (price_range / 20)  # Slight preference for quality
        else:  # Medium sensitivity
            # Bell curve centered on $$
            return 1 - abs(price_range - 2) * 0.2
    
    def _calculate_context_score(self, contextual_prefs: Dict,
                                restaurant: Dict, context: Dict) -> float:
        """Calculate context-based match score."""
        scores = []
        
        # Time of day matching
        if "time" in context:
            time_score = self._match_time_context(contextual_prefs, restaurant, context["time"])
            scores.append(time_score)
        
        # Weather matching
        if "weather" in context:
            weather_score = self._match_weather_context(contextual_prefs, restaurant, context["weather"])
            scores.append(weather_score)
        
        # Occasion matching
        if "occasion" in context:
            occasion_score = self._match_occasion_context(contextual_prefs, restaurant, context["occasion"])
            scores.append(occasion_score)
        
        # Social context matching
        if "group_size" in context:
            social_score = self._match_social_context(restaurant, context["group_size"])
            scores.append(social_score)
        
        return sum(scores) / len(scores) if scores else 0.5
    
    def _match_time_context(self, prefs: Dict, restaurant: Dict, time: str) -> float:
        """Match restaurant to time of day context."""
        time_vibes = {
            "breakfast": ["casual", "quick-bite", "calm"],
            "lunch": ["quick-bite", "business", "casual"],
            "dinner": ["romantic", "upscale", "special-occasion"],
            "late_night": ["lively", "casual", "vibrant"]
        }
        
        relevant_vibes = time_vibes.get(time, [])
        restaurant_vibes = self._normalize_restaurant_vibes(restaurant)
        
        match_score = 0
        for vibe in relevant_vibes:
            if vibe in restaurant_vibes:
                match_score += restaurant_vibes[vibe]
        
        return min(match_score / len(relevant_vibes), 1.0) if relevant_vibes else 0.5
    
    def _match_weather_context(self, prefs: Dict, restaurant: Dict, weather: str) -> float:
        """Match restaurant to weather context."""
        # Simple weather matching
        if weather in ["rain", "snow", "cold"]:
            # Prefer indoor, cozy places
            indoor_vibes = ["intimate", "cozy", "warm", "rustic"]
        else:  # sunny, warm
            # Outdoor seating bonus
            indoor_vibes = ["airy", "outdoor", "fresh", "vibrant"]
        
        restaurant_vibes = self._normalize_restaurant_vibes(restaurant)
        matches = sum(restaurant_vibes.get(v, 0) for v in indoor_vibes)
        
        return min(matches / 2, 1.0)
    
    def _match_occasion_context(self, prefs: Dict, restaurant: Dict, occasion: str) -> float:
        """Match restaurant to occasion context."""
        occasion_vibes = {
            "date": ["romantic", "intimate", "upscale"],
            "business": ["professional", "quiet", "upscale"],
            "family": ["family-friendly", "casual", "spacious"],
            "celebration": ["lively", "festive", "special-occasion"],
            "casual": ["casual", "relaxed", "everyday"]
        }
        
        relevant_vibes = occasion_vibes.get(occasion, ["casual"])
        restaurant_vibes = self._normalize_restaurant_vibes(restaurant)
        
        match_score = sum(restaurant_vibes.get(v, 0) for v in relevant_vibes)
        return min(match_score / len(relevant_vibes), 1.0)
    
    def _match_social_context(self, restaurant: Dict, group_size: int) -> float:
        """Match restaurant to group size."""
        restaurant_vibes = self._normalize_restaurant_vibes(restaurant)
        
        if group_size == 1:  # Solo
            solo_vibes = ["quiet", "casual", "quick-bite"]
            score = sum(restaurant_vibes.get(v, 0) for v in solo_vibes)
        elif group_size == 2:  # Couple
            couple_vibes = ["romantic", "intimate", "quiet"]
            score = sum(restaurant_vibes.get(v, 0) for v in couple_vibes)
        elif group_size <= 4:  # Small group
            group_vibes = ["casual", "lively", "social"]
            score = sum(restaurant_vibes.get(v, 0) for v in group_vibes)
        else:  # Large group
            large_vibes = ["spacious", "lively", "family-friendly"]
            score = sum(restaurant_vibes.get(v, 0) for v in large_vibes)
        
        return min(score / 2, 1.0)
    
    def _update_from_visit(self, profile: UserTasteProfile, interaction: Dict):
        """Update profile from restaurant visit."""
        restaurant_vibes = interaction.get("vibes", [])
        
        # Implicit positive signal - increase preference for these vibes
        for vibe in restaurant_vibes:
            current = profile.preferred_vibes.get(vibe, 0)
            profile.preferred_vibes[vibe] = min(current + 0.05, 1.0)
    
    def _update_from_rating(self, profile: UserTasteProfile, interaction: Dict):
        """Update profile from restaurant rating."""
        rating = interaction.get("rating", 3)
        restaurant_vibes = interaction.get("vibes", [])
        cuisine = interaction.get("cuisine", "").lower()
        
        # Update vibe preferences based on rating
        for vibe in restaurant_vibes:
            if rating >= 4:  # Positive
                current = profile.preferred_vibes.get(vibe, 0)
                profile.preferred_vibes[vibe] = min(current + 0.1, 1.0)
            elif rating <= 2:  # Negative
                current = profile.avoided_vibes.get(vibe, 0)
                profile.avoided_vibes[vibe] = min(current + 0.1, 1.0)
        
        # Update cuisine preferences
        if cuisine:
            current = profile.cuisine_preferences.get(cuisine, 0.5)
            # Weighted update based on rating
            weight = (rating - 3) / 10  # -0.2 to +0.2
            profile.cuisine_preferences[cuisine] = max(0, min(1, current + weight))
    
    def _update_from_bookmark(self, profile: UserTasteProfile, interaction: Dict):
        """Update profile from restaurant bookmark."""
        # Strong positive signal
        restaurant_vibes = interaction.get("vibes", [])
        
        for vibe in restaurant_vibes:
            current = profile.preferred_vibes.get(vibe, 0)
            profile.preferred_vibes[vibe] = min(current + 0.15, 1.0)
    
    def _apply_temporal_decay(self, profile: UserTasteProfile):
        """Apply temporal decay to preferences."""
        # Decay preferences that haven't been reinforced recently
        decay_factor = self.decay_rate
        
        # Check recent interactions for reinforced vibes
        recent_vibes = set()
        cutoff_date = datetime.now() - timedelta(days=30)
        
        for interaction in profile.interaction_history:
            if interaction.get("timestamp", datetime.min) > cutoff_date:
                recent_vibes.update(interaction.get("vibes", []))
        
        # Apply decay to non-reinforced preferences
        for vibe in list(profile.preferred_vibes.keys()):
            if vibe not in recent_vibes:
                profile.preferred_vibes[vibe] *= decay_factor
                if profile.preferred_vibes[vibe] < 0.1:
                    del profile.preferred_vibes[vibe]
        
        for vibe in list(profile.avoided_vibes.keys()):
            if vibe not in recent_vibes:
                profile.avoided_vibes[vibe] *= decay_factor
                if profile.avoided_vibes[vibe] < 0.1:
                    del profile.avoided_vibes[vibe]
    
    def _generate_match_explanation(self, profile: UserTasteProfile,
                                   restaurant: Dict, vibe_score: float,
                                   cuisine_score: float, price_score: float,
                                   context_score: float) -> Dict[str, str]:
        """Generate human-readable explanation for match."""
        explanation = {}
        
        # Vibe explanation
        if vibe_score > 0.7:
            matching_vibes = []
            restaurant_vibes = self._normalize_restaurant_vibes(restaurant)
            for vibe in profile.preferred_vibes:
                if vibe in restaurant_vibes:
                    matching_vibes.append(vibe)
            if matching_vibes:
                explanation["vibe"] = f"Perfect match for your love of {', '.join(matching_vibes[:2])} atmospheres"
        elif vibe_score < 0.3:
            explanation["vibe"] = "Different from your usual preferences - might be an adventure!"
        
        # Cuisine explanation
        cuisine = restaurant.get("cuisine", "").lower()
        if cuisine in profile.cuisine_preferences:
            if cuisine_score > 0.8:
                explanation["cuisine"] = f"One of your favorite cuisines: {cuisine.title()}"
            elif cuisine_score > 0.5:
                explanation["cuisine"] = f"You've enjoyed {cuisine.title()} before"
        
        # Price explanation
        if price_score < 0.5 and profile.price_sensitivity > 0.7:
            explanation["price"] = "Higher than your usual price range"
        elif price_score > 0.8 and profile.price_sensitivity > 0.7:
            explanation["price"] = "Great value in your price range"
        
        # Context explanation
        if context_score > 0.7:
            explanation["context"] = "Perfect for the occasion"
        
        return explanation