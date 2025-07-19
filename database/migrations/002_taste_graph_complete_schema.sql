-- ZipPicks Taste Graph Complete Database Schema
-- Version: 2.0
-- Description: Production-ready schema for the Taste Graph system
-- IMPORTANT: This preserves the existing restaurants table and rebuilds everything else

BEGIN;

-- ============================================
-- STEP 1: Drop existing tables that need rebuilding
-- ============================================

DROP TABLE IF EXISTS business_vibe_matches CASCADE;
DROP TABLE IF EXISTS vibe_match_cache CASCADE;
DROP TABLE IF EXISTS restaurant_trends CASCADE;

-- ============================================
-- STEP 2: Extend existing restaurants table
-- ============================================

-- Add Taste Graph specific columns to restaurants table
ALTER TABLE restaurants 
ADD COLUMN IF NOT EXISTS vibe_profile_extracted_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS vibe_extraction_version INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS taste_graph_score DOUBLE PRECISION DEFAULT 0.0 CHECK (taste_graph_score >= 0 AND taste_graph_score <= 1),
ADD COLUMN IF NOT EXISTS embedding_vector DOUBLE PRECISION[], -- For ML similarity calculations
ADD COLUMN IF NOT EXISTS taste_graph_metadata JSONB DEFAULT '{}'::jsonb;

-- Create indexes for new columns
CREATE INDEX IF NOT EXISTS idx_restaurants_vibe_extracted ON restaurants (vibe_profile_extracted_at);
CREATE INDEX IF NOT EXISTS idx_restaurants_taste_score ON restaurants (taste_graph_score DESC);
CREATE INDEX IF NOT EXISTS idx_restaurants_embedding ON restaurants USING ivfflat (embedding_vector vector_cosine_ops) 
  WHERE embedding_vector IS NOT NULL; -- Requires pgvector extension

-- ============================================
-- STEP 3: Core Vibe System Tables
-- ============================================

