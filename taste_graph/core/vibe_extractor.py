"""
Vibe Extractor Module

Claude-powered vibe analysis for restaurants based on reviews, descriptions,
and other data sources. Extracts and quantifies restaurant vibes with
confidence scoring.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass
class VibeProfile:
    """Represents a restaurant's vibe profile with confidence scores."""
    primary_vibes: List[Dict[str, float]]  # [{"vibe": "casual", "score": 0.8}, ...]
    secondary_vibes: List[Dict[str, float]]
    energy_level: float  # 0-1 scale (0=calm, 1=energetic)
    formality_level: float  # 0-1 scale (0=casual, 1=formal)
    vibe_confidence: float  # Overall confidence in vibe extraction
    extracted_at: datetime
    source_types: List[str]  # ["reviews", "description", "photos", etc.]


class VibeExtractor:
    """Extracts and analyzes restaurant vibes using Claude API."""
    
    def __init__(self, api_key: str, model: str = "claude-3-opus-20240229"):
        """
        Initialize the vibe extractor.
        
        Args:
            api_key: Anthropic API key
            model: Claude model to use for extraction
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.vibe_taxonomy = self._load_vibe_taxonomy()
        
    def _load_vibe_taxonomy(self) -> Dict[str, List[str]]:
        """Load standardized vibe taxonomy from configuration."""
        # This would normally load from config/vibes.yaml
        # For now, using a simplified taxonomy
        return {
            "atmosphere": ["casual", "upscale", "intimate", "lively", "romantic", 
                          "trendy", "classic", "modern", "rustic", "elegant"],
            "energy": ["calm", "vibrant", "bustling", "relaxed", "energetic"],
            "occasion": ["date-night", "business", "family-friendly", "celebration",
                        "quick-bite", "special-occasion", "everyday"],
            "style": ["traditional", "innovative", "fusion", "authentic", "contemporary"]
        }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def extract_vibes(self, restaurant_data: Dict) -> VibeProfile:
        """
        Extract vibes from restaurant data using Claude.
        
        Args:
            restaurant_data: Dictionary containing restaurant information
                - name: Restaurant name
                - description: Restaurant description
                - reviews: List of review texts
                - cuisine: Cuisine type
                - price_range: Price tier
                - additional_data: Any other relevant data
                
        Returns:
            VibeProfile object with extracted vibes and confidence scores
        """
        prompt = self._build_extraction_prompt(restaurant_data)
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.2,  # Lower temperature for consistency
                system=self._get_system_prompt(),
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse Claude's response
            extracted_data = self._parse_response(response.content[0].text)
            
            # Validate and normalize vibes
            validated_vibes = self._validate_vibes(extracted_data)
            
            # Calculate confidence scores
            confidence = self._calculate_confidence(restaurant_data, validated_vibes)
            
            return VibeProfile(
                primary_vibes=validated_vibes["primary"],
                secondary_vibes=validated_vibes["secondary"],
                energy_level=validated_vibes["energy_level"],
                formality_level=validated_vibes["formality_level"],
                vibe_confidence=confidence,
                extracted_at=datetime.now(),
                source_types=self._get_source_types(restaurant_data)
            )
            
        except Exception as e:
            logger.error(f"Error extracting vibes: {str(e)}")
            raise
    
    def _build_extraction_prompt(self, restaurant_data: Dict) -> str:
        """Build the prompt for Claude to extract vibes."""
        reviews_text = "\n".join(restaurant_data.get("reviews", [])[:5])  # Limit to 5 reviews
        
        return f"""
Analyze the following restaurant and extract its vibe profile:

Restaurant: {restaurant_data.get('name', 'Unknown')}
Cuisine: {restaurant_data.get('cuisine', 'Unknown')}
Price Range: {restaurant_data.get('price_range', 'Unknown')}
Description: {restaurant_data.get('description', 'No description available')}

Recent Reviews:
{reviews_text if reviews_text else 'No reviews available'}

Please analyze and provide:
1. Primary vibes (2-3 most prominent vibes with confidence scores 0-1)
2. Secondary vibes (2-3 supporting vibes with confidence scores 0-1)
3. Energy level (0-1 scale where 0=calm, 1=energetic)
4. Formality level (0-1 scale where 0=casual, 1=formal)

Use these vibe categories: {json.dumps(self.vibe_taxonomy)}

