-- Verification script to check if migration was successful
-- Run this after applying 002_taste_graph_complete_schema.sql

-- Check all new tables were created
SELECT 
    'Tables Created' as check_type,
    COUNT(*) as count,
    CASE 
        WHEN COUNT(*) = 24 THEN 'PASS ✓' 
        ELSE 'FAIL ✗ - Expected 24 tables' 
    END as status
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
    'vibe_definitions',
    'restaurant_vibe_profiles',
    'vibe_relationships',
    'users',
    'user_taste_profiles',
    'user_interactions',
    'user_bookmarks',
    'restaurant_relationships',
    'restaurant_clusters',
    'restaurant_cluster_members',
    'recommendation_sessions',
    'recommendation_cache',
    'business_accounts',
    'business_insights',
    'competitive_sets',
    'vibe_trends',
    'taste_graph_metrics',
    'restaurant_performance_trends'
);

-- Check restaurants table was extended
SELECT 
    'Restaurants Extended' as check_type,
    COUNT(*) as count,
    CASE 
        WHEN COUNT(*) = 5 THEN 'PASS ✓' 
        ELSE 'FAIL ✗ - Expected 5 new columns' 
    END as status
FROM information_schema.columns
WHERE table_name = 'restaurants'
AND column_name IN (
    'vibe_profile_extracted_at',
    'vibe_extraction_version',
    'taste_graph_score',
    'embedding_vector',
    'taste_graph_metadata'
);

-- Check vibe definitions were loaded
SELECT 
    'Vibe Definitions' as check_type,
    COUNT(*) as count,
    CASE 
        WHEN COUNT(*) >= 20 THEN 'PASS ✓' 
        ELSE 'FAIL ✗ - Expected at least 20 vibes' 
    END as status
FROM vibe_definitions;

-- Check indexes were created
SELECT 
    'Indexes Created' as check_type,
    COUNT(*) as count,
    CASE 
        WHEN COUNT(*) >= 30 THEN 'PASS ✓' 
        ELSE 'FAIL ✗ - Expected at least 30 indexes' 
    END as status
FROM pg_indexes
WHERE schemaname = 'public'
AND indexname LIKE 'idx_%';

-- Check views were created
SELECT 
    'Views Created' as check_type,
    COUNT(*) as count,
    CASE 
        WHEN COUNT(*) = 3 THEN 'PASS ✓' 
        ELSE 'FAIL ✗ - Expected 3 views' 
    END as status
FROM information_schema.views
WHERE table_schema = 'public'
AND table_name IN (
    'v_restaurant_vibes',
    'v_user_taste_summary',
    'v_business_insights_summary'
);

-- Check functions were created
SELECT 
    'Functions Created' as check_type,
    COUNT(*) as count,
    CASE 
        WHEN COUNT(*) = 3 THEN 'PASS ✓' 
        ELSE 'FAIL ✗ - Expected 3 functions' 
    END as status
FROM information_schema.routines
WHERE routine_schema = 'public'
AND routine_name IN (
    'update_updated_at_column',
    'calculate_profile_completeness',
    'get_restaurant_vibe_summary'
);

-- Summary of restaurant data preservation
SELECT 
    'Restaurants Preserved' as check_type,
    COUNT(*) as count,
    CASE 
        WHEN COUNT(*) = 5760 THEN 'PASS ✓ - All restaurants preserved' 
        ELSE 'FAIL ✗ - Restaurant count changed!' 
    END as status
FROM restaurants;

-- List any missing expected tables
SELECT 
    'Missing Tables' as check_type,
    string_agg(expected_table, ', ') as missing_tables
FROM (
    VALUES 
        ('vibe_definitions'),
        ('restaurant_vibe_profiles'),
        ('users'),
        ('user_taste_profiles'),
        ('restaurant_relationships'),
        ('business_insights')
) AS expected(expected_table)
WHERE NOT EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = expected_table
);