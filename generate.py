#!/usr/bin/env python3
"""
ZipPicks Generator - Main CLI for generating AI-powered Top 10 restaurant lists
"""

import click
import yaml
import json
import os
from datetime import datetime
from pathlib import Path
import sys
from typing import List, Dict

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, will use system environment variables only
    pass

from data_manager import DataManager
from prompt_engine import PromptEngine
from response_validator import ResponseValidator
from publisher import Publisher
from monitor import GenerationMonitor


@click.command()
@click.option('--mode', type=click.Choice(['daily', 'single', 'publish-all', 'status', 'validate-pending']), 
              required=True, help='Operation mode')
@click.option('--city', help='City slug (e.g., new-york)')
@click.option('--vibe', help='Vibe slug (e.g., date-night)')
@click.option('--prompt-version', default='1.0', help='Prompt version to use')
@click.option('--batch-size', default=5, help='Number of lists to generate in daily mode')
def main(mode, city, vibe, prompt_version, batch_size):
    """ZipPicks Generator - AI-powered restaurant list generator"""
    
    if mode == 'daily':
        run_daily_batch(prompt_version, batch_size)
    elif mode == 'single':
        if not city or not vibe:
            click.echo("❌ --city and --vibe required for single mode")
            sys.exit(1)
        generate_single(city, vibe, prompt_version)
    elif mode == 'publish-all':
        publish_validated_drafts()
    elif mode == 'status':
        show_generation_status()
    elif mode == 'validate-pending':
        validate_all_pending()


def run_daily_batch(prompt_version: str, batch_size: int):
    """Run daily generation workflow"""
    
    # Initialize components
    monitor = GenerationMonitor()
    prompt_engine = PromptEngine(version=prompt_version)
    validator = ResponseValidator()
    data_manager = DataManager()
    
    # Get today's targets
    targets = monitor.get_todays_targets(batch_size)
    
    if not targets:
        click.echo("✅ All combinations have been generated!")
        return
    
    click.echo(f"\n📋 Today's Generation Queue: {len(targets)} lists")
    click.echo(f"📝 Using Prompt Version: {prompt_version}\n")
    
    # Process each target
    for idx, (city, vibe) in enumerate(targets, 1):
        click.echo(f"\n{'='*60}")
        click.echo(f"🏙️  {city.upper()} × {vibe.upper()} ({idx}/{len(targets)})")
        click.echo('='*60)
        
        try:
            # Load restaurant data
            restaurants = data_manager.load_city_restaurants(city, vibe)
            
            if restaurants.empty:
                click.echo(f"❌ No restaurants found for {city}")
                continue
                
            click.echo(f"✓ Loaded {len(restaurants)} restaurants")
            
            # Generate prompt
            prompt_data = prompt_engine.create_prompt(restaurants, city, vibe)
            
            # Save prompt with metadata
            prompt_file = save_prompt_with_metadata(city, vibe, prompt_data)
            click.echo(f"✓ Prompt saved: {prompt_file}")
            click.echo(f"  Version: {prompt_data['version']}")
            click.echo(f"  Restaurants: {prompt_data['restaurant_count']}")
            
            # Display prompt
            click.echo("\n" + "="*60)
            click.echo("📋 COPY THIS PROMPT TO CLAUDE:")
            click.echo("="*60)
            click.echo(prompt_data['prompt'])
            click.echo("="*60)
            
            # Wait for response
            click.echo("\n📝 Paste Claude's response below (end with '###' on new line):\n")
            response = get_multiline_input()
            
            # Validate response
            validation_result = validator.validate_response(response, city, vibe)
            
            if validation_result['valid']:
                click.echo("✅ Response validated successfully!")
                
                # Save validated draft
                save_validated_draft(city, vibe, validation_result['parsed_data'], prompt_version)
                
                # Update monitor
                monitor.mark_as_generated(city, vibe)
                
                # Show summary
                click.echo(f"  ✓ Restaurant count: {validation_result['restaurant_count']}")
                click.echo("  ✓ All required fields present")
                click.echo("  ✓ No duplicates found")
            else:
                click.echo("❌ Validation failed:")
                for error in validation_result['errors']:
                    click.echo(f"  - {error}")
                
                # Save failed draft
                save_failed_draft(city, vibe, response, validation_result['errors'])
                
                if click.confirm("Try again with this city/vibe?"):
                    # Decrement idx to retry
                    continue
            
        except Exception as e:
            click.echo(f"❌ Error processing {city}/{vibe}: {str(e)}")
            continue
        
        # Continue prompt
        if idx < len(targets) and not click.confirm("\nContinue with next city/vibe?", default=True):
            break
    
    click.echo("\n🎉 Daily batch complete!")
    click.echo("Run 'python generate.py --publish-all' to push validated drafts to WordPress")


