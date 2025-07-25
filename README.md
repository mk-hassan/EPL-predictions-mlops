## Setting Up the Environment

To activate and install the dependencies for this project, follow these steps:

1. **Activate Pipenv Shell**
   Open your terminal and navigate to the project directory:
   ```bash
   cd /path/to/EPL-predictions
   ```

2. **Install Dependencies Using uv (Recommended)**
   If you have `uv` installed, set the environment variable and run:
   ```bash
   export PIPENV_INSTALLER=uv
   pipenv install
   ```
   This will use `uv` for faster and more reliable dependency installation.

3. **If uv Is Not Found**
   If you do not have `uv` installed, Pipenv will fall back to using `pip`.
   You can install dependencies normally:
   ```bash
   pipenv install
   ```

4. **Activate the Virtual Environment**
   After installation, activate the environment:
   ```bash
   pipenv shell
   ```

This will set up all required packages as specified in the `Pipfile`.

---

## Initializing Pre-commit Hooks

To enable automated code quality and security checks before each commit, initialize pre-commit in your project:

### Setup Tasks

- **Install pre-commit (if not already installed):**
  ```bash
  pipenv install --dev pre-commit
  ```

- **Install the pre-commit hooks:**
  ```bash
  pre-commit install
  ```

- **(Optional) Install commit-msg and other hook types:**
  ```bash
  pre-commit install --hook-type commit-msg --hook-type pre-push
  ```

To list all created hooks
```bash
ls .git/hooks | grep -v '\.sample$'
```

---

### What pre-commit will do

- [x] Automatically runs code formatters (Black, isort, Ruff) on staged files before each commit.
- [x] Runs linters (pylint) and security scanners (Bandit) to check code quality and security.
- [x] Prevents commits if code does not meet quality or security standards.
- [x] Helps maintain consistent code style and catch issues early.

You can manually run all hooks on all files with:
```bash
pre-commit run --all
```

## Infrastructure Overview

This document provides a comprehensive overview of the Terraform-managed infrastructure for the EPL Predictions project, emphasizing architectural decisions, best practices, and organizational patterns.

---

### 1. Infrastructure Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS Cloud Environment                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────┐ │
│  │   CloudWatch    │    │    S3 Buckets    │    │ Secrets     │ │
│  │   Monitoring    │    │                  │    │ Manager     │ │
│  │   + Dashboard   │    │ • MLflow Arts    │    │             │ │
│  │   + Alarms      │    │ • Data Storage   │    │ DB Creds    │ │
│  │   + Log Groups  │    │                  │    │             │ │
│  └─────────────────┘    └──────────────────┘    └─────────────┘ │
│           │                       │                      │      │
│           └───────────────────────┼──────────────────────┘      │
│                                   │                             │
│  ┌────────────────────────────────|───────────────────────────┐ │
│  │                Default VPC     |                           | │
│  │                                |                           | │
│  │  ┌───────────────┐             │           ┌─────────────┐ │ │
│  │  │   EC2 App     │             │           │ RDS         │ │ │
│  │  │   Instance    │◄────────────┼───────────┤ PostgreSQL  │ │ │
│  │  │               │             │           │             │ │ │
│  │  │ • t3.micro    │             │           │ • t3.micro  │ │ │
│  │  │ • Ubuntu      │             │           │ • Multi-DB  │ │ │
│  │  │ • IAM Role    │             │           │ • Encrypted │ │ │
│  │  └───────────────┘             │           └─────────────┘ │ │
│  │         │                      │                   │       │ │
│  │    ┌────────────┐              │           ┌─────────────┐ │ │
│  │    │ Security   │              │           │ DB Subnet   │ │ │
│  │    │ Group      │              │           │ Group       │ │ │
│  │    │ (SSH+HTTP) │              │           │             │ │ │
│  │    └────────────┘              │           └─────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 2. File Organization & Structure
The infrastructure follows a modular single-directory approach with clear separation of concerns:

```bash
terraform/
├── .terraform/             # Provider downloads & state cache
├── scripts/                # Provisioning & utility scripts
├── backend.tf              # State management configuration
├── main.tf                 # Core infrastructure resources
├── monitoring.tf           # Observability & alerting
├── outputs.tf              # Exposed values & connection details
├── providers.tf            # Provider configurations
└── terraform.tf            # Version constraints & requirements
```

