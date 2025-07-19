# Taste Graph Database Implementation Handoff

**Critical**: This database is the foundation of the entire ZipPicks business. Every decision here impacts scalability, performance, and business success.

## Current State Analysis

### Existing Database Structure
- **Database**: PostgreSQL (zipbusiness)
- **Core Table**: `restaurants` (5,760 records) - DO NOT MODIFY STRUCTURE
- **ID Pattern**: INTEGER with auto-increment (not UUID)
- **Existing Tables to Drop/Rebuild**:
  - `business_vibe_matches` (empty) - poor structure
  - `vibe_match_cache` (empty) - needs redesign  
  - `restaurant_trends` (empty) - needs enhancement

### Critical Issues Found
1. **No User System**: Zero user tables exist - blocking all B2C features
2. **Poor Vibe Structure**: Current `business_vibe_matches` uses strings (zpid/vibe_slug) instead of proper IDs
3. **No Relationship Tracking**: Missing restaurant similarity/recommendation infrastructure
4. **No Business Intelligence**: No tables for insights, analytics, or B2B features

## Implementation Strategy

### Phase 1: Foundation (MUST DO FIRST)

#### 1.1 Apply Core Schema Migration
```sql
-- Run the complete migration from:
-- /database/migrations/002_taste_graph_complete_schema.sql

-- This will:
-- 1. Drop and rebuild 3 existing tables
-- 2. Add 5 columns to restaurants table
-- 3. Create 18 new tables
-- 4. Set up proper indexes and constraints
-- 5. Load initial vibe definitions
```

#### 1.2 Verify Migration Success
```sql
-- Run verification script from:
-- /database/migrations/verify_migration.sql

-- Must see all "PASS ✓" results before proceeding
```

### Phase 2: Data Migration & Setup

#### 2.1 Migrate Existing Vibe Data
```sql
-- If you have vibe_attributes data in restaurants table:
INSERT INTO restaurant_vibe_profiles (restaurant_id, vibe_id, score, confidence, is_primary, extraction_method)
SELECT 
    r.id,
    vd.id,
    0.8, -- default score
    0.5, -- low confidence for migrated data
    true,
    'legacy_migration'
FROM restaurants r
CROSS JOIN LATERAL jsonb_array_elements_text(r.vibe_attributes) AS vibe_name
JOIN vibe_definitions vd ON vd.vibe_slug = lower(vibe_name)
WHERE r.vibe_attributes IS NOT NULL 
  AND jsonb_array_length(r.vibe_attributes) > 0;
```

#### 2.2 Create Required Extensions
```sql
-- For ML features (optional but recommended):
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- for text similarity
CREATE EXTENSION IF NOT EXISTS earthdistance CASCADE; -- for location queries
```

### Phase 3: Critical Configurations

#### 3.1 Database Performance Settings
```sql
-- Run these as superuser:
ALTER SYSTEM SET shared_buffers = '2GB';
ALTER SYSTEM SET effective_cache_size = '6GB';
ALTER SYSTEM SET maintenance_work_mem = '512MB';
ALTER SYSTEM SET work_mem = '50MB';
ALTER SYSTEM SET max_connections = 200;

-- Then reload:
SELECT pg_reload_conf();
```

#### 3.2 Create Application User
```sql
-- Create dedicated user for application
CREATE USER taste_graph_app WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT CONNECT ON DATABASE zipbusiness TO taste_graph_app;
GRANT USAGE ON SCHEMA public TO taste_graph_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO taste_graph_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO taste_graph_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO taste_graph_app;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO taste_graph_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO taste_graph_app;
```

## Critical Tables Overview

### 1. Core Vibe System
- **vibe_definitions**: Master list of all vibes with hierarchy
- **restaurant_vibe_profiles**: Restaurant-vibe mappings with confidence scores
- **vibe_relationships**: How vibes relate to each other

### 2. User System (NEW)
- **users**: User accounts with location, preferences
- **user_taste_profiles**: Learned preferences and taste vectors
- **user_interactions**: Every click, view, rating for ML training
- **user_bookmarks**: Saved restaurants and lists

