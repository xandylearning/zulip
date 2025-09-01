# Zulip Cloud Run Deployment

This workflow builds and deploys Zulip to Google Cloud Run.

## Required GitHub Secrets

The following secrets must be configured in your GitHub repository settings:

### Required Secrets

- `GCP_PROJECT_ID`: Your Google Cloud Project ID
- `GCP_SA_KEY`: Service account key JSON for authentication
- `POSTGRES_HOST`: PostgreSQL database host
- `POSTGRES_PORT`: PostgreSQL database port (usually 5432)
- `POSTGRES_PASSWORD`: PostgreSQL database password
- `POSTGRES_SSLMODE`: PostgreSQL SSL mode (usually 'require')
- `ZULIP_SECRETS_B64`: Base64-encoded zulip-secrets.conf file (see setup instructions below)

### Optional Secrets

- `CLOUDSQL_INSTANCE`: Cloud SQL instance connection name (if using Cloud SQL)

### Service Account Permissions

The service account used for deployment needs the following roles:
- Cloud Run Admin
- Artifact Registry Administrator
- Service Account User
- Cloud SQL Client (if using Cloud SQL)

## Setup Instructions

### 1. Generate Secrets

Run the secrets generation script to create your `ZULIP_SECRETS_B64`:

```bash
python3 scripts/setup/generate-secrets-b64.py
```

This will output a base64-encoded string that you'll add to GitHub Secrets.

### 2. Update Database Password

After running the script, you'll see the raw secrets content. Update the `postgres_password` field with your actual database password, then re-run the script to generate the updated base64 string.

### 3. Add to GitHub Secrets

Copy the `ZULIP_SECRETS_B64` value and add it to your GitHub repository secrets.

## Deployment Process

1. **Build**: Docker image is built and pushed to Artifact Registry
2. **Deploy**: Cloud Run service is updated with the new image
3. **Configure**: Secrets are extracted from base64 and written to `/etc/zulip/zulip-secrets.conf`
4. **Initialize**: Database migrations are run if needed

## Environment Variables

The following environment variables are set in the Cloud Run service:

- `ZULIP_ENVIRONMENT=production`
- `EXTERNAL_HOST`: Auto-generated Cloud Run URL
- `POSTGRES_HOST`: From GitHub secret
- `POSTGRES_PORT`: From GitHub secret
- `POSTGRES_PASSWORD`: From GitHub secret
- `POSTGRES_SSLMODE`: From GitHub secret
- `ZULIP_SECRETS_B64`: Base64-encoded secrets file from GitHub secret

## Troubleshooting

### Common Issues

1. **Missing shared_secret error**: Ensure `ZULIP_SECRETS_B64` is properly set in GitHub secrets and contains a valid `shared_secret`
2. **Database connection issues**: Verify `POSTGRES_HOST`, `POSTGRES_PORT`, and `POSTGRES_PASSWORD` are correctly set
3. **Permission errors**: Ensure the service account has the required roles
4. **Malformed env-vars error**: The workflow now uses clean environment variables without comments

### Logs

Check the Cloud Run logs for detailed error messages. The container will fail to start if required secrets are missing.

### Security Notes

- The `ZULIP_SECRETS_B64` contains all sensitive configuration in base64-encoded format
- Secrets are automatically extracted and written to `/etc/zulip/zulip-secrets.conf` with proper permissions
- The secrets file is owned by the zulip user with 640 permissions
- All secrets are stored securely in GitHub's encrypted secrets store

## Security Notes

- Secrets are automatically generated if not provided, but it's recommended to set them explicitly for production
- The secrets file is created with restricted permissions (640) and owned by the zulip user
- All secrets are stored securely in GitHub's encrypted secrets store