def generate_single(city: str, vibe: str, prompt_version: str):
    """Generate a single city/vibe combination"""
    
    monitor = GenerationMonitor()
    
    # Check if already generated
    if monitor.is_generated(city, vibe):
        if not click.confirm(f"⚠️  {city}/{vibe} already generated. Regenerate?"):
            return
    
    # Run single generation (reuse daily batch logic)
    run_daily_batch(prompt_version, batch_size=1)


def publish_validated_drafts():
    """Publish all validated drafts to WordPress"""
    
    publisher = Publisher()
    validated_dir = Path("output/validated")
    
    if not validated_dir.exists():
        click.echo("❌ No validated drafts found")
        return
    
    # Find all validated files
    drafts = list(validated_dir.glob("**/*.json"))
    
    if not drafts:
        click.echo("❌ No validated drafts found")
        return
    
    click.echo(f"\n📤 Found {len(drafts)} validated drafts")
    
    if not click.confirm("Publish all to WordPress?"):
        return
    
    # Publish each draft
    success_count = 0
    for draft_file in drafts:
        try:
            with open(draft_file, 'r') as f:
                data = json.load(f)
            
            city = data['city']
            vibe = data['vibe']
            
            click.echo(f"\n Publishing {city}/{vibe}...")
            
            # Publish to WordPress
            post_id = publisher.publish_to_wordpress(data)
            
            if post_id:
                click.echo(f"✅ Published! Post ID: {post_id}")
                
                # Move to published
                published_dir = Path(f"output/published/{city}/{vibe}")
                published_dir.mkdir(parents=True, exist_ok=True)
                
                # Save published data
                published_file = published_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                data['wordpress_post_id'] = post_id
                data['published_at'] = datetime.now().isoformat()
                
                with open(published_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                # Remove from validated
                draft_file.unlink()
                
                success_count += 1
            else:
                click.echo(f"❌ Failed to publish {city}/{vibe}")
                
        except Exception as e:
            click.echo(f"❌ Error publishing {draft_file}: {str(e)}")
    
    click.echo(f"\n✅ Published {success_count}/{len(drafts)} drafts successfully!")


def show_generation_status():
    """Show current generation status"""
    
    monitor = GenerationMonitor()
    status = monitor.get_status()
    
    click.echo("\n📊 GENERATION STATUS")
    click.echo("="*50)
    click.echo(f"Total Combinations: {status['total_combinations']}")
    click.echo(f"Generated: {status['generated_count']} ({status['generated_percentage']:.1f}%)")
    click.echo(f"Remaining: {status['remaining_count']}")
    
    # Show breakdown by city
    click.echo("\n📍 By City:")
    for city, stats in status['by_city'].items():
        click.echo(f"  {city}: {stats['generated']}/{stats['total']} ({stats['percentage']:.1f}%)")
    
    # Show recent generations
    if status['recent_generations']:
        click.echo("\n🕐 Recent Generations:")
        for gen in status['recent_generations'][:5]:
            click.echo(f"  {gen['city']}/{gen['vibe']} - {gen['timestamp']}")
    
    # Show next targets
    next_targets = monitor.get_todays_targets(5)
    if next_targets:
        click.echo("\n🎯 Next Targets:")
        for city, vibe in next_targets:
            click.echo(f"  {city}/{vibe}")


def validate_all_pending():
    """Validate all pending drafts"""
    
    validator = ResponseValidator()
    drafts_dir = Path("output/drafts")
    
    if not drafts_dir.exists():
        click.echo("❌ No drafts found")
        return
    
    # Find all draft files
    draft_files = list(drafts_dir.glob("**/*.txt"))
    draft_files = [f for f in draft_files if not f.name.startswith('prompt_')]
    
    if not draft_files:
        click.echo("❌ No drafts to validate")
        return
    
    click.echo(f"\n🔍 Found {len(draft_files)} drafts to validate")
    
    valid_count = 0
    for draft_file in draft_files:
        try:
            # Extract city/vibe from path with validation
            parts = draft_file.parts
            
            # Ensure path has enough parts
            if len(parts) < 3:
                click.echo(f"⚠️  Skipping {draft_file}: Invalid path structure")
                continue
                
            city = parts[-3]
            vibe = parts[-2]
            
            # Validate extracted values
            if not city or not isinstance(city, str) or city == 'drafts':
                click.echo(f"⚠️  Skipping {draft_file}: Invalid city value")
                continue
                
            if not vibe or not isinstance(vibe, str):
                click.echo(f"⚠️  Skipping {draft_file}: Invalid vibe value")
                continue
            
            click.echo(f"\nValidating {city}/{vibe}...")
            
            with open(draft_file, 'r') as f:
                content = f.read()
            
            # Skip if it's a prompt file
            if content.startswith('---'):
                # Extract response part
                parts = content.split('---', 2)
                if len(parts) > 2:
                    response = parts[2].strip()
                else:
                    continue
            else:
                response = content
            
            # Validate
            result = validator.validate_response(response, city, vibe)
            
            if result['valid']:
                click.echo("✅ Valid!")
                save_validated_draft(city, vibe, result['parsed_data'], 'unknown')
                valid_count += 1
            else:
                click.echo("❌ Invalid:")
                for error in result['errors'][:3]:
                    click.echo(f"  - {error}")
                    
        except Exception as e:
            click.echo(f"❌ Error validating {draft_file}: {str(e)}")
    
    click.echo(f"\n✅ Validated {valid_count}/{len(draft_files)} drafts")


# Helper functions
def get_multiline_input(max_lines: int = 1000, max_chars: int = 100000) -> str:
    """Get multiline input from user, ending with ###
    
    Args:
        max_lines: Maximum number of lines to accept (default 1000)
        max_chars: Maximum total characters to accept (default 100000)
    """
    lines = []
    total_chars = 0
    
    while True:
        line = input()
        if line.strip() == '###':
            break
            
        # Check line limit
        if len(lines) >= max_lines:
            click.echo(f"\n⚠️  Maximum line limit ({max_lines}) reached. Input truncated.")
            break
            
        # Check character limit
        line_length = len(line)
        if total_chars + line_length > max_chars:
            click.echo(f"\n⚠️  Maximum character limit ({max_chars}) reached. Input truncated.")
            break
            
        lines.append(line)
        total_chars += line_length + 1  # +1 for newline
        
    return '\n'.join(lines)


def save_prompt_with_metadata(city: str, vibe: str, prompt_data: Dict) -> Path:
    """Save prompt with YAML frontmatter"""
    
    # Create metadata
    metadata = {
        'city': city,
        'vibe': vibe,
        'date': datetime.now().isoformat(),
        'prompt_version': prompt_data['version'],
        'restaurant_count': prompt_data['restaurant_count'],
        'template': prompt_data.get('template_name', 'top10_prompt.txt')
    }
    
    # Format with frontmatter
    content = "---\n"
    content += yaml.dump(metadata, default_flow_style=False)
    content += "---\n\n"
    content += prompt_data['prompt']
    
    # Save to file
    prompt_dir = Path(f"output/drafts/{city}/{vibe}")
    prompt_dir.mkdir(parents=True, exist_ok=True)
    
    prompt_file = prompt_dir / f"prompt_v{prompt_data['version']}.txt"
    with open(prompt_file, 'w') as f:
        f.write(content)
    
    return prompt_file


def save_validated_draft(city: str, vibe: str, data: Dict, prompt_version: str):
    """Save validated draft"""
    
    # Add metadata
    data['prompt_version'] = prompt_version
    data['validated_at'] = datetime.now().isoformat()
    
    # Save to validated directory
    validated_dir = Path(f"output/validated/{city}/{vibe}")
    validated_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(validated_dir / filename, 'w') as f:
        json.dump(data, f, indent=2)


def save_failed_draft(city: str, vibe: str, response: str, errors: List[str]):
    """Save failed draft for manual review"""
    
    failed_dir = Path(f"output/failed/{city}/{vibe}")
    failed_dir.mkdir(parents=True, exist_ok=True)
    
    # Save with error info
    data = {
        'city': city,
        'vibe': vibe,
        'response': response,
        'errors': errors,
        'failed_at': datetime.now().isoformat()
    }
    
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(failed_dir / filename, 'w') as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    main()