Respond in JSON format only.
"""
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for Claude."""
        return """You are a restaurant vibe analyst. Your task is to extract and quantify 
the atmosphere, energy, and overall vibe of restaurants based on available data. 
Be objective, precise, and base your analysis only on the provided information. 
Always respond with valid JSON containing the requested vibe analysis."""
    
    def _parse_response(self, response_text: str) -> Dict:
        """Parse Claude's JSON response."""
        try:
            # Extract JSON from response (Claude might add explanation)
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response: {e}")
            # Return a default structure
            return {
                "primary_vibes": [{"vibe": "casual", "score": 0.5}],
                "secondary_vibes": [],
                "energy_level": 0.5,
                "formality_level": 0.5
            }
    
    def _validate_vibes(self, extracted_data: Dict) -> Dict:
        """Validate and normalize extracted vibes against taxonomy."""
        validated = {
            "primary": [],
            "secondary": [],
            "energy_level": extracted_data.get("energy_level", 0.5),
            "formality_level": extracted_data.get("formality_level", 0.5)
        }
        
        # Validate primary vibes
        for vibe_data in extracted_data.get("primary_vibes", []):
            vibe = vibe_data.get("vibe", "").lower()
            score = min(max(vibe_data.get("score", 0.5), 0), 1)  # Clamp to 0-1
            
            # Check if vibe exists in taxonomy
            if self._is_valid_vibe(vibe):
                validated["primary"].append({"vibe": vibe, "score": score})
        
        # Validate secondary vibes
        for vibe_data in extracted_data.get("secondary_vibes", []):
            vibe = vibe_data.get("vibe", "").lower()
            score = min(max(vibe_data.get("score", 0.5), 0), 1)
            
            if self._is_valid_vibe(vibe):
                validated["secondary"].append({"vibe": vibe, "score": score})
        
        # Ensure we have at least one primary vibe
        if not validated["primary"]:
            validated["primary"] = [{"vibe": "casual", "score": 0.5}]
        
        return validated
    
    def _is_valid_vibe(self, vibe: str) -> bool:
        """Check if a vibe exists in our taxonomy."""
        for category_vibes in self.vibe_taxonomy.values():
            if vibe in category_vibes:
                return True
        return False
    
    def _calculate_confidence(self, restaurant_data: Dict, validated_vibes: Dict) -> float:
        """Calculate overall confidence in vibe extraction."""
        confidence_factors = []
        
        # Factor 1: Data completeness
        has_description = bool(restaurant_data.get("description"))
        has_reviews = bool(restaurant_data.get("reviews"))
        data_completeness = (has_description + has_reviews) / 2
        confidence_factors.append(data_completeness)
        
        # Factor 2: Review count (more reviews = higher confidence)
        review_count = len(restaurant_data.get("reviews", []))
        review_confidence = min(review_count / 10, 1.0)  # Max confidence at 10+ reviews
        confidence_factors.append(review_confidence)
        
        # Factor 3: Vibe score consistency
        all_scores = [v["score"] for v in validated_vibes["primary"]] + \
                    [v["score"] for v in validated_vibes["secondary"]]
        if all_scores:
            avg_score = sum(all_scores) / len(all_scores)
            # Higher scores indicate stronger vibe signals
            confidence_factors.append(avg_score)
        
        # Calculate overall confidence
        return sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.5
    
    def _get_source_types(self, restaurant_data: Dict) -> List[str]:
        """Determine which data sources were used for extraction."""
        sources = []
        if restaurant_data.get("description"):
            sources.append("description")
        if restaurant_data.get("reviews"):
            sources.append("reviews")
        if restaurant_data.get("cuisine"):
            sources.append("cuisine")
        if restaurant_data.get("price_range"):
            sources.append("price_range")
        return sources
    
    def extract_batch(self, restaurants: List[Dict], batch_size: int = 10) -> Dict[str, VibeProfile]:
        """
        Extract vibes for multiple restaurants in batches.
        
        Args:
            restaurants: List of restaurant data dictionaries
            batch_size: Number of restaurants to process in parallel
            
        Returns:
            Dictionary mapping restaurant IDs to VibeProfiles
        """
        results = {}
        
        for i in range(0, len(restaurants), batch_size):
            batch = restaurants[i:i + batch_size]
            
            for restaurant in batch:
                restaurant_id = restaurant.get("id", restaurant.get("name", "unknown"))
                try:
                    vibe_profile = self.extract_vibes(restaurant)
                    results[restaurant_id] = vibe_profile
                    logger.info(f"Extracted vibes for {restaurant_id}")
                except Exception as e:
                    logger.error(f"Failed to extract vibes for {restaurant_id}: {e}")
                    
        return results