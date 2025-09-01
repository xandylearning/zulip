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

### Optional Secrets (with fallbacks)

- `SHARED_SECRET`: Shared secret for internal communication (auto-generated if not provided)
- `ZULIP_SECRETS_KEY`: Django secret key (auto-generated if not provided)
- `ZULIP_SECRET_KEY`: Alternative name for Django secret key (used as fallback)

### Service Account Permissions

The service account used for deployment needs the following roles:
- Cloud Run Admin
- Artifact Registry Administrator
- Service Account User
- Cloud SQL Client (if using Cloud SQL)

## Deployment Process

1. **Build**: Docker image is built and pushed to Artifact Registry
2. **Deploy**: Cloud Run service is updated with the new image
3. **Configure**: Secrets and settings are configured during container startup
4. **Initialize**: Database migrations are run if needed

## Environment Variables

The following environment variables are set in the Cloud Run service:

- `ZULIP_ENVIRONMENT=production`
- `POSTGRES_HOST`: From GitHub secret
- `POSTGRES_PORT`: From GitHub secret
- `POSTGRES_PASSWORD`: From GitHub secret
- `POSTGRES_SSLMODE`: From GitHub secret
- `ZULIP_SECRETS_KEY`: From GitHub secret or auto-generated
- `SHARED_SECRET`: From GitHub secret or auto-generated
- `EXTERNAL_HOST`: Auto-generated Cloud Run URL

## Troubleshooting

### Common Issues

1. **Missing shared_secret error**: Ensure at least one of `SHARED_SECRET`, `ZULIP_SECRETS_KEY`, or `ZULIP_SECRET_KEY` is set in GitHub secrets
2. **Database connection issues**: Verify `POSTGRES_HOST`, `POSTGRES_PORT`, and `POSTGRES_PASSWORD` are correctly set
3. **Permission errors**: Ensure the service account has the required roles

### Logs

Check the Cloud Run logs for detailed error messages. The container will fail to start if required secrets are missing.

## Security Notes

- Secrets are automatically generated if not provided, but it's recommended to set them explicitly for production
- The secrets file is created with restricted permissions (640) and owned by the zulip user
- All secrets are stored securely in GitHub's encrypted secrets store