-- Master vibe definitions table
CREATE TABLE vibe_definitions (
    id SERIAL PRIMARY KEY,
    vibe_name VARCHAR(50) NOT NULL UNIQUE,
    vibe_slug VARCHAR(50) NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL, -- 'atmosphere', 'energy', 'occasion', 'style'
    description TEXT,
    parent_vibe_id INTEGER REFERENCES vibe_definitions(id),
    icon_name VARCHAR(50),
    color_hex VARCHAR(7),
    display_order INTEGER DEFAULT 999,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Restaurant vibe profiles (replaces business_vibe_matches)
CREATE TABLE restaurant_vibe_profiles (
    id SERIAL PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    vibe_id INTEGER NOT NULL REFERENCES vibe_definitions(id),
    score DOUBLE PRECISION NOT NULL CHECK (score >= 0 AND score <= 1),
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    is_primary BOOLEAN DEFAULT false,
    extraction_method VARCHAR(50) NOT NULL, -- 'claude_api', 'user_votes', 'review_analysis', 'manual'
    source_data JSONB, -- Store source reviews/data used for extraction
    temporal_context VARCHAR(50), -- 'all_day', 'breakfast', 'lunch', 'dinner', 'late_night'
    extracted_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ, -- For time-sensitive vibes
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_restaurant_vibe_temporal UNIQUE (restaurant_id, vibe_id, temporal_context)
);

-- Vibe relationships and hierarchy
CREATE TABLE vibe_relationships (
    id SERIAL PRIMARY KEY,
    vibe_a_id INTEGER NOT NULL REFERENCES vibe_definitions(id),
    vibe_b_id INTEGER NOT NULL REFERENCES vibe_definitions(id),
    relationship_type VARCHAR(50) NOT NULL, -- 'similar', 'opposite', 'includes', 'complements'
    strength DOUBLE PRECISION DEFAULT 0.5 CHECK (strength >= 0 AND strength <= 1),
    bidirectional BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_vibe_pair UNIQUE (vibe_a_id, vibe_b_id),
    CONSTRAINT no_self_relationship CHECK (vibe_a_id != vibe_b_id)
);

-- ============================================
-- STEP 4: User System Tables
-- ============================================

-- User accounts (B2C)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(255) UNIQUE, -- For integration with auth systems
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    date_of_birth DATE,
    gender VARCHAR(20),
    location_lat DOUBLE PRECISION,
    location_lng DOUBLE PRECISION,
    default_search_radius INTEGER DEFAULT 10, -- miles
    preferences JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User taste profiles
CREATE TABLE user_taste_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    preferred_vibes JSONB NOT NULL DEFAULT '{}'::jsonb, -- {"romantic": 0.8, "casual": 0.6}
    avoided_vibes JSONB NOT NULL DEFAULT '{}'::jsonb,
    cuisine_preferences JSONB NOT NULL DEFAULT '{}'::jsonb, -- {"italian": 0.9, "thai": 0.7}
    dietary_restrictions JSONB DEFAULT '[]'::jsonb, -- ["vegetarian", "gluten_free"]
    price_sensitivity DOUBLE PRECISION DEFAULT 0.5 CHECK (price_sensitivity >= 0 AND price_sensitivity <= 1),
    adventure_score DOUBLE PRECISION DEFAULT 0.5 CHECK (adventure_score >= 0 AND adventure_score <= 1),
    quality_threshold DOUBLE PRECISION DEFAULT 0.7 CHECK (quality_threshold >= 0 AND quality_threshold <= 1),
    social_dining_style VARCHAR(50) DEFAULT 'flexible', -- 'solo', 'couples', 'groups', 'family', 'flexible'
    time_preferences JSONB DEFAULT '{}'::jsonb, -- {"dinner": {"early": 0.8, "late": 0.2}}
    contextual_preferences JSONB DEFAULT '{}'::jsonb,
    taste_vector DOUBLE PRECISION[], -- ML embedding for similarity
    profile_completeness DOUBLE PRECISION DEFAULT 0.0,
    last_calculated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User interactions for learning
CREATE TABLE user_interactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id),
    interaction_type VARCHAR(50) NOT NULL, -- 'view', 'click', 'bookmark', 'share', 'visit', 'rating', 'review'
    interaction_value DOUBLE PRECISION, -- rating value, time spent, etc.
    interaction_metadata JSONB, -- additional context
    device_type VARCHAR(50),
    session_id VARCHAR(100),
    context_data JSONB, -- time, weather, occasion, group_size
    restaurant_snapshot JSONB, -- snapshot of restaurant data at interaction time
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- User bookmarks/favorites
CREATE TABLE user_bookmarks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id),
    list_name VARCHAR(100) DEFAULT 'favorites',
    notes TEXT,
    tags JSONB DEFAULT '[]'::jsonb,
    is_visited BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_user_restaurant_list UNIQUE (user_id, restaurant_id, list_name)
);

-- ============================================
-- STEP 5: Restaurant Relationships & Discovery
-- ============================================

-- Restaurant similarity relationships
CREATE TABLE restaurant_relationships (
    id SERIAL PRIMARY KEY,
    restaurant_a_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    restaurant_b_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    similarity_overall DOUBLE PRECISION NOT NULL CHECK (similarity_overall >= 0 AND similarity_overall <= 1),
    similarity_vibe DOUBLE PRECISION CHECK (similarity_vibe >= 0 AND similarity_vibe <= 1),
    similarity_cuisine DOUBLE PRECISION CHECK (similarity_cuisine >= 0 AND similarity_cuisine <= 1),
    similarity_price DOUBLE PRECISION CHECK (similarity_price >= 0 AND similarity_price <= 1),
    similarity_quality DOUBLE PRECISION CHECK (similarity_quality >= 0 AND similarity_quality <= 1),
    relationship_type VARCHAR(50) NOT NULL, -- 'similar', 'complementary', 'alternative', 'upgrade', 'downgrade'
    relationship_metadata JSONB,
    confidence DOUBLE PRECISION DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    algorithm_version INTEGER DEFAULT 1,
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 days',
    CONSTRAINT unique_restaurant_pair UNIQUE (restaurant_a_id, restaurant_b_id),
    CONSTRAINT no_self_relationship CHECK (restaurant_a_id != restaurant_b_id)
);

