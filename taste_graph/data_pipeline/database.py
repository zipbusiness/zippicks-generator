"""
Database connection and management for Taste Graph

Handles PostgreSQL connections and provides database utilities.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import ThreadedConnectionPool
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages PostgreSQL database connections and operations."""
    
    def __init__(self, connection_params: Optional[Dict[str, Any]] = None):
        """
        Initialize database manager.
        
        Args:
            connection_params: Database connection parameters
                - host: Database host
                - port: Database port
                - database: Database name
                - user: Database user
                - password: Database password
        """
        if connection_params:
            self.connection_params = connection_params
        else:
            # Load from environment variables
            self.connection_params = {
                'host': os.getenv('POSTGRES_HOST', 'localhost'),
                'port': os.getenv('POSTGRES_PORT', '5432'),
                'database': os.getenv('POSTGRES_DB', 'zipbusiness'),
                'user': os.getenv('POSTGRES_USER', 'postgres'),
                'password': os.getenv('POSTGRES_PASSWORD', '')
            }
        
        # Initialize connection pool
        self.pool = None
        self._initialize_pool()
    
    def _initialize_pool(self, min_connections: int = 2, max_connections: int = 10):
        """Initialize connection pool."""
        try:
            self.pool = ThreadedConnectionPool(
                min_connections,
                max_connections,
                **self.connection_params
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Get a database connection from the pool."""
        connection = None
        try:
            connection = self.pool.getconn()
            yield connection
            connection.commit()
        except Exception as e:
            if connection:
                connection.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if connection:
                self.pool.putconn(connection)
    
    @contextmanager
    def get_cursor(self, cursor_factory=RealDictCursor):
        """Get a database cursor."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """
        Execute a SELECT query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of dictionaries representing rows
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: Optional[tuple] = None) -> int:
        """
        Execute an INSERT/UPDATE/DELETE query.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Number of affected rows
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """
        Execute multiple INSERT/UPDATE queries.
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
            
        Returns:
            Total number of affected rows
        """
        with self.get_cursor() as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount
    
    # Taste Graph specific methods
    
    def save_vibe_profile(self, restaurant_id: str, vibe_profile: Dict) -> bool:
        """
        Save or update a restaurant's vibe profile.
        
        Args:
            restaurant_id: Restaurant UUID
            vibe_profile: Vibe profile data
            
        Returns:
            Success boolean
        """
        query = """
        UPDATE restaurants 
        SET primary_vibes = %s,
            energy_level = %s,
            formality_level = %s,
            vibe_extraction_confidence = %s,
            vibe_profile_updated_at = %s
        WHERE id = %s
        """
        
        params = (
            Json(vibe_profile.get('primary_vibes', [])),
            vibe_profile.get('energy_level', 0.5),
            vibe_profile.get('formality_level', 0.5),
            vibe_profile.get('vibe_confidence', 0.5),
            datetime.now(),
            restaurant_id
        )
        
        try:
            rows_affected = self.execute_update(query, params)
            
            # Also save individual vibe matches
            self._save_vibe_matches(restaurant_id, vibe_profile)
            
            return rows_affected > 0
        except Exception as e:
            logger.error(f"Failed to save vibe profile for {restaurant_id}: {e}")
            return False
    
    def _save_vibe_matches(self, restaurant_id: str, vibe_profile: Dict):
        """Save individual vibe matches."""
        # Clear existing matches
        delete_query = "DELETE FROM business_vibe_matches WHERE restaurant_id = %s"
        self.execute_update(delete_query, (restaurant_id,))
        
        # Insert new matches
        insert_query = """
        INSERT INTO business_vibe_matches 
        (restaurant_id, vibe, confidence_score, source_type, is_primary, extracted_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        params_list = []
        
        # Primary vibes
        for vibe_data in vibe_profile.get('primary_vibes', []):
            params_list.append((
                restaurant_id,
                vibe_data['vibe'],
                vibe_data['score'],
                ','.join(vibe_profile.get('source_types', ['unknown'])),
                True,
                vibe_profile.get('extracted_at', datetime.now())
            ))
        
        # Secondary vibes
        for vibe_data in vibe_profile.get('secondary_vibes', []):
            params_list.append((
                restaurant_id,
                vibe_data['vibe'],
                vibe_data['score'],
                ','.join(vibe_profile.get('source_types', ['unknown'])),
                False,
                vibe_profile.get('extracted_at', datetime.now())
            ))
        
        if params_list:
            self.execute_many(insert_query, params_list)
    
    def get_restaurant_vibe_profile(self, restaurant_id: str) -> Optional[Dict]:
        """
        Get a restaurant's vibe profile.
        
        Args:
            restaurant_id: Restaurant UUID
            
        Returns:
            Vibe profile dictionary or None
        """
        query = """
        SELECT 
            r.id,
            r.name,
            r.primary_vibes,
            r.energy_level,
            r.formality_level,
            r.vibe_extraction_confidence,
            r.vibe_profile_updated_at,
            array_agg(
                DISTINCT jsonb_build_object(
                    'vibe', bvm.vibe,
                    'score', bvm.confidence_score,
                    'is_primary', bvm.is_primary
                )
            ) FILTER (WHERE bvm.vibe IS NOT NULL) as vibe_matches
        FROM restaurants r
        LEFT JOIN business_vibe_matches bvm ON r.id = bvm.restaurant_id
        WHERE r.id = %s
        GROUP BY r.id
        """
        
        results = self.execute_query(query, (restaurant_id,))
        
        if results:
            profile = results[0]
            
            # Restructure vibe matches
            if profile['vibe_matches']:
                primary_vibes = [v for v in profile['vibe_matches'] if v['is_primary']]
                secondary_vibes = [v for v in profile['vibe_matches'] if not v['is_primary']]
                
                profile['primary_vibes'] = primary_vibes
                profile['secondary_vibes'] = secondary_vibes
            
            return profile
        
        return None
    
    def save_user_taste_profile(self, user_id: str, taste_profile: Dict) -> bool:
        """
        Save or update a user's taste profile.
        
        Args:
            user_id: User UUID
            taste_profile: Taste profile data
            
        Returns:
            Success boolean
        """
        query = """
        INSERT INTO user_taste_profiles 
        (user_id, preferred_vibes, avoided_vibes, cuisine_preferences, 
         contextual_preferences, price_sensitivity, adventure_score, 
         social_dining_style, last_updated)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            preferred_vibes = EXCLUDED.preferred_vibes,
            avoided_vibes = EXCLUDED.avoided_vibes,
            cuisine_preferences = EXCLUDED.cuisine_preferences,
            contextual_preferences = EXCLUDED.contextual_preferences,
            price_sensitivity = EXCLUDED.price_sensitivity,
            adventure_score = EXCLUDED.adventure_score,
            social_dining_style = EXCLUDED.social_dining_style,
            last_updated = EXCLUDED.last_updated
        """
        
        params = (
            user_id,
            Json(taste_profile.get('preferred_vibes', {})),
            Json(taste_profile.get('avoided_vibes', {})),
            Json(taste_profile.get('cuisine_preferences', {})),
            Json(taste_profile.get('contextual_preferences', {})),
            taste_profile.get('price_sensitivity', 0.5),
            taste_profile.get('adventure_score', 0.5),
            taste_profile.get('social_dining_style', 'couples'),
            datetime.now()
        )
        
        try:
            rows_affected = self.execute_update(query, params)
            return rows_affected > 0
        except Exception as e:
            logger.error(f"Failed to save taste profile for {user_id}: {e}")
            return False
    
    def get_user_taste_profile(self, user_id: str) -> Optional[Dict]:
        """
        Get a user's taste profile.
        
        Args:
            user_id: User UUID
            
        Returns:
            Taste profile dictionary or None
        """
        query = """
        SELECT 
            user_id,
            preferred_vibes,
            avoided_vibes,
            cuisine_preferences,
            contextual_preferences,
            price_sensitivity,
            adventure_score,
            social_dining_style,
            interaction_count,
            profile_completeness,
            last_updated,
            last_interaction_at
        FROM user_taste_profiles
        WHERE user_id = %s
        """
        
        results = self.execute_query(query, (user_id,))
        return results[0] if results else None
    
    def save_user_interaction(self, user_id: str, interaction: Dict) -> bool:
        """
        Save a user interaction for learning.
        
        Args:
            user_id: User UUID
            interaction: Interaction data
            
        Returns:
            Success boolean
        """
        query = """
        INSERT INTO user_interactions 
        (user_id, restaurant_id, interaction_type, interaction_data, 
         context_data, restaurant_vibes)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        params = (
            user_id,
            interaction['restaurant_id'],
            interaction['type'],
            Json(interaction.get('data', {})),
            Json(interaction.get('context', {})),
            Json(interaction.get('restaurant_vibes', {}))
        )
        
        try:
            self.execute_update(query, params)
            
            # Update interaction count and last interaction time
            update_query = """
            UPDATE user_taste_profiles 
            SET interaction_count = interaction_count + 1,
                last_interaction_at = NOW()
            WHERE user_id = %s
            """
            self.execute_update(update_query, (user_id,))
            
            return True
        except Exception as e:
            logger.error(f"Failed to save interaction: {e}")
            return False
    
    def save_restaurant_relationships(self, relationships: List[Dict]) -> int:
        """
        Save restaurant relationships in bulk.
        
        Args:
            relationships: List of relationship dictionaries
            
        Returns:
            Number of relationships saved
        """
        query = """
        INSERT INTO restaurant_relationships 
        (restaurant_a_id, restaurant_b_id, similarity_score, vibe_similarity,
         cuisine_similarity, price_similarity, location_proximity, 
         relationship_type, confidence)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (restaurant_a_id, restaurant_b_id) DO UPDATE SET
            similarity_score = EXCLUDED.similarity_score,
            vibe_similarity = EXCLUDED.vibe_similarity,
            cuisine_similarity = EXCLUDED.cuisine_similarity,
            price_similarity = EXCLUDED.price_similarity,
            location_proximity = EXCLUDED.location_proximity,
            relationship_type = EXCLUDED.relationship_type,
            confidence = EXCLUDED.confidence,
            updated_at = NOW()
        """
        
        params_list = [
            (
                rel['restaurant_a_id'],
                rel['restaurant_b_id'],
                rel['similarity_score'],
                rel.get('vibe_similarity', 0),
                rel.get('cuisine_similarity', 0),
                rel.get('price_similarity', 0),
                rel.get('location_proximity', 0),
                rel['relationship_type'],
                rel.get('confidence', 0.5)
            )
            for rel in relationships
        ]
        
        try:
            return self.execute_many(query, params_list)
        except Exception as e:
            logger.error(f"Failed to save relationships: {e}")
            return 0
    
    def save_insight(self, restaurant_id: str, insight: Dict) -> bool:
        """
        Save a business intelligence insight.
        
        Args:
            restaurant_id: Restaurant UUID
            insight: Insight data
            
        Returns:
            Success boolean
        """
        query = """
        INSERT INTO taste_graph_insights 
        (restaurant_id, insight_type, insight_category, insight_data,
         confidence_score, priority, is_actionable, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        params = (
            restaurant_id,
            insight['type'],
            insight.get('category'),
            Json(insight['data']),
            insight.get('confidence', 0.5),
            insight.get('priority', 'medium'),
            insight.get('is_actionable', True),
            insight.get('expires_at')
        )
        
        try:
            self.execute_update(query, params)
            return True
        except Exception as e:
            logger.error(f"Failed to save insight: {e}")
            return False
    
    def get_restaurants_for_vibe_extraction(self, limit: int = 100) -> List[Dict]:
        """
        Get restaurants that need vibe extraction.
        
        Args:
            limit: Maximum number of restaurants to return
            
        Returns:
            List of restaurant dictionaries
        """
        query = """
        SELECT 
            r.id,
            r.name,
            r.cuisine,
            r.price_range,
            r.description,
            r.address,
            r.city,
            r.state,
            r.rating,
            r.review_count
        FROM restaurants r
        WHERE r.vibe_profile_updated_at IS NULL
           OR r.vibe_profile_updated_at < NOW() - INTERVAL '30 days'
        ORDER BY r.review_count DESC NULLS LAST
        LIMIT %s
        """
        
        return self.execute_query(query, (limit,))
    
    def close(self):
        """Close all database connections."""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connection pool closed")