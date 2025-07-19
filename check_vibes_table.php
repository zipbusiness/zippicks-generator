<?php
/**
 * Diagnostic script to check vibes table structure and contents
 * Upload this to your WordPress root and run it once
 */

// Load WordPress
require_once('wp-load.php');

global $wpdb;

// Check if user is admin
if (!current_user_can('manage_options')) {
    die('Unauthorized');
}

echo "<h1>ZipPicks Vibes Table Diagnostic</h1>";
echo "<pre>";

// 1. Check table name
$table_name = $wpdb->prefix . 'zippicks_vibes';
echo "Looking for table: $table_name\n\n";

// 2. Check if table exists
$table_exists = $wpdb->get_var("SHOW TABLES LIKE '$table_name'");
if (!$table_exists) {
    echo "❌ Table does not exist!\n";
    
    // List all tables with 'vibe' in the name
    echo "\nTables containing 'vibe':\n";
    $tables = $wpdb->get_col("SHOW TABLES LIKE '%vibe%'");
    foreach ($tables as $table) {
        echo "  - $table\n";
    }
} else {
    echo "✅ Table exists!\n\n";
    
    // 3. Show table structure
    echo "Table structure:\n";
    $columns = $wpdb->get_results("SHOW COLUMNS FROM $table_name");
    foreach ($columns as $column) {
        echo "  - {$column->Field} ({$column->Type})\n";
    }
    
    // 4. Count rows
    $count = $wpdb->get_var("SELECT COUNT(*) FROM $table_name");
    echo "\nTotal vibes: $count\n\n";
    
    // 5. Show sample data
    if ($count > 0) {
        echo "Sample vibes (first 10):\n";
        $vibes = $wpdb->get_results("SELECT id, slug, name FROM $table_name LIMIT 10");
        foreach ($vibes as $vibe) {
            echo "  ID: {$vibe->id} | Slug: '{$vibe->slug}' | Name: '{$vibe->name}'\n";
        }
        
        // 6. Show all unique slug patterns
        echo "\nUnique slug patterns:\n";
        $slugs = $wpdb->get_col("SELECT DISTINCT slug FROM $table_name ORDER BY slug");
        $patterns = [];
        foreach ($slugs as $slug) {
            if (strpos($slug, '-') !== false) {
                $patterns['hyphenated'][] = $slug;
            } elseif (strpos($slug, '_') !== false) {
                $patterns['underscored'][] = $slug;
            } else {
                $patterns['single_word'][] = $slug;
            }
        }
        
        foreach ($patterns as $type => $examples) {
            echo "  $type: " . implode(', ', array_slice($examples, 0, 3)) . "\n";
        }
    }
}

echo "</pre>";

// Clean up sensitive info
echo "<p><small>This diagnostic script should be deleted after use.</small></p>";