-- Restaurant clusters for discovery
CREATE TABLE restaurant_clusters (
    id SERIAL PRIMARY KEY,
    cluster_name VARCHAR(100) NOT NULL,
    cluster_type VARCHAR(50) NOT NULL, -- 'vibe', 'cuisine', 'price', 'quality', 'hybrid'
    cluster_definition JSONB NOT NULL, -- criteria for cluster membership
    center_restaurant_id INTEGER REFERENCES restaurants(id),
    member_count INTEGER DEFAULT 0,
    avg_similarity DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE restaurant_cluster_members (
    id SERIAL PRIMARY KEY,
    cluster_id INTEGER NOT NULL REFERENCES restaurant_clusters(id) ON DELETE CASCADE,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    distance_from_center DOUBLE PRECISION,
    membership_score DOUBLE PRECISION CHECK (membership_score >= 0 AND membership_score <= 1),
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_cluster_member UNIQUE (cluster_id, restaurant_id)
);

-- ============================================
-- STEP 6: Recommendations & Personalization
-- ============================================

-- Recommendation sessions
CREATE TABLE recommendation_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    query_params JSONB NOT NULL, -- location, filters, context
    algorithm_version VARCHAR(50),
    total_results INTEGER,
    results_shown INTEGER,
    user_actions JSONB DEFAULT '[]'::jsonb,
    performance_metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '24 hours'
);

-- Recommendation results cache
CREATE TABLE recommendation_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(255) NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    query_hash VARCHAR(64) NOT NULL,
    recommendations JSONB NOT NULL, -- [{restaurant_id, score, reasons}]
    algorithm_version VARCHAR(50),
    context_data JSONB,
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_cache_lookup (cache_key, user_id, expires_at)
);

-- ============================================
-- STEP 7: Business Intelligence (B2B)
-- ============================================

-- Business accounts for restaurants
CREATE TABLE business_accounts (
    id SERIAL PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id),
    account_type VARCHAR(50) NOT NULL, -- 'free', 'starter', 'professional', 'enterprise'
    primary_contact_email VARCHAR(255) NOT NULL,
    primary_contact_name VARCHAR(255),
    billing_email VARCHAR(255),
    subscription_status VARCHAR(50) DEFAULT 'active',
    subscription_started_at TIMESTAMPTZ,
    subscription_ends_at TIMESTAMPTZ,
    features_enabled JSONB DEFAULT '[]'::jsonb,
    api_key VARCHAR(100) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_restaurant_account UNIQUE (restaurant_id)
);

-- Business insights
CREATE TABLE business_insights (
    id SERIAL PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    insight_type VARCHAR(100) NOT NULL, -- 'performance', 'competitive', 'opportunity', 'trend', 'action'
    insight_category VARCHAR(100), -- 'vibe_alignment', 'market_position', 'customer_sentiment'
    title VARCHAR(255) NOT NULL,
    description TEXT,
    insight_data JSONB NOT NULL,
    impact_score DOUBLE PRECISION CHECK (impact_score >= 0 AND impact_score <= 1),
    confidence_score DOUBLE PRECISION CHECK (confidence_score >= 0 AND confidence_score <= 1),
    priority VARCHAR(20) DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
    is_actionable BOOLEAN DEFAULT true,
    suggested_actions JSONB DEFAULT '[]'::jsonb,
    related_insights INTEGER[] DEFAULT '{}',
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    valid_until TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days',
    viewed_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,
    action_taken_at TIMESTAMPTZ,
    action_result JSONB
);

-- Competitive intelligence
CREATE TABLE competitive_sets (
    id SERIAL PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    competitor_id INTEGER NOT NULL REFERENCES restaurants(id),
    competition_type VARCHAR(50), -- 'direct', 'indirect', 'aspirational'
    similarity_score DOUBLE PRECISION CHECK (similarity_score >= 0 AND similarity_score <= 1),
    market_overlap DOUBLE PRECISION CHECK (market_overlap >= 0 AND market_overlap <= 1),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_competitive_pair UNIQUE (restaurant_id, competitor_id)
);

-- ============================================
-- STEP 8: Analytics & Metrics
-- ============================================

-- Vibe trends over time
CREATE TABLE vibe_trends (
    id SERIAL PRIMARY KEY,
    vibe_id INTEGER NOT NULL REFERENCES vibe_definitions(id),
    geography_type VARCHAR(50) NOT NULL, -- 'city', 'state', 'neighborhood', 'zipcode'
    geography_value VARCHAR(255) NOT NULL,
    trend_period VARCHAR(20) NOT NULL, -- 'daily', 'weekly', 'monthly', 'quarterly'
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    restaurant_count INTEGER DEFAULT 0,
    avg_vibe_score DOUBLE PRECISION,
    total_interactions INTEGER DEFAULT 0,
    growth_rate DOUBLE PRECISION, -- % change from previous period
    popularity_rank INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_vibe_trend UNIQUE (vibe_id, geography_type, geography_value, trend_period, period_start)
);

