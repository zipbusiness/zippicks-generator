-- Rollback script for Taste Graph Complete Schema
-- Run this if you need to revert the changes

BEGIN;

-- Drop views
DROP VIEW IF EXISTS v_business_insights_summary;
DROP VIEW IF EXISTS v_user_taste_summary;
DROP VIEW IF EXISTS v_restaurant_vibes;

-- Drop functions
DROP FUNCTION IF EXISTS get_restaurant_vibe_summary(INTEGER);
DROP FUNCTION IF EXISTS calculate_profile_completeness(INTEGER);
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Drop roles
DROP ROLE IF EXISTS taste_graph_app;
DROP ROLE IF EXISTS taste_graph_readonly;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS taste_graph_metrics CASCADE;
DROP TABLE IF EXISTS restaurant_performance_trends CASCADE;
DROP TABLE IF EXISTS vibe_trends CASCADE;
DROP TABLE IF EXISTS competitive_sets CASCADE;
DROP TABLE IF EXISTS business_insights CASCADE;
DROP TABLE IF EXISTS business_accounts CASCADE;
DROP TABLE IF EXISTS recommendation_cache CASCADE;
DROP TABLE IF EXISTS recommendation_sessions CASCADE;
DROP TABLE IF EXISTS restaurant_cluster_members CASCADE;
DROP TABLE IF EXISTS restaurant_clusters CASCADE;
DROP TABLE IF EXISTS restaurant_relationships CASCADE;
DROP TABLE IF EXISTS user_bookmarks CASCADE;
DROP TABLE IF EXISTS user_interactions CASCADE;
DROP TABLE IF EXISTS user_taste_profiles CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS vibe_relationships CASCADE;
DROP TABLE IF EXISTS restaurant_vibe_profiles CASCADE;
DROP TABLE IF EXISTS vibe_definitions CASCADE;

-- Remove columns added to restaurants table
ALTER TABLE restaurants 
DROP COLUMN IF EXISTS vibe_profile_extracted_at,
DROP COLUMN IF EXISTS vibe_extraction_version,
DROP COLUMN IF EXISTS taste_graph_score,
DROP COLUMN IF EXISTS embedding_vector,
DROP COLUMN IF EXISTS taste_graph_metadata;

-- Recreate original tables as they were
-- Note: You'll need to restore these from backup or recreate with original schema

COMMIT;