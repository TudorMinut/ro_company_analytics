# Deployment Guide

This project uses template variables for configuration to avoid exposing sensitive information in version control.

## Configuration Files

The following files contain template placeholders that must be replaced with actual values:

| File                                             | Variables                                            |
| ------------------------------------------------ | ---------------------------------------------------- |
| `infra/ecs-task-definition.json`                 | `${AWS_ACCOUNT_ID}`, `${AWS_REGION}`, `${S3_BUCKET}` |
| `infra/iam/scheduler-ecs-policy.json`            | `${AWS_ACCOUNT_ID}`, `${AWS_REGION}`                 |
| `infra/iam/s3-downloader-policy.json`            | `${S3_BUCKET}`                                       |
| `infra/iam/databricks-s3-trust-placeholder.json` | `${EXTERNAL_AWS_ACCOUNT_ID}`, `${EXTERNAL_ID}`       |

## Setup Instructions

### 1. Create `.env` file from template

```bash
cp .env.example .env
```

### 2. Edit `.env` with your actual values

```bash
# Edit these values with your AWS configuration
AWS_ACCOUNT_ID=555146423555
AWS_REGION=eu-central-1
S3_BUCKET=ro-company-lake
EXTERNAL_AWS_ACCOUNT_ID=414351767826
EXTERNAL_ID=your_external_id_here
```

### 3. Substitute variables in configuration files

Use one of the following methods:

#### Option A: Using `envsubst` (Linux/Mac)

```bash
envsubst < infra/ecs-task-definition.json > infra/ecs-task-definition.resolved.json
envsubst < infra/iam/scheduler-ecs-policy.json > infra/iam/scheduler-ecs-policy.resolved.json
envsubst < infra/iam/s3-downloader-policy.json > infra/iam/s3-downloader-policy.resolved.json
envsubst < infra/iam/databricks-s3-trust-placeholder.json > infra/iam/databricks-s3-trust-placeholder.resolved.json
```

#### Option B: Using PowerShell (Windows)

```powershell
$env:AWS_ACCOUNT_ID = "555146423555"
$env:AWS_REGION = "eu-central-1"
$env:S3_BUCKET = "ro-company-lake"
$env:EXTERNAL_AWS_ACCOUNT_ID = "414351767826"
$env:EXTERNAL_ID = "your_external_id_here"

# Then substitute
(Get-Content infra/ecs-task-definition.json) -replace '\$\{AWS_ACCOUNT_ID\}', $env:AWS_ACCOUNT_ID | Set-Content infra/ecs-task-definition.resolved.json
```

#### Option C: Using a deployment script

Create a `deploy.sh` or `deploy.ps1` script in your CI/CD pipeline to automate this process.

### 4. Deploy with resolved configuration

Use the `.resolved.json` files for deployment:

```bash
aws ecs register-task-definition --cli-input-json file://infra/ecs-task-definition.resolved.json
```

## Security Notes

- **Never commit** `.env` files with actual credentials
- **Never commit** `.resolved.json` files
- **Never commit** any files with exposed account IDs or credentials
- Use `.gitignore` to prevent accidental commits
- Store secrets securely in AWS Secrets Manager or similar service
- Consider using AWS Systems Manager Parameter Store for configuration