-- Performance metrics
CREATE TABLE taste_graph_metrics (
    id SERIAL PRIMARY KEY,
    metric_type VARCHAR(100) NOT NULL,
    metric_name VARCHAR(255) NOT NULL,
    metric_value NUMERIC,
    metric_metadata JSONB,
    dimension_type VARCHAR(50), -- 'user_segment', 'restaurant_type', 'geography'
    dimension_value VARCHAR(255),
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- STEP 9: Enhanced Restaurant Trends (Rebuild)
-- ============================================

CREATE TABLE restaurant_performance_trends (
    id SERIAL PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,
    -- Rating metrics
    yelp_rating DOUBLE PRECISION,
    yelp_review_count INTEGER,
    google_rating DOUBLE PRECISION,
    google_review_count INTEGER,
    combined_rating DOUBLE PRECISION,
    rating_momentum DOUBLE PRECISION, -- trend direction and strength
    -- Taste graph metrics
    taste_graph_score DOUBLE PRECISION,
    vibe_consistency DOUBLE PRECISION,
    recommendation_frequency INTEGER DEFAULT 0,
    click_through_rate DOUBLE PRECISION,
    conversion_rate DOUBLE PRECISION,
    -- Competitive metrics
    market_position_percentile DOUBLE PRECISION,
    competitive_advantage_score DOUBLE PRECISION,
    -- Sentiment metrics
    sentiment_score DOUBLE PRECISION,
    sentiment_volume INTEGER,
    -- Operational metrics
    response_rate DOUBLE PRECISION,
    response_time_hours DOUBLE PRECISION,
    -- Calculated fields
    trend_direction VARCHAR(20), -- 'improving', 'stable', 'declining'
    anomaly_detected BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_restaurant_date UNIQUE (restaurant_id, metric_date)
);

-- ============================================
-- STEP 10: Indexes for Performance
-- ============================================

-- Vibe system indexes
CREATE INDEX idx_vibe_profiles_restaurant ON restaurant_vibe_profiles (restaurant_id);
CREATE INDEX idx_vibe_profiles_vibe ON restaurant_vibe_profiles (vibe_id);
CREATE INDEX idx_vibe_profiles_primary ON restaurant_vibe_profiles (restaurant_id, is_primary) WHERE is_primary = true;
CREATE INDEX idx_vibe_profiles_temporal ON restaurant_vibe_profiles (restaurant_id, temporal_context);
CREATE INDEX idx_vibe_profiles_confidence ON restaurant_vibe_profiles (confidence DESC);

-- User system indexes
CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_location ON users USING gist (ll_to_earth(location_lat, location_lng));
CREATE INDEX idx_interactions_user ON user_interactions (user_id, created_at DESC);
CREATE INDEX idx_interactions_restaurant ON user_interactions (restaurant_id, interaction_type);
CREATE INDEX idx_interactions_session ON user_interactions (session_id);
CREATE INDEX idx_bookmarks_user ON user_bookmarks (user_id);

-- Relationship indexes
CREATE INDEX idx_relationships_restaurant_a ON restaurant_relationships (restaurant_a_id, similarity_overall DESC);
CREATE INDEX idx_relationships_restaurant_b ON restaurant_relationships (restaurant_b_id, similarity_overall DESC);
CREATE INDEX idx_relationships_type ON restaurant_relationships (relationship_type);

-- Business intelligence indexes
CREATE INDEX idx_insights_restaurant ON business_insights (restaurant_id, generated_at DESC);
CREATE INDEX idx_insights_priority ON business_insights (priority, generated_at DESC) WHERE dismissed_at IS NULL;
CREATE INDEX idx_insights_actionable ON business_insights (restaurant_id) WHERE is_actionable = true AND action_taken_at IS NULL;

-- Analytics indexes
CREATE INDEX idx_trends_geography ON vibe_trends (geography_type, geography_value, period_start DESC);
CREATE INDEX idx_trends_growth ON vibe_trends (growth_rate DESC) WHERE growth_rate IS NOT NULL;
CREATE INDEX idx_performance_trends_date ON restaurant_performance_trends (metric_date DESC);
CREATE INDEX idx_performance_trends_restaurant ON restaurant_performance_trends (restaurant_id, metric_date DESC);

-- ============================================
-- STEP 11: Functions and Triggers
-- ============================================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update trigger to all relevant tables
CREATE TRIGGER update_vibe_definitions_updated BEFORE UPDATE ON vibe_definitions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_restaurant_vibe_profiles_updated BEFORE UPDATE ON restaurant_vibe_profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_users_updated BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_taste_profiles_updated BEFORE UPDATE ON user_taste_profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_business_accounts_updated BEFORE UPDATE ON business_accounts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Calculate user profile completeness
CREATE OR REPLACE FUNCTION calculate_profile_completeness(user_id INTEGER)
RETURNS DOUBLE PRECISION AS $$
DECLARE
    completeness DOUBLE PRECISION := 0;
    profile user_taste_profiles%ROWTYPE;
BEGIN
    SELECT * INTO profile FROM user_taste_profiles WHERE user_taste_profiles.user_id = $1;
    
    -- Basic profile info (25%)
    IF jsonb_array_length(profile.preferred_vibes) > 0 THEN
        completeness := completeness + 0.25;
    END IF;
    
    -- Cuisine preferences (25%)
    IF jsonb_array_length(profile.cuisine_preferences) > 0 THEN
        completeness := completeness + 0.25;
    END IF;
    
    -- Has interactions (25%)
    IF EXISTS (SELECT 1 FROM user_interactions WHERE user_interactions.user_id = $1 LIMIT 5) THEN
        completeness := completeness + 0.25;
    END IF;
    
    -- Has bookmarks (25%)
    IF EXISTS (SELECT 1 FROM user_bookmarks WHERE user_bookmarks.user_id = $1 LIMIT 1) THEN
        completeness := completeness + 0.25;
    END IF;
    
    RETURN completeness;
END;
$$ LANGUAGE plpgsql;

-- Get restaurant vibe summary
CREATE OR REPLACE FUNCTION get_restaurant_vibe_summary(restaurant_id INTEGER)
RETURNS JSONB AS $$
DECLARE
    result JSONB;
BEGIN
    SELECT jsonb_build_object(
        'primary_vibes', 
        COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'name', vd.vibe_name,
                    'score', rvp.score,
                    'confidence', rvp.confidence
                ) ORDER BY rvp.score DESC
            ) FILTER (WHERE rvp.is_primary = true),
            '[]'::jsonb
        ),
        'secondary_vibes',
        COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'name', vd.vibe_name,
                    'score', rvp.score,
                    'confidence', rvp.confidence
                ) ORDER BY rvp.score DESC
            ) FILTER (WHERE rvp.is_primary = false),
            '[]'::jsonb
        ),
        'avg_confidence',
        AVG(rvp.confidence)
    ) INTO result
    FROM restaurant_vibe_profiles rvp
    JOIN vibe_definitions vd ON rvp.vibe_id = vd.id
    WHERE rvp.restaurant_id = $1
    GROUP BY rvp.restaurant_id;
    
    RETURN COALESCE(result, '{}'::jsonb);
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- STEP 12: Initial Data
-- ============================================

