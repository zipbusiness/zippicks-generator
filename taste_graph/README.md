# ZipPicks Taste Graph System

The Taste Graph is the foundational intelligence layer that powers both B2B (ZipPicks Pro) and B2C (Zipper) personalization features. It transforms subjective dining preferences into quantifiable, actionable insights at scale.

## System Overview

### Core Components

1. **Vibe Extractor** (`core/vibe_extractor.py`)
   - Claude-powered analysis of restaurant vibes from reviews and descriptions
   - Extracts primary/secondary vibes with confidence scores
   - Quantifies energy and formality levels

2. **Taste Engine** (`core/taste_engine.py`)
   - Manages user taste profiles and preferences
   - Calculates restaurant-user match scores
   - Learns from user interactions over time

3. **Relationship Mapper** (`core/relationship_mapper.py`)
   - Maps similarities between restaurants
   - Identifies complementary and alternative options
   - Creates restaurant clusters based on vibe profiles

4. **Database Layer** (`data_pipeline/database.py`)
   - PostgreSQL connection management
   - Handles all taste graph data persistence
   - Provides optimized queries for recommendations

## Setup

### Prerequisites

- PostgreSQL 16+
- Python 3.8+
- Anthropic API key for Claude
- Redis/Valkey for caching (optional)

### Installation

1. Install dependencies:
```bash
pip install psycopg2-binary anthropic pyyaml numpy scikit-learn tenacity
```

2. Set environment variables:
```bash
export ANTHROPIC_API_KEY=your_api_key
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=zipbusiness
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your_password
```

3. Run database migrations:
```bash
psql -U postgres -d zipbusiness -f database/migrations/001_taste_graph_schema.sql
```

## Usage

### Extract Restaurant Vibes

```python
from taste_graph.core.vibe_extractor import VibeExtractor
from taste_graph.data_pipeline.database import DatabaseManager

# Initialize components
db = DatabaseManager()
extractor = VibeExtractor(api_key="your_anthropic_key")

# Get restaurant data
restaurant = {
    "id": "123",
    "name": "Bella Vista",
    "cuisine": "Italian",
    "description": "Romantic rooftop dining with city views",
    "reviews": ["Amazing atmosphere!", "Perfect for dates"]
}

# Extract vibes
vibe_profile = extractor.extract_vibes(restaurant)

# Save to database
db.save_vibe_profile(restaurant["id"], vibe_profile.__dict__)
```

### Create User Taste Profile

```python
from taste_graph.core.taste_engine import TasteEngine

engine = TasteEngine()

# Create profile from user data
user_data = {
    "user_id": "user_456",
    "preferred_vibes": {"romantic": 0.8, "upscale": 0.7},
    "cuisine_preferences": {"italian": 0.9, "french": 0.8},
    "social_style": "couples"
}

profile = engine.create_taste_profile(user_data)
```

### Generate Recommendations

```python
# Get matching restaurants
context = {
    "time": "dinner",
    "occasion": "date",
    "weather": "clear"
}

match = engine.calculate_match(profile, restaurant_with_vibes, context)
print(f"Match score: {match.match_score:.2f}")
print(f"Why: {match.explanation}")
```

### Map Restaurant Relationships

```python
from taste_graph.core.relationship_mapper import RelationshipMapper

mapper = RelationshipMapper()

# Map relationships for all restaurants
relationships = mapper.map_restaurant_relationships(restaurants)

# Find similar restaurants
similar = mapper.find_similar_restaurants("restaurant_id", count=5)
```

## Database Schema

The system extends your existing restaurant database with:

- **Enhanced restaurants table**: Adds vibe profiles, energy/formality levels
- **business_vibe_matches**: Individual vibe assignments with confidence
- **user_taste_profiles**: User preference data
- **user_interactions**: Learning from user behavior
- **restaurant_relationships**: Similarity mappings
- **taste_graph_insights**: B2B analytics and recommendations

## API Integration

The taste graph integrates with your existing systems:

1. **WordPress (zippicks-final)**: Consumes data via REST API
2. **ZipBusiness API**: Provides taste graph endpoints
3. **Master Critic Plugin**: Enhanced with vibe-based filtering

## Testing

Run the test suite:

```bash
python -m pytest tests/test_vibe_extraction.py -v
```

## Performance Considerations

- Vibe extraction: ~2 seconds per restaurant (Claude API)
- Recommendation generation: <200ms (cached)
- Relationship mapping: Batch process, runs nightly
- Database queries: Optimized with proper indexes

## Configuration

Edit `config/taste_graph_config.yaml` to customize:

- API settings and rate limits
- Confidence thresholds
- Cache TTLs
- Recommendation weights
- Analytics parameters

## Monitoring

The system provides metrics for:

- Vibe extraction accuracy
- Recommendation relevance
- User engagement rates
- API performance
- Cache hit rates

## Future Enhancements

- Photo-based vibe analysis
- Menu text mining
- Real-time trend detection
- Social graph integration
- Multi-language support