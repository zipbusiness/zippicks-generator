# Security Configuration

## Credential Management

This application follows security best practices by using environment variables for sensitive credentials instead of storing them in configuration files.

### Setting Up Environment Variables

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit the .env file with your credentials:**
   ```bash
   # WordPress Configuration
   WP_SITE_URL=https://your-wordpress-site.com
   WP_API_ENDPOINT=/wp-json/wp/v2
   WP_AUTH_TYPE=basic
   
   # For Basic Authentication
   WP_USERNAME=your_wordpress_username
   WP_PASSWORD=your_wordpress_password
   
   # For Application Authentication
   WP_API_KEY=your_api_key_here
   ```

3. **Ensure .env is in your .gitignore:**
   ```bash
   echo ".env" >> .gitignore
   ```

### Using Environment Variables

The application will automatically load environment variables in this order of precedence:
1. System environment variables (highest priority)
2. .env file (if using python-dotenv)
3. Config file defaults (lowest priority, non-sensitive data only)

### Running with Environment Variables

You can set environment variables in several ways:

**Option 1: Export in shell**
```bash
export WP_USERNAME="your_username"
export WP_PASSWORD="your_password"
python generate.py --mode daily
```

**Option 2: Inline with command**
```bash
WP_USERNAME="your_username" WP_PASSWORD="your_password" python generate.py --mode daily
```

**Option 3: Using python-dotenv (recommended)**
```bash
pip install python-dotenv
# Create .env file with your credentials
python generate.py --mode daily
```

### Security Best Practices

1. **Never commit credentials to version control**
   - Always use .gitignore for .env files
   - Review commits before pushing

2. **Use least privilege principle**
   - Create WordPress users with minimal required permissions
   - Use application-specific passwords when possible

3. **Rotate credentials regularly**
   - Change passwords and API keys periodically
   - Update environment variables after rotation

4. **Secure your environment**
   - Protect .env files with appropriate file permissions
   - Use secrets management services in production (e.g., AWS Secrets Manager, HashiCorp Vault)

### Configuration File Security

The `config/wp_config.yaml` file should now only contain non-sensitive configuration:

```yaml
# Non-sensitive configuration only
site_url: https://example.com  # Can be overridden by WP_SITE_URL env var
api_endpoint: /wp-json/wp/v2
auth_type: basic

# Category and tag mappings
category_mapping:
  date-night: 15
  family-friendly: 16
  
tag_mapping:
  italian: 25
  mexican: 26
```

Any credentials found in configuration files will be ignored and a warning will be logged.