-- Insert core vibe definitions
INSERT INTO vibe_definitions (vibe_name, vibe_slug, category, description, display_order) VALUES
-- Atmosphere vibes
('Casual', 'casual', 'atmosphere', 'Relaxed and informal dining', 10),
('Upscale', 'upscale', 'atmosphere', 'Refined and elegant atmosphere', 20),
('Intimate', 'intimate', 'atmosphere', 'Cozy and personal setting', 30),
('Trendy', 'trendy', 'atmosphere', 'Modern and fashionable', 40),
('Classic', 'classic', 'atmosphere', 'Traditional and timeless', 50),
('Romantic', 'romantic', 'atmosphere', 'Perfect for couples and dates', 60),
('Family-Friendly', 'family-friendly', 'atmosphere', 'Welcoming to families with children', 70),
-- Energy vibes
('Lively', 'lively', 'energy', 'High energy and bustling', 100),
('Vibrant', 'vibrant', 'energy', 'Dynamic and exciting atmosphere', 110),
('Calm', 'calm', 'energy', 'Peaceful and quiet', 120),
('Bustling', 'bustling', 'energy', 'Busy and energetic', 130),
('Relaxed', 'relaxed', 'energy', 'Laid-back and easy-going', 140),
-- Occasion vibes
('Date Night', 'date-night', 'occasion', 'Ideal for romantic occasions', 200),
('Business', 'business', 'occasion', 'Suitable for professional meetings', 210),
('Celebration', 'celebration', 'occasion', 'Great for special occasions', 220),
('Quick Bite', 'quick-bite', 'occasion', 'Fast and convenient dining', 230),
('Special Occasion', 'special-occasion', 'occasion', 'Perfect for memorable events', 240),
-- Style vibes
('Modern', 'modern', 'style', 'Contemporary design and approach', 300),
('Traditional', 'traditional', 'style', 'Classic culinary traditions', 310),
('Innovative', 'innovative', 'style', 'Creative and experimental', 320),
('Authentic', 'authentic', 'style', 'True to cultural origins', 330),
('Fusion', 'fusion', 'style', 'Blending multiple cuisines', 340);

