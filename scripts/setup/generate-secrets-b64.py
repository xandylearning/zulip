#!/usr/bin/env python3
"""
Generate base64-encoded Zulip secrets for Cloud Run deployment.

This script creates a zulip-secrets.conf file and outputs it as base64,
which can be used as the ZULIP_SECRETS_B64 environment variable in Cloud Run.
"""

import base64
import secrets
import sys
from pathlib import Path

def generate_secret(length=64):
    """Generate a random secret string."""
    return secrets.token_urlsafe(length)

def create_secrets_conf():
    """Create the zulip-secrets.conf content."""
    content = """[secrets]
# Django secret key - used by Django for cryptographic signing
secret_key = {secret_key}

# Shared secret for internal communication between Zulip services
shared_secret = {shared_secret}

# PostgreSQL database password
postgres_password = {postgres_password}

# Email configuration (optional)
email_password = 

# Social authentication secrets (optional)
social_auth_github_secret = 
social_auth_google_secret = 

# File upload secrets (optional)
s3_secret_key = 

# Push notification secrets (optional)
zulip_org_id = 
zulip_org_key = 

# Caching and messaging passwords
memcached_password = 
rabbitmq_password = {rabbitmq_password}
redis_password = 

# Additional secrets for production
camo_key = {camo_key}
initial_password_salt = {initial_password_salt}
""".format(
        secret_key=generate_secret(50),
        shared_secret=generate_secret(32),
        postgres_password=generate_secret(32),
        rabbitmq_password=generate_secret(32),
        camo_key=secrets.token_hex(32),
        initial_password_salt=generate_secret(32)
    )
    return content

def main():
    """Main function to generate and output base64-encoded secrets."""
    print("Generating Zulip secrets for Cloud Run deployment...")
    
    # Create the secrets configuration
    secrets_content = create_secrets_conf()
    
    # Encode to base64
    secrets_b64 = base64.b64encode(secrets_content.encode('utf-8')).decode('utf-8')
    
    print("\n" + "="*60)
    print("ZULIP_SECRETS_B64 (for GitHub Secrets):")
    print("="*60)
    print(secrets_b64)
    print("="*60)
    
    print("\n" + "="*60)
    print("Raw secrets file content (for reference):")
    print("="*60)
    print(secrets_content)
    print("="*60)
    
    print("\nInstructions:")
    print("1. Copy the ZULIP_SECRETS_B64 value above")
    print("2. Add it to your GitHub repository secrets as 'ZULIP_SECRETS_B64'")
    print("3. Update the postgres_password in the raw content above with your actual database password")
    print("4. Re-run this script if you need to update the postgres_password")
    print("\nNote: Keep the raw secrets file content secure - it contains sensitive information!")

if __name__ == "__main__":
    main()
