-- ZipPicks Taste Graph Database Schema Migration
-- Version: 1.0
-- Description: Extends existing restaurant data with vibe profiles and taste graph tables

-- Note: This assumes you have an existing PostgreSQL database with a restaurants table
-- The migration enhances the existing schema without breaking current functionality

BEGIN;

-- ============================================
-- Extend existing restaurants table
-- ============================================

-- Add vibe-related columns to existing restaurants table
ALTER TABLE restaurants 
ADD COLUMN IF NOT EXISTS vibe_profile_updated_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS primary_vibes JSONB,
ADD COLUMN IF NOT EXISTS energy_level DECIMAL(3,2) CHECK (energy_level >= 0 AND energy_level <= 1),
ADD COLUMN IF NOT EXISTS formality_level DECIMAL(3,2) CHECK (formality_level >= 0 AND formality_level <= 1),
ADD COLUMN IF NOT EXISTS vibe_extraction_confidence DECIMAL(3,2) CHECK (vibe_extraction_confidence >= 0 AND vibe_extraction_confidence <= 1);

-- Create indexes for vibe-based queries
CREATE INDEX IF NOT EXISTS idx_restaurants_vibes ON restaurants USING GIN (primary_vibes);
CREATE INDEX IF NOT EXISTS idx_restaurants_energy_level ON restaurants (energy_level);
CREATE INDEX IF NOT EXISTS idx_restaurants_formality_level ON restaurants (formality_level);
CREATE INDEX IF NOT EXISTS idx_restaurants_vibe_updated ON restaurants (vibe_profile_updated_at);

-- ============================================
-- Enhanced vibe matches table
-- ============================================

-- If business_vibe_matches exists, extend it; otherwise create it
CREATE TABLE IF NOT EXISTS business_vibe_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL,
    vibe VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Add new columns for enhanced vibe tracking
ALTER TABLE business_vibe_matches
ADD COLUMN IF NOT EXISTS confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
ADD COLUMN IF NOT EXISTS temporal_context VARCHAR(50), -- 'breakfast', 'lunch', 'dinner', 'late_night'
ADD COLUMN IF NOT EXISTS source_type VARCHAR(50), -- 'reviews', 'description', 'menu', 'photos'
ADD COLUMN IF NOT EXISTS is_primary BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS extracted_at TIMESTAMP DEFAULT NOW();

-- Add foreign key if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_vibe_matches_restaurant') THEN
        ALTER TABLE business_vibe_matches 
        ADD CONSTRAINT fk_vibe_matches_restaurant 
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_vibe_matches_restaurant ON business_vibe_matches (restaurant_id);
CREATE INDEX IF NOT EXISTS idx_vibe_matches_vibe ON business_vibe_matches (vibe);
CREATE INDEX IF NOT EXISTS idx_vibe_matches_confidence ON business_vibe_matches (confidence_score);
CREATE INDEX IF NOT EXISTS idx_vibe_matches_temporal ON business_vibe_matches (temporal_context);

-- ============================================
-- User taste profiles table
-- ============================================

CREATE TABLE IF NOT EXISTS user_taste_profiles (
    user_id UUID PRIMARY KEY,
    preferred_vibes JSONB NOT NULL DEFAULT '{}',
    avoided_vibes JSONB NOT NULL DEFAULT '{}',
    cuisine_preferences JSONB NOT NULL DEFAULT '{}',
    contextual_preferences JSONB NOT NULL DEFAULT '{}',
    price_sensitivity DECIMAL(3,2) DEFAULT 0.5 CHECK (price_sensitivity >= 0 AND price_sensitivity <= 1),
    adventure_score DECIMAL(3,2) DEFAULT 0.5 CHECK (adventure_score >= 0 AND adventure_score <= 1),
    social_dining_style VARCHAR(50) DEFAULT 'couples', -- 'solo', 'couples', 'groups', 'family'
    interaction_count INTEGER DEFAULT 0,
    last_interaction_at TIMESTAMP,
    profile_completeness DECIMAL(3,2) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP DEFAULT NOW()
);

-- Create indexes for user profiles
CREATE INDEX IF NOT EXISTS idx_user_profiles_updated ON user_taste_profiles (last_updated);
CREATE INDEX IF NOT EXISTS idx_user_profiles_vibes ON user_taste_profiles USING GIN (preferred_vibes);
CREATE INDEX IF NOT EXISTS idx_user_profiles_cuisines ON user_taste_profiles USING GIN (cuisine_preferences);

-- ============================================
-- User interactions table (for learning)
-- ============================================

CREATE TABLE IF NOT EXISTS user_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_taste_profiles(user_id) ON DELETE CASCADE,
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    interaction_type VARCHAR(50) NOT NULL, -- 'view', 'click', 'bookmark', 'visit', 'rating', 'share'
    interaction_data JSONB, -- Additional context (rating value, time spent, etc.)
    context_data JSONB, -- Time of day, weather, occasion, group size, etc.
    restaurant_vibes JSONB, -- Snapshot of restaurant vibes at interaction time
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_interactions_user ON user_interactions (user_id);
CREATE INDEX IF NOT EXISTS idx_interactions_restaurant ON user_interactions (restaurant_id);
CREATE INDEX IF NOT EXISTS idx_interactions_type ON user_interactions (interaction_type);
CREATE INDEX IF NOT EXISTS idx_interactions_created ON user_interactions (created_at);

