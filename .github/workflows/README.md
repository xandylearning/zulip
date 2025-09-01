# GitHub Workflows

This directory contains GitHub Actions workflows for the Zulip project.

## Zulip CD - Docker Build and Cloud Run Deploy

The `zulip-cd.yml` workflow builds a Docker image and deploys it to Google Cloud Run.

### Prerequisites

1. **Google Cloud Project**: You need a Google Cloud project with the following APIs enabled:
   - Cloud Run API
   - Artifact Registry API

2. **Service Account**: Create a service account with minimal required permissions:

   **Option A: Minimal Permissions (Recommended)**
   ```bash
   # Create service account
   gcloud iam service-accounts create github-actions \
     --display-name="GitHub Actions Service Account"
   
   # Grant specific permissions
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/run.admin"
   
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/artifactregistry.admin"
   
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/iam.serviceAccountUser"
   ```

   **Option B: Broad Permissions (Less Secure)**
   - Cloud Run Admin
   - Artifact Registry Admin
   - Cloud Build Service Account
   - Service Account User

   **Why Service Account User is needed:**
   - Allows the workflow to deploy Cloud Run services that run under the default compute service account
   - Enables cross-service authentication for resource access
   - Required for managing Cloud Run revisions and traffic routing

3. **Artifact Registry Repository**: Create a Docker repository in Artifact Registry:
   ```bash
   gcloud artifacts repositories create zulip \
     --repository-format=docker \
     --location=us-central1 \
     --description="Zulip Docker repository"
   ```

### Required Secrets

Add the following secrets to your GitHub repository:

#### **Core Secrets**
- `GCP_PROJECT_ID`: Your Google Cloud project ID
- `GCP_SA_KEY`: The JSON key file content of your service account
- `ZULIP_SECRETS_KEY`: Zulip secrets key for the application

#### **PostgreSQL Database Secrets (Required)**

**Staging Environment:**
- `STAGING_POSTGRES_HOST`: PostgreSQL host for staging environment (required)
- `STAGING_POSTGRES_PORT`: PostgreSQL port (optional, default: 5432)
- `STAGING_POSTGRES_PASSWORD`: PostgreSQL password for staging (required)
- `STAGING_POSTGRES_SSLMODE`: SSL mode (optional, default: require)

**Production Environment:**
- `PROD_POSTGRES_HOST`: PostgreSQL host for production environment (required)
- `PROD_POSTGRES_PORT`: PostgreSQL port (optional, default: 5432)
- `PROD_POSTGRES_PASSWORD`: PostgreSQL password for production (required)
- `PROD_POSTGRES_SSLMODE`: SSL mode (optional, default: require)

#### **Optional Service Secrets (for advanced configurations)**
- `REDIS_PASSWORD`: Redis password if using external Redis
- `RABBITMQ_PASSWORD`: RabbitMQ password if using external RabbitMQ
- `MEMCACHED_PASSWORD`: Memcached password if using external Memcached

### Permission Breakdown

Here's why each permission is needed and how to minimize them:

#### **Cloud Run Admin (`roles/run.admin`)**
- **Why needed**: Deploy, update, and manage Cloud Run services
- **What it provides**: Full access to Cloud Run resources
- **Can be minimized**: Use `roles/run.developer` + specific IAM bindings for individual services

#### **Artifact Registry Admin (`roles/artifactregistry.admin`)**
- **Why needed**: Push Docker images to Artifact Registry
- **What it provides**: Full access to all Artifact Registry repositories
- **Can be minimized**: Use `roles/artifactregistry.writer` + specific repository permissions

#### **Service Account User (`roles/iam.serviceAccountUser`)**
- **Why needed**: Cloud Run services need to run under a service account
- **What it provides**: Ability to impersonate other service accounts
- **Can be minimized**: Grant only for the specific service account that Cloud Run will use

#### **Cloud Build Service Account (NOT needed)**
- **Why it was listed**: Misunderstanding - we're using Docker Buildx, not Cloud Build
- **What it provides**: Access to Cloud Build service
- **Recommendation**: Remove this permission entirely

#### **Minimal Permission Alternative**
```bash
# Create custom roles with minimal permissions
gcloud iam roles create githubActionsCloudRun \
  --project=$PROJECT_ID \
  --title="GitHub Actions Cloud Run" \
  --description="Minimal permissions for GitHub Actions Cloud Run deployment" \
  --permissions="run.services.create,run.services.update,run.services.get,run.revisions.create,run.revisions.update,run.revisions.get"

gcloud iam roles create githubActionsArtifactRegistry \
  --project=$PROJECT_ID \
  --title="GitHub Actions Artifact Registry" \
  --description="Minimal permissions for GitHub Actions Artifact Registry" \
  --permissions="artifactregistry.repositories.uploadArtifacts,artifactregistry.repositories.downloadArtifacts"

# Apply custom roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="projects/$PROJECT_ID/roles/githubActionsCloudRun"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="projects/$PROJECT_ID/roles/githubActionsArtifactRegistry"
```