### 3. Required Tools Installation
**AWS CLI:**
[Install awscli depending on the OS](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html#getting-started-install-instructions)
```bash
# Install AWS CLI for macos
brew install awscli

# Configure AWS credentials
aws configure
```

**Terraform:**
[Install terraform depending on the OS](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli#install-terraform)
```bash
# macOS installation
brew install terraform

# Verify installation
terraform version
```

**configure aws credentiales:**

- `aws config` stores the credentials into 2 files at HOME/.aws/credentiales and HOME/.aws/config
- aws cofig asks you to enter USER credentials besides the region to use by default (eu-south-1)
- user should have access to EC2, S3, RDS, Cloud watch, Secrets manager

> [!NOTE]
> specifying the credentials within the aws provider block is highly discourged and not best practice. So the credentials must be specified within the bese class
>
> ```bash
> provider "aws" {
>   region     = "eu-south-1"
> }
> ```
>
> If the region not sepecified the default will be used from `HOME/.aws/config`

**PostgreSQL Client:**
[Install postgres client depending on the OS](https://www.postgresql.org/download/)
```bash
# Install PostgreSQL client tools
brew install postgresql

# Verify pg_isready command
# used for checking database health
pg_isready --version
```

**Manually created S3 bucket**
This bucket will be used to store the terraform infrastructure state.\I named the bucket as `epl-predictor-tf-state` so I will continue with this name.

---

### 4. Infrastructure Components

#### Core Resources

**Compute**:
**EC2 Instance:**
- t3.micro Ubuntu server for application hosting
- Key Pair: SSH access key for secure connection
- Security Group: Controls inbound/outbound traffic (SSH, HTTP, custom ports)

**Storage**:
- **S3 Buckets**: Separate buckets for MLflow artifacts and data storage
- **RDS PostgreSQL**: Managed database with multiple logical databases (MLFlow experiment tracking, actual app data)

**Networking**:
- **Default VPC:** Leverages existing AWS VPC infrastructure
- **DB Subnet Group**: Multi-AZ database placement
- **Security Groups**: Network access control between resources


#### IAM Roles & Policies
**EC2 Instance Role:**
Permissions:
- S3: Read/Write access to project buckets
- Secrets Manager: Retrieve database credentials
- CloudWatch: Send logs and metrics

```bash
resource "aws_iam_role" "ec2_s3_role" {
  name = "${local.project_name}-ec2-s3-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${local.project_name}-ec2-s3-role"
    Project     = local.project_name
  }
}

# IAM policy for S3 access
resource "aws_iam_role_policy" "ec2_s3_policy" {
  name = "${local.project_name}-ec2-s3-policy"
  role = aws_iam_role.ec2_s3_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.mlflow_artifacts.arn,
          "${aws_s3_bucket.mlflow_artifacts.arn}/*",
          aws_s3_bucket.data_storage.arn,
          "${aws_s3_bucket.data_storage.arn}/*"
        ]
      }
    ]
  })
}

# EC2 can access secrets manager
resource "aws_iam_role_policy" "ec2_secrets_policy" {
  name = "${local.project_name}-ec2-secrets-policy"
  role = aws_iam_role.ec2_s3_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.db_credentials.arn
        ]
      }
    ]
  })
}

# Instance profile for EC2
# Now EC2 can access S3 buckets, secrets manager
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${local.project_name}-ec2-profile"
  role = aws_iam_role.ec2_s3_role.name
}
```

**Policy Structure:**
- **Principle of Least Privilege**: Only necessary permissions granted
- **Resource-Specific**: Policies target specific buckets and secrets
- **No Wildcard Access**: Explicit resource ARNs used

#### Security Aspects

**Credential Management:**
- Database passwords stored in AWS Secrets Manager
- Random password generation with 16-character complexity
- No hardcoded credentials in code or configuration

**Network Security:**
- RDS accessible only from EC2 security group
- SSH access restricted to key-based authentication
- Database encryption at rest enabled

**Access Control:**
- IAM instance profiles for EC2-to-AWS service authentication
- Security group rules limit port access
- Database connections require SSL/TLS

---

### Monitoring & Observability
CloudWatch Integration
**Log Groups:**
- EC2 system logs with 7-day retention
- Application logs with 14-day retention

**Alarms:**
- CPU utilization monitoring (>80% threshold)
- RDS connection count tracking
- Database storage space monitoring

**Dashboard:**
- Unified view of infrastructure health
- Real-time metrics visualization
- Historical trend analysis

**Notifications:**
- SNS topic for alert delivery
- Email subscription for alarm notifications

---

### Advanced Terraform Techniques

#### State Management
```bash
# Remote state storage on S3
backend "s3" {
   bucket  = "epl-predictor-tf-state"
   key     = "terraform.tfstate"
   region  = "eu-south-1"
   encrypt = true
}
```

#### Provider Configuration
```bash
# Multi-provider setup
provider "aws" {
  region     = "eu-south-1"
}

provider "random" {}

provider "postgresql" {
  scheme          = "awspostgres"
  host            = aws_db_instance.postgres.address
  port            = aws_db_instance.postgres.port
  database        = aws_db_instance.postgres.db_name
  username        = aws_db_instance.postgres.username
  password        = random_password.db_password.result
  sslmode         = "require"
  connect_timeout = 15

  max_connections = 4
  expected_version = "17.4"
}
```

#### Null Resource Tricks
**Database Readiness Check:**

- Uses pg_isready command to verify RDS availability
- Implements retry logic with 30-second intervals
- Prevents PostgreSQL provider connection failures

```bash
resource "null_resource" "wait_for_db" {
   depends_on = [aws_db_instance.postgres]

   provisioner "local-exec" {
      command = <<-EOT
         echo "Waiting for database to be ready..."
         until pg_isready -h ${aws_db_instance.postgres.address} -p ${aws_db_instance.postgres.port} -U ${aws_db_instance.postgres.username}; do
         echo "Database not ready, waiting 30 seconds..."
         sleep 30
         done
         echo "Database is ready!"
      EOT
   }
}
```

**Random Suffix Generation:**

- Prevents Secrets Manager naming conflicts
- Enables infrastructure recreation without deletion wait periods
- Ensures globally unique S3 bucket names

```bash
resource "random_password" "db_password" {
   length           = 16
   special         = true
   upper           = true
   lower           = true
   numeric         = true
}

# Generate random suffix for unique naming
resource "random_id" "secret_suffix" {
   byte_length = 4
}
```

#### Local Values & Data Sources
```bash
# Centralized project naming
locals {
  project_name = "epl-predictions"
  account_id   = data.aws_caller_identity.current.account_id
}

# Dynamic VPC discovery
data "aws_vpc" "default" {
  default = true
}
```
---

### Deployment Commands
#### Initialization
```bash
cd terraform/
terraform init
terraform validate
terraform plan
```

#### Staged Deployment (to start with local testing and ML tracking)
```bash
terraform apply
   -target=aws_s3_bucket.mlflow_artifacts \
   -target=aws_s3_bucket.data_storage \
   -target=random_password.db_password \
   -target=aws_db_subnet_group.postgres_subnet_group \
   -target=aws_security_group.rds_sg \
   -target=aws_db_instance.postgres \
   -target=aws_secretsmanager_secret.db_credentials \
   -target=aws_secretsmanager_secret_version.db_credentials \
   -target=postgresql_database.mlflow_db \
   -target=postgresql_database.app_db \
   -target=postgresql_database.analytics_db
```

#### Complete Deployment
```bash
terraform apply
```

### Troubleshooting
#### Issue 1: Secrets Manager Conflict
```bash
# aws secrets manager doesn't remove the keys directly but waiting up to 30 days
Error: Secret with this name is already scheduled for deletion
```

You can run this command to check all available secrets even the scheduled for deletion ones
```bash
aws secretsmanager list-secrets --include-planned-deletion
```

**Solution**: Random suffix prevents conflicts
```bash
resource "random_id" "secret_suffix" {
   byte_length = 4
}

resource "aws_secretsmanager_secret" "db_credentials" {
   name        = "${local.project_name}-db-credentials-${random_id.secret_suffix.hex}"
   ...
   # Disable recovery to allow immediate deletion
   recovery_window_in_days = 0
}
```

#### Issue 2: Database under creation
This issue should be resolved by using the null_resource.wait_for_db
```bash
Error: PostgreSQL server not ready
```

Solution: Manually create mlflow_tracking database, in case this problem appeared again
```bash
# Wait for RDS (5-10 minutes), then:
pgcli -h $(terraform output -raw database_endpoint) -U postgres_admin -d epl-predictions

CREATE DATABASE mlflow_tracking;
```

> This infrastructure provides a complete, secure, and monitored environment optimized for AWS Free Tier usage while maintaining production-ready patterns and practices.
