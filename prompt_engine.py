"""
Prompt Engine - Manages prompt templates with version tracking
"""

import yaml
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd


class PromptEngine:
    """Manages prompt templates with version tracking"""
    
    def __init__(self, version: str = "1.0"):
        self.version = version
        self.template_dir = Path(f"config/prompts/v{version}")
        self.template = self._load_template()
        
    def _load_template(self) -> str:
        """Load prompt template for current version"""
        template_file = self.template_dir / "top10_prompt.txt"
        
        if not template_file.exists():
            # Fall back to latest version
            print(f"⚠️  Version {self.version} not found, using latest")
            latest = self._get_latest_version()
            if latest:
                self.version = latest
                self.template_dir = Path(f"config/prompts/v{latest}")
                template_file = self.template_dir / "top10_prompt.txt"
            else:
                # Use default template
                return self._get_default_template()
        
        with open(template_file, 'r') as f:
            return f.read()
    
    def _get_latest_version(self) -> Optional[str]:
        """Find the latest prompt version"""
        prompt_dir = Path("config/prompts")
        
        if not prompt_dir.exists():
            return None
            
        versions = []
        for d in prompt_dir.iterdir():
            if d.is_dir() and d.name.startswith('v'):
                version = d.name.replace('v', '')
                try:
                    # Validate version format
                    float(version)
                    versions.append(version)
                except ValueError:
                    continue
        
        if not versions:
            return None
            
        return sorted(versions, key=lambda x: float(x))[-1]
    
    def _get_default_template(self) -> str:
        """Get default prompt template"""
        return """You are a local food expert creating a Top 10 list of {vibe} restaurants in {city}.

City: {city}
List Type: Top 10 {vibe} Restaurants
Date: {date}

IMPORTANT INSTRUCTIONS:
1. Select EXACTLY 10 restaurants from the provided list
2. Rank them 1-10 based on how well they match the "{vibe}" vibe
3. Each entry must include:
   - Restaurant name (exactly as provided)
   - Why it's perfect for {vibe} (2-3 sentences)
   - Must-try dish or drink
   - Full address (exactly as provided)
   - Price range (use exactly: $, $$, $$$, or $$$$)

VIBE DESCRIPTION:
{vibe_description}

AVAILABLE RESTAURANTS:
{restaurants_list}

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

**1. Restaurant Name**
- Why: [2-3 sentences about why it's perfect for {vibe}]
- Must-try: [Specific dish or drink]
- Address: [Full address]
- Price: [$ to $$$$]

**2. Restaurant Name**
[Continue same format for all 10]

Remember: Focus on what makes each restaurant perfect for "{vibe}" specifically."""
    
    def create_prompt(self, restaurants_df: pd.DataFrame, city: str, vibe: str) -> Dict:
        """Create a versioned prompt with metadata"""
        
        # Load vibe description
        vibes = self._load_vibes()
        vibe_info = vibes.get(vibe, {})
        
        # Format restaurant data
        restaurants_text = self._format_restaurants(restaurants_df)
        
        # Format city and vibe names
        city_name = city.replace('-', ' ').title()
        vibe_name = vibe.replace('-', ' ')
        
        # Fill template
        prompt = self.template.format(
            city=city_name,
            vibe=vibe_name,
            vibe_description=vibe_info.get('description', f'Restaurants perfect for {vibe_name}'),
            restaurants_list=restaurants_text,
            date=datetime.now().strftime('%B %Y')
        )
        
        return {
            'prompt': prompt,
            'version': self.version,
            'template_name': 'top10_prompt.txt',
            'restaurant_count': len(restaurants_df),
            'city': city,
            'vibe': vibe,
            'generated_at': datetime.now().isoformat()
        }
    
    def _format_restaurants(self, df: pd.DataFrame) -> str:
        """Format restaurant data for prompt"""
        restaurants = []
        
        for idx, row in df.iterrows():
            # Build restaurant entry
            lines = [
                f"Name: {row['name']}",
                f"Rating: {row['yelp_rating']:.1f} stars",
            ]
            
            # Add review count if available
            if 'yelp_review_count' in row and pd.notna(row['yelp_review_count']):
                lines.append(f"Reviews: {int(row['yelp_review_count'])} reviews")
            
            # Add price range
            lines.append(f"Price: {row.get('price_range', '$')}")
            
            # Add cuisine type if available
            if 'cuisine_type' in row and pd.notna(row['cuisine_type']):
                lines.append(f"Cuisine: {row['cuisine_type']}")
            
            # Add address
            lines.append(f"Address: {row['address']}")
            
            # Add neighborhood if available
            if 'neighborhood' in row and pd.notna(row['neighborhood']):
                lines.append(f"Neighborhood: {row['neighborhood']}")
            
            # Parse vibe attributes if available
            if 'vibe_attributes' in row and pd.notna(row['vibe_attributes']):
                try:
                    if isinstance(row['vibe_attributes'], str):
                        vibe_attrs = json.loads(row['vibe_attributes'])
                    else:
                        vibe_attrs = row['vibe_attributes']
                    
                    positive_vibes = [k for k, v in vibe_attrs.items() if v]
                    if positive_vibes:
                        lines.append(f"Atmosphere: {', '.join(positive_vibes)}")
                except:
                    pass
            
            # Add description if available
            if 'description' in row and pd.notna(row['description']):
                desc = str(row['description'])[:200]
                if len(desc) == 200:
                    desc += "..."
                lines.append(f"About: {desc}")
            
            # Add review excerpt if available
            if 'review_excerpts' in row and pd.notna(row['review_excerpts']):
                try:
                    if isinstance(row['review_excerpts'], str):
                        reviews = json.loads(row['review_excerpts'])
                    else:
                        reviews = row['review_excerpts']
                    
                    if reviews and len(reviews) > 0:
                        review_text = reviews[0].get('text', '')[:150]
                        if review_text:
                            lines.append(f'Recent Review: "{review_text}..."')
                except:
                    pass
            
            # Join lines and add to list
            restaurants.append('\n'.join(lines))
        
        return '\n\n'.join(restaurants)
    
    def _load_vibes(self) -> Dict:
        """Load vibe definitions"""
        vibe_file = Path('config/vibes.yaml')
        
        if not vibe_file.exists():
            return {}
            
        with open(vibe_file, 'r') as f:
            data = yaml.safe_load(f)
            return data.get('vibes', {}) if data else {}
    
    def get_version_info(self) -> Dict:
        """Get information about this prompt version"""
        
        changelog_file = self.template_dir / "changelog.txt"
        changelog = ""
        
        if changelog_file.exists():
            with open(changelog_file, 'r') as f:
                changelog = f.read()
        
        # Get template stats
        template_file = self.template_dir / "top10_prompt.txt"
        created_at = datetime.now()
        
        if template_file.exists():
            created_at = datetime.fromtimestamp(template_file.stat().st_mtime)
        
        return {
            'version': self.version,
            'template_path': str(self.template_dir),
            'changelog': changelog,
            'created_at': created_at.isoformat(),
            'template_size': len(self.template)
        }
    
    def list_versions(self) -> List[Dict]:
        """List all available prompt versions"""
        prompt_dir = Path("config/prompts")
        versions = []
        
        if not prompt_dir.exists():
            return versions
        
        for version_dir in sorted(prompt_dir.iterdir()):
            if version_dir.is_dir() and version_dir.name.startswith('v'):
                version = version_dir.name.replace('v', '')
                
                # Get version info
                template_file = version_dir / "top10_prompt.txt"
                if template_file.exists():
                    created = datetime.fromtimestamp(template_file.stat().st_mtime)
                    
                    # Load changelog
                    changelog = ""
                    changelog_file = version_dir / "changelog.txt"
                    if changelog_file.exists():
                        with open(changelog_file, 'r') as f:
                            changelog = f.read().split('\n')[0]  # First line
                    
                    versions.append({
                        'version': version,
                        'created': created.strftime('%Y-%m-%d'),
                        'changelog': changelog,
                        'path': str(version_dir)
                    })
        
        return versions