### Workflow Features

#### Triggers
- **Push to main/master**: Builds and deploys to staging
- **Tags**: Builds and deploys to production
- **Pull Requests**: Builds image for testing (no deployment)
- **Manual**: Allows manual deployment to staging or production

#### Environments
- **Staging**: Deployed on pushes to main branch
  - Memory: 2Gi
  - CPU: 2
  - Max instances: 10
  - Min instances: 0
  - Concurrency: 80

- **Production**: Deployed on tags or manual trigger
  - Memory: 4Gi
  - CPU: 4
  - Max instances: 20
  - Min instances: 1
  - Concurrency: 100

#### Security
- Vulnerability scanning on staging deployments
- Docker layer caching for faster builds
- Secure credential handling

### Usage

#### Automatic Deployment
1. Push to the main branch to deploy to staging
2. Create a tag to deploy to production

#### Manual Deployment
1. Go to Actions tab in GitHub
2. Select "Zulip CD - Docker Build and Cloud Run Deploy"
3. Click "Run workflow"
4. Choose environment (staging/production)
5. Click "Run workflow"

### PostgreSQL Database Setup

Zulip requires a PostgreSQL database to function. Here are the recommended setup options:

#### **Option 1: Google Cloud SQL (Recommended)**
```bash
# Create Cloud SQL instance
gcloud sql instances create zulip-postgres \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --storage-type=SSD \
  --storage-size=20GB \
  --backup-start-time=03:00

# Create database
gcloud sql databases create zulip --instance=zulip-postgres

# Create user
gcloud sql users create zulip \
  --instance=zulip-postgres \
  --password=your-secure-password

# Get connection information
gcloud sql instances describe zulip-postgres \
  --format="value(connectionName,ipAddresses[0].ipAddress)"
```

**Note**: Cloud SQL instances don't include PostgreSQL dictionary files by default, which affects full-text search functionality. The workflow automatically configures `missing_dictionaries = true` in zulip.conf to handle this limitation.

#### **Option 2: External PostgreSQL**
You can use any PostgreSQL server accessible from Cloud Run:
- Amazon RDS PostgreSQL
- Azure Database for PostgreSQL
- Self-hosted PostgreSQL with public access
- PostgreSQL on Google Compute Engine

#### **Database Configuration**
After setting up PostgreSQL, configure these GitHub secrets:
- `STAGING_POSTGRES_HOST`: Your database host/IP
- `STAGING_POSTGRES_PASSWORD`: Database password
- `PROD_POSTGRES_HOST`: Production database host/IP
- `PROD_POSTGRES_PASSWORD`: Production database password

### Customization

You can customize the workflow by modifying:

- **Region**: Change `REGION` environment variable
- **Repository name**: Change `REPOSITORY` environment variable
- **Service name**: Change `SERVICE_NAME` environment variable
- **Resource allocation**: Modify the `flags` section in deployment steps
- **Environment variables**: Add more environment variables in `env_vars` section

### Troubleshooting

#### Common Issues

1. **Authentication errors**: Ensure your service account has the correct permissions
2. **Build failures**: Check that the Dockerfile is valid and all dependencies are available
3. **Deployment failures**: Verify that the Cloud Run service can be created in your region
4. **Image pull errors**: Ensure the Artifact Registry repository exists and is accessible
5. **Database connection errors**: 
   - Verify PostgreSQL host and credentials are correct
   - Ensure Cloud Run can reach your database (check firewall rules)
   - For Cloud SQL, ensure public IP is enabled or use Cloud SQL Proxy
6. **Database migration failures**:
   - Check if database user has sufficient privileges
   - Verify database exists and is accessible
   - Review application logs for specific migration errors
7. **Full-text search issues**:
   - Cloud SQL instances have `missing_dictionaries = true` configured automatically
   - This is normal and expected for managed PostgreSQL services
   - Full-text search will still work but with reduced stemming capabilities

#### Debugging

- Check the workflow logs in the Actions tab
- Verify secrets are correctly set in repository settings
- Test the Docker build locally before pushing
- Check Google Cloud Console for service account permissions

### Cost Optimization

- Use appropriate resource limits for your workload
- Consider using Cloud Run's min-instances=0 for staging to reduce costs
- Monitor usage in Google Cloud Console
- Set up billing alerts for unexpected charges