-- Create some vibe relationships
INSERT INTO vibe_relationships (vibe_a_id, vibe_b_id, relationship_type, strength) 
SELECT 
    v1.id, v2.id, 'opposite', 0.9
FROM vibe_definitions v1, vibe_definitions v2
WHERE (v1.vibe_slug = 'casual' AND v2.vibe_slug = 'upscale')
   OR (v1.vibe_slug = 'lively' AND v2.vibe_slug = 'calm')
   OR (v1.vibe_slug = 'modern' AND v2.vibe_slug = 'traditional');

-- ============================================
-- STEP 13: Views for Easy Access
-- ============================================

-- Restaurant vibe summary view
CREATE OR REPLACE VIEW v_restaurant_vibes AS
SELECT 
    r.id AS restaurant_id,
    r.name AS restaurant_name,
    r.cuisine_type,
    r.price_range,
    get_restaurant_vibe_summary(r.id) AS vibe_summary,
    r.taste_graph_score,
    r.vibe_profile_extracted_at
FROM restaurants r;

-- User taste summary view
CREATE OR REPLACE VIEW v_user_taste_summary AS
SELECT 
    u.id AS user_id,
    u.email,
    utp.preferred_vibes,
    utp.cuisine_preferences,
    utp.price_sensitivity,
    utp.adventure_score,
    calculate_profile_completeness(u.id) AS profile_completeness,
    COUNT(DISTINCT ui.restaurant_id) AS restaurants_interacted,
    COUNT(DISTINCT ub.restaurant_id) AS restaurants_bookmarked
FROM users u
LEFT JOIN user_taste_profiles utp ON u.id = utp.user_id
LEFT JOIN user_interactions ui ON u.id = ui.user_id
LEFT JOIN user_bookmarks ub ON u.id = ub.user_id
GROUP BY u.id, u.email, utp.preferred_vibes, utp.cuisine_preferences, 
         utp.price_sensitivity, utp.adventure_score;

-- Business insights summary
CREATE OR REPLACE VIEW v_business_insights_summary AS
SELECT 
    r.id AS restaurant_id,
    r.name AS restaurant_name,
    COUNT(bi.id) AS total_insights,
    COUNT(bi.id) FILTER (WHERE bi.priority = 'critical') AS critical_insights,
    COUNT(bi.id) FILTER (WHERE bi.priority = 'high') AS high_priority_insights,
    COUNT(bi.id) FILTER (WHERE bi.is_actionable AND bi.action_taken_at IS NULL) AS pending_actions,
    MAX(bi.generated_at) AS latest_insight_date
FROM restaurants r
LEFT JOIN business_insights bi ON r.id = bi.restaurant_id
GROUP BY r.id, r.name;

-- ============================================
-- STEP 14: Permissions
-- ============================================

-- Create read-only role for analytics
CREATE ROLE taste_graph_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO taste_graph_readonly;

-- Create application role with full access
CREATE ROLE taste_graph_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO taste_graph_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO taste_graph_app;

COMMIT;

-- ============================================
-- Migration Notes
-- ============================================
/*
1. This migration preserves the restaurants table completely
2. Drops and rebuilds: business_vibe_matches, vibe_match_cache, restaurant_trends
3. Creates a complete user system for B2C features
4. Implements proper vibe hierarchy and relationships
5. Adds comprehensive business intelligence tables
6. Includes performance optimization indexes
7. Sets up initial vibe definitions

To rollback:
- Run the rollback script in 002_taste_graph_rollback.sql
*/