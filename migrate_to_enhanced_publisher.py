#!/usr/bin/env python3
"""
Migration script to update your system to use the enhanced publisher
"""

import shutil
from datetime import datetime
from pathlib import Path


def migrate_publisher():
    """Migrate from old publisher to enhanced publisher"""
    
    print("🚀 Starting publisher migration...")
    
    # Backup original publisher
    original = Path("publisher.py")
    backup = Path(f"publisher_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py")
    
    if original.exists():
        shutil.copy2(original, backup)
        print(f"✅ Backed up original publisher to: {backup}")
    
    # Copy enhanced publisher
    enhanced = Path("publisher_enhanced.py")
    if enhanced.exists():
        shutil.copy2(enhanced, original)
        print(f"✅ Replaced publisher.py with enhanced version")
    else:
        print("❌ Error: publisher_enhanced.py not found!")
        return False
    
    # Update generate.py imports (if needed)
    generate_file = Path("generate.py")
    if generate_file.exists():
        content = generate_file.read_text()
        
        # Check if we need to update anything
        if "from publisher import Publisher" in content:
            print("✅ generate.py already imports Publisher correctly")
        elif "from publisher import" in content:
            # Update import if needed
            new_content = content.replace(
                "from publisher import",
                "from publisher import Publisher  #"
            )
            generate_file.write_text(new_content)
            print("✅ Updated generate.py imports")
    
    print("\n📋 Migration Summary:")
    print("1. Original publisher backed up")
    print("2. Enhanced publisher is now active")
    print("3. Vibe lookup integration enabled")
    print("4. Master Critic post type support added")
    
    print("\n⚠️  Important Notes:")
    print("- Make sure your .env file has WP_SITE_URL and WP_API_KEY set")
    print("- The vibe API endpoint must be active on your WordPress site")
    print("- Restaurant data should include 'vibes' arrays with slug values")
    
    print("\n✅ Migration complete!")
    return True


def test_enhanced_features():
    """Test that enhanced features are working"""
    print("\n🧪 Testing enhanced features...")
    
    try:
        from publisher import EnhancedPublisher, VibeLookupClient
        print("✅ Enhanced publisher imports successfully")
        
        # Test initialization
        publisher = EnhancedPublisher()
        print("✅ Publisher initialized")
        
        # Check vibe client
        if hasattr(publisher, 'vibe_client'):
            print("✅ Vibe lookup client configured")
        else:
            print("❌ Vibe lookup client not found")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("Enhanced Publisher Migration Tool")
    print("=" * 50)
    
    # Run migration
    if migrate_publisher():
        # Test the new features
        test_enhanced_features()
        
        print("\n🎉 Ready to use enhanced publisher!")
        print("\nExample usage:")
        print("python generate.py --publish-all")
    else:
        print("\n❌ Migration failed. Please check the errors above.")