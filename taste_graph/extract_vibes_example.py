"""
Example script demonstrating vibe extraction pipeline

This script shows how to:
1. Load restaurant data
2. Extract vibes using Claude API
3. Save vibe profiles to PostgreSQL
4. Map restaurant relationships
5. Generate basic insights
"""

import os
import sys
import logging
import yaml
from datetime import datetime
from typing import Dict, List

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from taste_graph.core.vibe_extractor import VibeExtractor
from taste_graph.core.taste_engine import TasteEngine
from taste_graph.core.relationship_mapper import RelationshipMapper
from taste_graph.data_pipeline.database import DatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config/taste_graph_config.yaml") -> Dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Replace environment variables
    def replace_env_vars(obj):
        if isinstance(obj, str) and obj.startswith('${') and obj.endswith('}'):
            env_var = obj[2:-1]
            if ':' in env_var:
                var_name, default = env_var.split(':', 1)
                return os.getenv(var_name, default)
            return os.getenv(env_var, '')
        elif isinstance(obj, dict):
            return {k: replace_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_env_vars(item) for item in obj]
        return obj
    
    return replace_env_vars(config)


def extract_vibes_for_restaurants(config: Dict, limit: int = 10):
    """
    Extract vibes for restaurants that need processing.
    
    Args:
        config: Configuration dictionary
        limit: Number of restaurants to process
    """
    # Initialize components
    db = DatabaseManager(config['database'])
    vibe_extractor = VibeExtractor(
        api_key=config['vibe_extraction']['api_key'],
        model=config['vibe_extraction']['model']
    )
    
    try:
        # Get restaurants needing vibe extraction
        logger.info(f"Fetching up to {limit} restaurants for vibe extraction...")
        restaurants = db.get_restaurants_for_vibe_extraction(limit=limit)
        
        if not restaurants:
            logger.info("No restaurants found needing vibe extraction")
            return
        
        logger.info(f"Found {len(restaurants)} restaurants to process")
        
        # Process each restaurant
        for restaurant in restaurants:
            logger.info(f"Processing restaurant: {restaurant['name']} (ID: {restaurant['id']})")
            
            # Prepare data for extraction
            restaurant_data = {
                "id": restaurant['id'],
                "name": restaurant['name'],
                "cuisine": restaurant.get('cuisine', ''),
                "price_range": restaurant.get('price_range', 2),
                "description": restaurant.get('description', ''),
                "reviews": []  # Would normally load from reviews table
            }
            
            # For demo purposes, create synthetic review data
            # In production, this would come from actual reviews
            if restaurant.get('rating', 0) > 4:
                restaurant_data["reviews"] = [
                    "Amazing atmosphere and great food! The vibe is upscale but welcoming.",
                    "Perfect for date night. Intimate setting with excellent service.",
                    "Loved the modern decor and energetic atmosphere. Will definitely return!"
                ]
            else:
                restaurant_data["reviews"] = [
                    "Decent food but nothing special. Very casual atmosphere.",
                    "Good for a quick bite. Simple and straightforward.",
                    "Average experience. The place feels a bit dated."
                ]
            
            try:
                # Extract vibes
                vibe_profile = vibe_extractor.extract_vibes(restaurant_data)
                
                # Convert to dictionary for database storage
                profile_dict = {
                    "primary_vibes": vibe_profile.primary_vibes,
                    "secondary_vibes": vibe_profile.secondary_vibes,
                    "energy_level": vibe_profile.energy_level,
                    "formality_level": vibe_profile.formality_level,
                    "vibe_confidence": vibe_profile.vibe_confidence,
                    "extracted_at": vibe_profile.extracted_at,
                    "source_types": vibe_profile.source_types
                }
                
                # Save to database
                success = db.save_vibe_profile(restaurant['id'], profile_dict)
                
                if success:
                    logger.info(f"Successfully saved vibe profile for {restaurant['name']}")
                    logger.info(f"  Primary vibes: {[v['vibe'] for v in vibe_profile.primary_vibes]}")
                    logger.info(f"  Energy level: {vibe_profile.energy_level:.2f}")
                    logger.info(f"  Formality level: {vibe_profile.formality_level:.2f}")
                    logger.info(f"  Confidence: {vibe_profile.vibe_confidence:.2f}")
                else:
                    logger.error(f"Failed to save vibe profile for {restaurant['name']}")
                    
            except Exception as e:
                logger.error(f"Error processing restaurant {restaurant['name']}: {e}")
                continue
                
    finally:
        db.close()