### 3. Intelligence Layer
- **restaurant_relationships**: Similarity scores between restaurants
- **restaurant_clusters**: Grouped restaurants for discovery
- **business_insights**: AI-generated insights for restaurants
- **restaurant_performance_trends**: Time-series performance data

### 4. Recommendation Engine
- **recommendation_sessions**: Track recommendation performance
- **recommendation_cache**: Speed up frequent queries

## Data Flow Architecture

```
User Action → user_interactions → ML Pipeline → user_taste_profiles
                                       ↓
Restaurant Data → restaurant_vibe_profiles → Similarity Engine
                                       ↓
                            recommendation_cache → API Response
```

## Performance Considerations

### Critical Indexes (Already in Migration)
1. **User Queries**: `user_id + created_at` for interaction history
2. **Restaurant Lookups**: `restaurant_id + is_primary` for vibe profiles  
3. **Similarity Queries**: `restaurant_a_id + similarity_overall DESC`
4. **Location Queries**: GiST index on lat/lng for geographic searches

### Query Performance Targets
- User profile lookup: < 10ms
- Restaurant vibe summary: < 20ms
- Recommendation generation: < 200ms
- Similarity search: < 50ms

## Monitoring & Maintenance

### Daily Checks
```sql
-- Check for stale vibe profiles
SELECT COUNT(*) 
FROM restaurants 
WHERE vibe_profile_extracted_at < NOW() - INTERVAL '30 days'
   OR vibe_profile_extracted_at IS NULL;

-- Monitor recommendation cache hit rate
SELECT 
    SUM(hit_count) as total_hits,
    COUNT(*) as total_entries,
    AVG(hit_count) as avg_hits_per_entry
FROM recommendation_cache
WHERE created_at > NOW() - INTERVAL '24 hours';
```

### Weekly Maintenance
```sql
-- Update restaurant performance trends
INSERT INTO restaurant_performance_trends (restaurant_id, metric_date, ...)
SELECT ... -- aggregated metrics

-- Clean expired cache entries
DELETE FROM recommendation_cache WHERE expires_at < NOW();

-- Vacuum analyze critical tables
VACUUM ANALYZE restaurant_vibe_profiles;
VACUUM ANALYZE user_interactions;
```

## Integration Points

### 1. With Existing Systems
- **WordPress API**: Read vibe profiles via REST endpoints
- **Master Critic Plugin**: Enhanced filtering with taste graph scores
- **Analytics Pipeline**: Feed user interactions for ML training

### 2. New API Endpoints Needed
```
POST /api/v1/taste-graph/extract-vibes
GET  /api/v1/taste-graph/restaurants/{id}/vibes
GET  /api/v1/taste-graph/restaurants/{id}/similar
POST /api/v1/taste-graph/users/{id}/interactions
GET  /api/v1/taste-graph/users/{id}/recommendations
```

## Rollback Plan

If anything goes wrong:
```sql
-- Execute rollback script:
-- /database/migrations/002_taste_graph_rollback.sql

-- Then restore from backup:
pg_restore -d zipbusiness backup_before_migration.sql
```

## Next Steps After Database Setup

1. **Immediate** (Day 1):
   - Run initial vibe extraction for top 100 restaurants
   - Create test users for development
   - Verify all indexes are being used

2. **Week 1**:
   - Build API endpoints for vibe data
   - Implement recommendation caching
   - Start collecting user interactions

3. **Month 1**:
   - Extract vibes for all 5,760 restaurants
   - Launch B2B dashboard with insights
   - Begin A/B testing recommendation algorithms

## Success Metrics

- **Database Health**: All queries under 200ms
- **Data Quality**: 90%+ restaurants with vibe profiles
- **Cache Performance**: 80%+ cache hit rate
- **User Engagement**: 10%+ users with complete taste profiles

## Critical Warnings

1. **Never modify restaurants table structure** - only add columns
2. **Always use transactions** for multi-table updates
3. **Monitor disk space** - user_interactions will grow rapidly
4. **Backup before any schema changes**
5. **Test migrations on staging first**

## Contact for Issues

- Database schema questions: Review this document
- Migration issues: Check verify_migration.sql output
- Performance problems: Review slow query log
- Data integrity: Check constraint violations in logs

This database is the foundation of a $50M+ ARR business. Build it right the first time.