# Version management helpers
def create_new_prompt_version(base_version: str, changes: str) -> str:
    """Create a new prompt version based on existing one"""
    
    # Parse version
    try:
        major, minor = base_version.split('.')
        new_version = f"{major}.{int(minor) + 1}"
    except:
        # Default to incrementing from 1.0
        new_version = "1.1"
    
    # Create directories
    old_dir = Path(f"config/prompts/v{base_version}")
    new_dir = Path(f"config/prompts/v{new_version}")
    new_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy template if exists
    old_template = old_dir / "top10_prompt.txt"
    new_template = new_dir / "top10_prompt.txt"
    
    if old_template.exists():
        import shutil
        shutil.copy(old_template, new_template)
    else:
        # Create default template
        engine = PromptEngine()
        with open(new_template, 'w') as f:
            f.write(engine._get_default_template())
    
    # Create changelog
    with open(new_dir / "changelog.txt", 'w') as f:
        f.write(f"Version {new_version} - {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(f"Based on: v{base_version}\n\n")
        f.write(f"Changes:\n{changes}\n")
    
    print(f"✅ Created new prompt version: {new_version}")
    print(f"📁 Location: {new_dir}")
    print(f"Edit the template at: {new_template}")
    
    return new_version


def compare_versions(version1: str, version2: str):
    """Compare two prompt versions"""
    
    v1_file = Path(f"config/prompts/v{version1}/top10_prompt.txt")
    v2_file = Path(f"config/prompts/v{version2}/top10_prompt.txt")
    
    if not v1_file.exists():
        print(f"❌ Version {version1} not found")
        return
        
    if not v2_file.exists():
        print(f"❌ Version {version2} not found")
        return
    
    with open(v1_file, 'r') as f:
        v1_content = f.read()
        
    with open(v2_file, 'r') as f:
        v2_content = f.read()
    
    if v1_content == v2_content:
        print(f"✅ Versions {version1} and {version2} are identical")
    else:
        print(f"❌ Versions {version1} and {version2} differ")
        
        # Show basic diff stats
        v1_lines = v1_content.split('\n')
        v2_lines = v2_content.split('\n')
        
        print(f"\nVersion {version1}: {len(v1_lines)} lines, {len(v1_content)} chars")
        print(f"Version {version2}: {len(v2_lines)} lines, {len(v2_content)} chars")


if __name__ == "__main__":
    # Test prompt engine
    engine = PromptEngine()
    
    print(f"Current version: {engine.version}")
    print(f"Template loaded: {len(engine.template)} characters")
    
    # List available versions
    versions = engine.list_versions()
    if versions:
        print("\nAvailable versions:")
        for v in versions:
            print(f"  v{v['version']} - {v['created']} - {v['changelog']}")
    
    # Test creating a new version
    if not Path("config/prompts/v1.0").exists():
        create_new_prompt_version("1.0", "Initial version")