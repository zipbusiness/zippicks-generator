# ZipPicks Generator

AI-powered Top 10 restaurant list generator with full SEO optimization and WordPress integration.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Add your restaurant data
cp your-data.csv data/restaurants.csv

# Configure WordPress
edit config/wp_config.yaml

# Generate your first list
python generate.py --mode daily
```

## 📋 Features

- **Versioned Prompts**: Track and optimize what works
- **Response Validation**: Ensure quality and consistency
- **SEO Optimized**: Full schema.org markup
- **WordPress Integration**: One-click publishing
- **Progress Tracking**: Know what's been generated

## 🎯 Daily Workflow

1. **Run daily batch**
   ```bash
   python generate.py --mode daily --prompt-version 1.0
   ```

2. **Copy prompts to Claude**
   - System prepares formatted prompts
   - Paste into Claude
   - Get responses back

3. **Automatic validation**
   - Responses are validated for structure
   - Failed validations saved for review

4. **Publish to WordPress**
   ```bash
   python generate.py --publish-all
   ```

## 📁 Project Structure

```
/zippicks-generator/
├── generate.py          # Main CLI
├── data_manager.py      # Restaurant data handling
├── prompt_engine.py     # Versioned prompt management
├── response_validator.py # Response validation
├── publisher.py         # WordPress publishing
├── schema_builder.py    # SEO schema generation
├── monitor.py          # Progress tracking
│
├── /config/
│   ├── cities.yaml     # City configurations
│   ├── vibes.yaml      # Vibe definitions
│   ├── wp_config.yaml  # WordPress settings
│   └── prompts/        # Versioned prompts
│
├── /data/
│   └── restaurants.csv # Your restaurant data
│
└── /output/
    ├── /drafts/        # Raw responses
    ├── /validated/     # Validated content
    └── /published/     # Published records
```

## 🔧 Commands

### Generation
```bash
# Generate specific city/vibe
python generate.py --mode single --city san-francisco --vibe date-night

# Run daily batch (5 lists)
python generate.py --mode daily --batch-size 5

# Use specific prompt version
python generate.py --mode daily --prompt-version 1.1
```

### Management
```bash
# Check generation status
python generate.py --status

# Validate pending drafts
python generate.py --validate-pending

# Publish all validated
python generate.py --publish-all
```

## 📊 Restaurant Data Format

Your `data/restaurants.csv` should include:

```csv
name,address,city,yelp_rating,price_range,cuisine_type
"Restaurant Name","123 Main St","San Francisco",4.5,"$$","Italian"
```

Required columns:
- `name`: Restaurant name
- `address`: Full address
- `city`: City name
- `yelp_rating`: Rating (numeric)

Optional columns:
- `price_range`: $, $$, $$$, $$$$
- `cuisine_type`: Cuisine category
- `neighborhood`: Area within city
- `vibe_attributes`: JSON of boolean attributes

## 🌐 WordPress Setup

1. **Install WordPress REST API** (included by default in WP 5.0+)

2. **Create Application Password**
   - Go to Users → Your Profile
   - Scroll to "Application Passwords"
   - Create new password for ZipPicks

3. **Update config/wp_config.yaml**
   ```yaml
   site_url: "https://your-site.com"
   api_key: "your-application-password"
   ```

4. **Create Categories**
   - Create city categories (San Francisco, New York, etc.)
   - Create vibe categories (Date Night, Family Friendly, etc.)
   - Update category IDs in config

## 📈 Scaling Tips

### Week 1: Manual Excellence
- Generate 5-10 lists daily
- Track which prompts work best
- Build quality validation data

### Week 2: Optimization
- A/B test prompt versions
- Refine validation rules
- Optimize for specific vibes

### Month 1: Scale
- Increase daily batch size
- Add more cities
- Monitor SEO performance

### Month 2: Automation
- Add browser automation
- Implement Claude API when available
- Build quality metrics dashboard

## 🔍 Monitoring Progress

```bash
# View detailed status
python generate.py --status

# Export progress report
python -c "from monitor import GenerationMonitor; GenerationMonitor().export_to_csv()"

# Check specific city
python -c "from monitor import GenerationMonitor; m = GenerationMonitor(); print(m.get_city_stats('san-francisco'))"
```

## 🎨 Creating New Prompt Versions

```python
from prompt_engine import create_new_prompt_version

# Create version 1.1 based on 1.0
create_new_prompt_version("1.0", "Added emphasis on local favorites")

# Edit the new template
edit config/prompts/v1.1/top10_prompt.txt
```

## 🐛 Troubleshooting

### Validation Failures
- Check response format matches expected pattern
- Ensure all 10 restaurants are included
- Verify price ranges are valid ($, $$, $$$, $$$$)

### WordPress Publishing
- Verify API credentials
- Check category IDs exist
- Ensure proper permissions

### Data Issues
- Validate CSV encoding (UTF-8 preferred)
- Check required columns exist
- Ensure ratings are numeric

## 📚 Advanced Usage

### Custom Vibes
Add new vibes in `config/vibes.yaml`:

```yaml
brunch-spots:
  name: "Brunch Spots"
  description: "Perfect weekend brunch destinations"
  filters:
    keywords: ["brunch", "breakfast", "mimosa"]
    price_ranges: ["$$", "$$$"]
```

### Prompt Optimization
Track performance in `output/logs/generation_log.json` to identify:
- Which prompts generate valid responses
- Common validation failures
- Best performing city/vibe combinations

## 🤝 Contributing

1. Test changes locally
2. Validate with sample data
3. Update documentation
4. Submit pull request

## 📄 License

MIT License - See LICENSE file for details