def map_restaurant_relationships(config: Dict):
    """
    Map relationships between restaurants based on vibe similarity.
    
    Args:
        config: Configuration dictionary
    """
    db = DatabaseManager(config['database'])
    mapper = RelationshipMapper()
    
    try:
        # Get all restaurants with vibe profiles
        query = """
        SELECT 
            r.id,
            r.name,
            r.cuisine,
            r.price_range,
            r.primary_vibes,
            r.energy_level,
            r.formality_level,
            json_build_object(
                'city', r.city,
                'state', r.state,
                'neighborhood', r.neighborhood
            ) as location
        FROM restaurants r
        WHERE r.primary_vibes IS NOT NULL
        LIMIT 100
        """
        
        restaurants = db.execute_query(query)
        
        if not restaurants:
            logger.info("No restaurants with vibe profiles found")
            return
        
        logger.info(f"Mapping relationships for {len(restaurants)} restaurants...")
        
        # Convert to format expected by mapper
        restaurants_data = []
        for r in restaurants:
            restaurants_data.append({
                "id": r['id'],
                "name": r['name'],
                "cuisine": r['cuisine'],
                "price_range": r['price_range'],
                "location": r['location'],
                "vibe_profile": {
                    "primary_vibes": r['primary_vibes'] or [],
                    "secondary_vibes": [],
                    "energy_level": float(r['energy_level'] or 0.5),
                    "formality_level": float(r['formality_level'] or 0.5)
                }
            })
        
        # Map relationships
        relationships = mapper.map_restaurant_relationships(
            restaurants_data,
            max_relationships=config['relationship_mapping']['max_relationships_per_restaurant']
        )
        
        # Save relationships to database
        all_relationships = []
        for restaurant_id, restaurant_relationships in relationships.items():
            for rel in restaurant_relationships:
                all_relationships.append({
                    'restaurant_a_id': rel.restaurant_a_id,
                    'restaurant_b_id': rel.restaurant_b_id,
                    'similarity_score': rel.similarity_score,
                    'vibe_similarity': rel.vibe_similarity,
                    'cuisine_similarity': rel.cuisine_similarity,
                    'price_similarity': rel.price_similarity,
                    'location_proximity': rel.location_proximity,
                    'relationship_type': rel.relationship_type,
                    'confidence': rel.confidence
                })
        
        if all_relationships:
            saved_count = db.save_restaurant_relationships(all_relationships)
            logger.info(f"Saved {saved_count} restaurant relationships")
        
        # Find and log some interesting relationships
        for restaurant_id, restaurant_relationships in list(relationships.items())[:5]:
            restaurant_name = next(r['name'] for r in restaurants_data if r['id'] == restaurant_id)
            logger.info(f"\nTop relationships for {restaurant_name}:")
            
            for rel in restaurant_relationships[:3]:
                related_name = next(r['name'] for r in restaurants_data if r['id'] == rel.restaurant_b_id)
                logger.info(f"  - {related_name}: {rel.similarity_score:.2f} "
                          f"({rel.relationship_type}, vibe similarity: {rel.vibe_similarity:.2f})")
                
    finally:
        db.close()


def generate_sample_insights(config: Dict):
    """
    Generate sample business insights for restaurants.
    
    Args:
        config: Configuration dictionary
    """
    db = DatabaseManager(config['database'])
    
    try:
        # Get restaurants with vibe profiles
        query = """
        SELECT 
            r.id,
            r.name,
            r.primary_vibes,
            r.energy_level,
            r.formality_level,
            r.rating,
            r.review_count,
            COUNT(rr.restaurant_b_id) as relationship_count
        FROM restaurants r
        LEFT JOIN restaurant_relationships rr ON r.id = rr.restaurant_a_id
        WHERE r.primary_vibes IS NOT NULL
        GROUP BY r.id
        LIMIT 10
        """
        
        restaurants = db.execute_query(query)
        
        for restaurant in restaurants:
            # Generate a sample insight based on vibe data
            primary_vibes = restaurant['primary_vibes'] or []
            
            if primary_vibes:
                top_vibe = primary_vibes[0]['vibe']
                
                # Create insight based on vibe analysis
                insight = {
                    'type': 'vibe_analysis',
                    'category': 'vibe_alignment',
                    'data': {
                        'current_vibe': top_vibe,
                        'energy_level': float(restaurant['energy_level'] or 0.5),
                        'formality_level': float(restaurant['formality_level'] or 0.5),
                        'recommendation': f"Your restaurant strongly projects a '{top_vibe}' vibe. "
                                        f"Consider highlighting this in your marketing materials.",
                        'opportunities': [
                            "Update menu descriptions to reinforce vibe identity",
                            "Adjust lighting/music to match desired energy level",
                            "Train staff to embody the restaurant's vibe"
                        ]
                    },
                    'confidence': 0.8,
                    'priority': 'high' if restaurant['review_count'] > 100 else 'medium',
                    'is_actionable': True
                }
                
                success = db.save_insight(restaurant['id'], insight)
                
                if success:
                    logger.info(f"Generated insight for {restaurant['name']}: {top_vibe} vibe analysis")
                    
    finally:
        db.close()


def main():
    """Main function to run the example pipeline."""
    # Load configuration
    config = load_config()
    
    # Check for required API key
    if not config['vibe_extraction']['api_key']:
        logger.error("ANTHROPIC_API_KEY environment variable not set")
        logger.info("Please set: export ANTHROPIC_API_KEY=your_api_key")
        return
    
    # Run pipeline steps
    logger.info("=== Starting Taste Graph Pipeline Example ===")
    
    # Step 1: Extract vibes for restaurants
    logger.info("\n--- Step 1: Extracting Vibes ---")
    extract_vibes_for_restaurants(config, limit=5)
    
    # Step 2: Map restaurant relationships
    logger.info("\n--- Step 2: Mapping Restaurant Relationships ---")
    map_restaurant_relationships(config)
    
    # Step 3: Generate sample insights
    logger.info("\n--- Step 3: Generating Business Insights ---")
    generate_sample_insights(config)
    
    logger.info("\n=== Pipeline Example Complete ===")


if __name__ == "__main__":
    main()