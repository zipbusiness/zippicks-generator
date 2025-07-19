<?php
/**
 * Plugin Name: ZipPicks Vibe API
 * Description: REST API endpoint for vibe ID lookups
 * Version: 1.0.0
 * 
 * Place this file in wp-content/mu-plugins/ for automatic loading
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Register REST API routes
 */
add_action('rest_api_init', function() {
    register_rest_route('zippicks/v1', '/vibes/lookup', [
        'methods' => 'POST',
        'callback' => 'zippicks_lookup_vibe_ids',
        'permission_callback' => 'zippicks_vibe_api_permissions',
        'args' => [
            'slugs' => [
                'required' => true,
                'type' => 'array',
                'items' => [
                    'type' => 'string',
                    'sanitize_callback' => 'sanitize_title'
                ],
                'validate_callback' => function($param) {
                    return is_array($param) && count($param) > 0;
                }
            ]
        ]
    ]);
});

/**
 * Permission callback for the API endpoint
 * 
 * @param WP_REST_Request $request
 * @return bool
 */
function zippicks_vibe_api_permissions($request) {
    // Option 1: Require authentication (recommended for production)
    // return current_user_can('edit_posts');
    
    // Option 2: Allow with application password
    $auth_header = $request->get_header('Authorization');
    if ($auth_header && strpos($auth_header, 'Basic') === 0) {
        return true;
    }
    
    // Option 3: Check for a custom API key (most secure)
    $api_key = $request->get_header('X-ZipPicks-API-Key');
    $valid_key = get_option('zippicks_vibe_api_key', '');
    
    if ($api_key && $valid_key && hash_equals($valid_key, $api_key)) {
        return true;
    }
    
    return false;
}

/**
 * API callback to lookup vibe IDs by slugs
 * 
 * @param WP_REST_Request $request
 * @return WP_REST_Response
 */
function zippicks_lookup_vibe_ids($request) {
    global $wpdb;
    
    $slugs = $request->get_param('slugs');
    
    // Additional sanitization
    $slugs = array_map('sanitize_title', $slugs);
    $slugs = array_filter($slugs); // Remove empty values
    $slugs = array_unique($slugs); // Remove duplicates
    
    if (empty($slugs)) {
        return new WP_REST_Response([
            'success' => false,
            'message' => 'No valid slugs provided',
            'data' => [
                'vibe_ids' => [],
                'mapping' => []
            ]
        ], 400);
    }
    
    // Build the query
    $table_name = $wpdb->prefix . 'zippicks_vibes';
    $placeholders = implode(',', array_fill(0, count($slugs), '%s'));
    
    $query = $wpdb->prepare(
        "SELECT id, slug, name FROM {$table_name} WHERE slug IN ($placeholders)",
        $slugs
    );
    
    $results = $wpdb->get_results($query, ARRAY_A);
    
    // Process results
    $vibe_ids = [];
    $mapping = [];
    $found_slugs = [];
    
    if ($results) {
        foreach ($results as $row) {
            $vibe_ids[] = (int) $row['id'];
            $mapping[$row['slug']] = [
                'id' => (int) $row['id'],
                'name' => $row['name']
            ];
            $found_slugs[] = $row['slug'];
        }
    }
    
    // Identify any missing slugs
    $missing_slugs = array_diff($slugs, $found_slugs);
    
    return new WP_REST_Response([
        'success' => true,
        'data' => [
            'vibe_ids' => $vibe_ids,
            'mapping' => $mapping,
            'missing_slugs' => array_values($missing_slugs),
            'request_count' => count($slugs),
            'found_count' => count($vibe_ids)
        ]
    ], 200);
}

/**
 * Helper function to generate a secure API key
 * Run this once to create a key, then save it
 */
function zippicks_generate_api_key() {
    $key = wp_generate_password(32, false);
    update_option('zippicks_vibe_api_key', $key);
    return $key;
}

// Optional: Add an admin notice if API key is not set
add_action('admin_notices', function() {
    if (!get_option('zippicks_vibe_api_key')) {
        ?>
        <div class="notice notice-warning">
            <p>ZipPicks Vibe API: No API key set. Generate one with: <code>wp eval "echo zippicks_generate_api_key();"</code></p>
        </div>
        <?php
    }
});