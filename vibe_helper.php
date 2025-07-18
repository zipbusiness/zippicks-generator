<?php
/**
 * Helper function to get vibe IDs from slugs
 * 
 * @param array $slugs Array of vibe slugs
 * @return array Array of vibe IDs (numeric)
 */
function get_vibe_ids_by_slugs($slugs) {
    global $wpdb;
    
    // Return empty array if no slugs provided
    if (empty($slugs) || !is_array($slugs)) {
        return array();
    }
    
    // Sanitize slugs
    $slugs = array_map('sanitize_title', $slugs);
    $slugs = array_filter($slugs); // Remove empty values
    
    if (empty($slugs)) {
        return array();
    }
    
    // Build placeholders for prepared statement
    $placeholders = implode(',', array_fill(0, count($slugs), '%s'));
    
    // Query the database
    $table_name = $wpdb->prefix . 'zippicks_vibes';
    $query = $wpdb->prepare(
        "SELECT id, slug FROM {$table_name} WHERE slug IN ($placeholders)",
        $slugs
    );
    
    $results = $wpdb->get_results($query, ARRAY_A);
    
    // Extract just the IDs
    $vibe_ids = array();
    if ($results) {
        foreach ($results as $row) {
            $vibe_ids[] = (int) $row['id'];
        }
    }
    
    return $vibe_ids;
}

/**
 * Alternative: Get vibe IDs with slug mapping
 * Returns associative array for debugging/verification
 * 
 * @param array $slugs Array of vibe slugs
 * @return array Associative array ['slug' => id]
 */
function get_vibe_ids_by_slugs_with_mapping($slugs) {
    global $wpdb;
    
    if (empty($slugs) || !is_array($slugs)) {
        return array();
    }
    
    $slugs = array_map('sanitize_title', $slugs);
    $slugs = array_filter($slugs);
    
    if (empty($slugs)) {
        return array();
    }
    
    $placeholders = implode(',', array_fill(0, count($slugs), '%s'));
    $table_name = $wpdb->prefix . 'zippicks_vibes';
    
    $query = $wpdb->prepare(
        "SELECT id, slug FROM {$table_name} WHERE slug IN ($placeholders)",
        $slugs
    );
    
    $results = $wpdb->get_results($query, ARRAY_A);
    
    $vibe_mapping = array();
    if ($results) {
        foreach ($results as $row) {
            $vibe_mapping[$row['slug']] = (int) $row['id'];
        }
    }
    
    return $vibe_mapping;
}