-- ============================================
-- Restaurant relationships table
-- ============================================

CREATE TABLE IF NOT EXISTS restaurant_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_a_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    restaurant_b_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    similarity_score DECIMAL(3,2) NOT NULL CHECK (similarity_score >= 0 AND similarity_score <= 1),
    vibe_similarity DECIMAL(3,2) CHECK (vibe_similarity >= 0 AND vibe_similarity <= 1),
    cuisine_similarity DECIMAL(3,2) CHECK (cuisine_similarity >= 0 AND cuisine_similarity <= 1),
    price_similarity DECIMAL(3,2) CHECK (price_similarity >= 0 AND price_similarity <= 1),
    location_proximity DECIMAL(3,2) CHECK (location_proximity >= 0 AND location_proximity <= 1),
    relationship_type VARCHAR(50) NOT NULL, -- 'similar', 'complementary', 'alternative'
    confidence DECIMAL(3,2) CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_restaurant_pair UNIQUE (restaurant_a_id, restaurant_b_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_relationships_restaurant_a ON restaurant_relationships (restaurant_a_id);
CREATE INDEX IF NOT EXISTS idx_relationships_restaurant_b ON restaurant_relationships (restaurant_b_id);
CREATE INDEX IF NOT EXISTS idx_relationships_similarity ON restaurant_relationships (similarity_score DESC);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON restaurant_relationships (relationship_type);

-- ============================================
-- Taste graph insights table (B2B analytics)
-- ============================================

CREATE TABLE IF NOT EXISTS taste_graph_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    insight_type VARCHAR(100) NOT NULL, -- 'performance', 'competitive', 'opportunity', 'trend'
    insight_category VARCHAR(100), -- 'vibe_alignment', 'market_position', 'demand_forecast', etc.
    insight_data JSONB NOT NULL, -- Flexible structure for different insight types
    confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    priority VARCHAR(20) DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
    is_actionable BOOLEAN DEFAULT true,
    action_taken BOOLEAN DEFAULT false,
    generated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    viewed_at TIMESTAMP,
    acted_at TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_insights_restaurant ON taste_graph_insights (restaurant_id);
CREATE INDEX IF NOT EXISTS idx_insights_type ON taste_graph_insights (insight_type);
CREATE INDEX IF NOT EXISTS idx_insights_category ON taste_graph_insights (insight_category);
CREATE INDEX IF NOT EXISTS idx_insights_priority ON taste_graph_insights (priority);
CREATE INDEX IF NOT EXISTS idx_insights_generated ON taste_graph_insights (generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_insights_expires ON taste_graph_insights (expires_at);

-- ============================================
-- Vibe trends table (temporal analysis)
-- ============================================

CREATE TABLE IF NOT EXISTS vibe_trends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vibe VARCHAR(100) NOT NULL,
    geography_type VARCHAR(50) NOT NULL, -- 'city', 'neighborhood', 'region'
    geography_id VARCHAR(255) NOT NULL,
    trend_period VARCHAR(20) NOT NULL, -- 'daily', 'weekly', 'monthly'
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    popularity_score DECIMAL(5,2),
    growth_rate DECIMAL(5,2), -- Percentage change from previous period
    restaurant_count INTEGER,
    interaction_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_vibe_trend UNIQUE (vibe, geography_type, geography_id, trend_period, period_start)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_trends_vibe ON vibe_trends (vibe);
CREATE INDEX IF NOT EXISTS idx_trends_geography ON vibe_trends (geography_type, geography_id);
CREATE INDEX IF NOT EXISTS idx_trends_period ON vibe_trends (period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_trends_growth ON vibe_trends (growth_rate DESC);

-- ============================================
-- Recommendation cache table
-- ============================================

CREATE TABLE IF NOT EXISTS recommendation_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES user_taste_profiles(user_id) ON DELETE CASCADE,
    cache_key VARCHAR(255) NOT NULL, -- Composite key for context
    recommendations JSONB NOT NULL, -- Array of restaurant IDs with scores
    context_data JSONB, -- Context used for generation
    generated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    hit_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_cache_user ON recommendation_cache (user_id);
CREATE INDEX IF NOT EXISTS idx_cache_key ON recommendation_cache (cache_key);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON recommendation_cache (expires_at);

-- ============================================
-- Audit and analytics tables
-- ============================================

CREATE TABLE IF NOT EXISTS taste_graph_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_type VARCHAR(100) NOT NULL,
    metric_name VARCHAR(255) NOT NULL,
    metric_value NUMERIC,
    metric_data JSONB,
    dimension_data JSONB, -- Breakdown by various dimensions
    period_type VARCHAR(20), -- 'hourly', 'daily', 'weekly', 'monthly'
    period_start TIMESTAMP,
    period_end TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_analytics_type ON taste_graph_analytics (metric_type, metric_name);
CREATE INDEX IF NOT EXISTS idx_analytics_period ON taste_graph_analytics (period_start, period_end);

-- ============================================
-- Functions and triggers
-- ============================================

-- Function to update last_updated timestamp
CREATE OR REPLACE FUNCTION update_last_updated_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for last_updated
DROP TRIGGER IF EXISTS update_user_profiles_updated ON user_taste_profiles;
CREATE TRIGGER update_user_profiles_updated
    BEFORE UPDATE ON user_taste_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_last_updated_column();

DROP TRIGGER IF EXISTS update_relationships_updated ON restaurant_relationships;
CREATE TRIGGER update_relationships_updated
    BEFORE UPDATE ON restaurant_relationships
    FOR EACH ROW
    EXECUTE FUNCTION update_last_updated_column();

-- Function to calculate profile completeness
CREATE OR REPLACE FUNCTION calculate_profile_completeness(profile user_taste_profiles)
RETURNS DECIMAL AS $$
DECLARE
    completeness DECIMAL := 0;
    factor_count INTEGER := 0;
BEGIN
    -- Check preferred vibes
    IF jsonb_array_length(profile.preferred_vibes) > 0 THEN
        completeness := completeness + 0.25;
    END IF;
    
    -- Check cuisine preferences
    IF jsonb_array_length(profile.cuisine_preferences) > 0 THEN
        completeness := completeness + 0.25;
    END IF;
    
    -- Check if has interactions
    IF profile.interaction_count > 5 THEN
        completeness := completeness + 0.25;
    END IF;
    
    -- Check contextual preferences
    IF jsonb_array_length(profile.contextual_preferences) > 0 THEN
        completeness := completeness + 0.25;
    END IF;
    
    RETURN completeness;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Initial data and views
-- ============================================

-- View for restaurant vibe summary
CREATE OR REPLACE VIEW restaurant_vibe_summary AS
SELECT 
    r.id,
    r.name,
    r.cuisine,
    r.price_range,
    r.primary_vibes,
    r.energy_level,
    r.formality_level,
    r.vibe_extraction_confidence,
    COUNT(DISTINCT bvm.vibe) as vibe_count,
    AVG(bvm.confidence_score) as avg_vibe_confidence,
    r.vibe_profile_updated_at
FROM restaurants r
LEFT JOIN business_vibe_matches bvm ON r.id = bvm.restaurant_id
GROUP BY r.id;

-- View for user taste summary
CREATE OR REPLACE VIEW user_taste_summary AS
SELECT 
    utp.user_id,
    utp.adventure_score,
    utp.price_sensitivity,
    utp.social_dining_style,
    jsonb_array_length(utp.preferred_vibes) as preferred_vibe_count,
    jsonb_array_length(utp.avoided_vibes) as avoided_vibe_count,
    jsonb_array_length(utp.cuisine_preferences) as cuisine_preference_count,
    utp.interaction_count,
    utp.profile_completeness,
    utp.last_interaction_at
FROM user_taste_profiles utp;

-- ============================================
-- Permissions (adjust based on your user setup)
-- ============================================

-- Grant permissions to application user (replace 'app_user' with your actual user)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
-- GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO app_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO app_user;

COMMIT;

-- ============================================
-- Rollback script (save separately)
-- ============================================
/*
BEGIN;

-- Remove views
DROP VIEW IF EXISTS user_taste_summary;
DROP VIEW IF EXISTS restaurant_vibe_summary;

-- Remove functions
DROP FUNCTION IF EXISTS calculate_profile_completeness(user_taste_profiles);
DROP FUNCTION IF EXISTS update_last_updated_column();

-- Remove tables in reverse order of dependencies
DROP TABLE IF EXISTS taste_graph_analytics;
DROP TABLE IF EXISTS recommendation_cache;
DROP TABLE IF EXISTS vibe_trends;
DROP TABLE IF EXISTS taste_graph_insights;
DROP TABLE IF EXISTS restaurant_relationships;
DROP TABLE IF EXISTS user_interactions;
DROP TABLE IF EXISTS user_taste_profiles;

-- Remove columns from restaurants table
ALTER TABLE restaurants 
DROP COLUMN IF EXISTS vibe_profile_updated_at,
DROP COLUMN IF EXISTS primary_vibes,
DROP COLUMN IF EXISTS energy_level,
DROP COLUMN IF EXISTS formality_level,
DROP COLUMN IF EXISTS vibe_extraction_confidence;

-- Remove columns from business_vibe_matches
ALTER TABLE business_vibe_matches
DROP COLUMN IF EXISTS confidence_score,
DROP COLUMN IF EXISTS temporal_context,
DROP COLUMN IF EXISTS source_type,
DROP COLUMN IF EXISTS is_primary,
DROP COLUMN IF EXISTS extracted_at;

COMMIT;
*/