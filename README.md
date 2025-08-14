# EPL-Predictions: A Production-Ready Football Match Predictor (MLOps)

🏆 **EPL-Predictions** is a machine learning pipeline built to forecast English Premier League (EPL) match outcomes.

Unlike one-off models, this system mirrors the behavior of a live production service. It ingests new data as it's published, retrains models on a schedule, monitors for drift, and adapts predictions over time.

Data is sourced from [football-data.co.uk](https://www.football-data.co.uk/), a long-standing source of structured football statistics. It covers Premier League fixtures from the 1993–94 season to today, with updates published twice weekly. This project uses only top-tier matches (E0 league code).

<p align="center">
  <a title="Ank Kumar, CC BY-SA 4.0 &lt;https://creativecommons.org/licenses/by-sa/4.0&gt;, via Wikimedia Commons" href="https://commons.wikimedia.org/wiki/File:Premier_League_Trophy_at_Manchester%27s_National_Football_Museum_(Ank_Kumar)_03.jpg"><img width="256" alt="Premier League Trophy at Manchester&#039;s National Football Museum" src="https://upload.wikimedia.org/wikipedia/commons/thumb/5/51/Premier_League_Trophy_at_Manchester%27s_National_Football_Museum_%28Ank_Kumar%29_03.jpg/256px-Premier_League_Trophy_at_Manchester%27s_National_Football_Museum_%28Ank_Kumar%29_03.jpg?20210412094232"></a>
</p>

Here’s a look at some practical use cases for the 🏆 **EPL-Predictions** module:

| Use Case               | Stakeholders            | Outcomes |
| ---------------------- | ----------------------- | ------------------------------------------------ |
| Fantasy Sports         | Users, Operators        | Real-time lineup advice, higher engagement       |
| Broadcast & Media      | Producers, Commentators | Data-driven insights, better audience engagement |
| Sports Analytics Firms | Analysts, Coaches       | Scalable modeling, actionable reports            |

This project is **production-ready**, built with full-stack MLOps tools and designed to meet the needs of real-world systems. It integrates with modern infrastructure, runs reliably at scale, and reflects the kind of architecture used in enterprise and research settings.

This README outlines how to set up, deploy, and understand the system, with sections covering environment setup, infrastructure, pipelines, and other operational details.

It includes:

- A [Quickstart Guide](#quickstart-guide) for running the pipeline locally for testing, development, and experimentation.
- The [Data Source and Data Pipelines](#data-source-and-data-pipelines) section, which explains where the data comes from, how it's structured, and how it's processed using automated pipelines.
- The [Problem Type](#problem-type-multi-class-classification), [Classification Pipeline](#classification-pipeline-psuedocode), and [Technical Challenges](#technical-challenges) sections for understanding the modeling objective, how predictions are made, and the key engineering hurdles encountered during development.
- A [Cloud Deployment Guide](#cloud-deployment-guide) for setting up and managing AWS infrastructure with Terraform and Prefect.
- An [Infrastructure Overview](#infrastructure-overview), which details the architecture, IAM setup, monitoring layers, and security considerations.

## Quickstart Guide

To activate and install the dependencies for this project, follow these steps:
    
### 1. Set up your environment

Open a terminal and navigate to the project directory:

```bash
cd /path/to/EPL-predictions
```

Activate and install dependencies using Pipenv. If you have the `uv` installer, it’s recommended for faster and more reliable dependency installation:

```bash
export PIPENV_INSTALLER=uv
pipenv install
# Or to install all dependencies including development tools:
pipenv shell --dev
```

If you don’t have `uv`, Pipenv will fall back to `pip` automatically:

```bash
pipenv install
```

Activate the virtual environment:

```bash
pipenv shell
```

### 2. Initialize code quality checks (optional, but recommended)

Set up automated pre-commit hooks to ensure consistent code style and catch issues early:

- [x] Automatically runs code formatters (Black, isort, Ruff) on staged files before each commit.
- [x] Runs linters (pylint) and security scanners (Bandit) to check code quality and security.
- [x] Prevents commits if code does not meet quality or security standards.
- [x] Helps maintain consistent code style and catch issues early.

Install pre-commit and pre-commit hooks:

```bash
pipenv install --dev pre-commit
pre-commit install
```

(Optional) Add additional hooks for commit messages and pre-push:

```bash
pre-commit install --hook-type commit-msg --hook-type pre-push
```

To verify installed hooks:

```bash
ls .git/hooks | grep -v '\.sample$'
```

You can manually run all hooks on all files with:
```bash
pre-commit run --all
```

## Data Source and Data Pipelines

<p align="center">
  <a title="Markbarnes, CC BY-SA 3.0 &lt;http://creativecommons.org/licenses/by-sa/3.0/&gt;, via Wikimedia Commons" href="https://commons.wikimedia.org/wiki/File:Ryan_Valentine_scores.jpg"><img width="512" alt="The old Kop stand in the Racecourse Ground of Wrexham A.F.C." src="https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Ryan_Valentine_scores.jpg/512px-Ryan_Valentine_scores.jpg?20070518173434"></a>
</p>

### Data Source

The data powering this project comes from [football-data.co.uk](https://www.football-data.co.uk/), a reliable and structured source of historical English football statistics provided in CSV format.

#### League Division

Matches are classified by league codes that indicate the competition level:

* `E0` — English Premier League (top tier, **used exclusively in this project**)
* `E1` — English Championship (2nd tier)
* `E2` — English League One (3rd tier)
* `E3` — English League Two (4th tier)

This project focuses solely on Premier League fixtures (`E0`).

#### Dataset Coverage

The dataset spans from the 1993–94 season to the current season, with updates published twice weekly. It contains detailed match-level statistics, including results, team performance metrics, and betting odds where available.

#### Core Match Information

| Column          | Description                                            |
| --------------- | ------------------------------------------------------ |
| `Date`          | Match date (DD/MM/YY)                                  |
| `HomeTeam`      | Home team name                                         |
| `AwayTeam`      | Away team name                                         |
| `FTHG` / `FTAG` | Full-time goals for home and away                      |
| `FTR`           | Full-time result: H = home win, D = draw, A = away win |
| `HTHG` / `HTAG` | Half-time home/away goals                              |
| `HTR`           | Half-time result (H, D, A)                             |

#### Match Statistics (where available)

|Column                 | Description                         |
| --------------------- | ------------------------------- |
|`HS`, `AS`             | Shots by home / away teams      |
| `HST`, `AST`          | Shots on target for home / away |
| `HC`, `AC`            | Corner kicks for home / away    |
| `HF`, `AF`            | Fouls committed                 |
| `HY`, `AY`            | Yellow cards                    |
| `HR`, `AR`            | Red cards                       |

#### Betting Odds

Betting odds are included for many seasons and sourced from Bet365. Common fields include:

* B365H, B365D, B365A — Odds for home win, draw, and away win
* Closing odds (B365CH, B365CD, B365CA) may also be available for later seasons

### Data Pipelines

The project includes robust data ingestion pipelines built with Prefect for orchestration, supporting both local development and AWS cloud deployments.

Key Features:
- Automated data fetching from football-data.co.uk
- Smart caching and retry logic for reliability
- Fallback mechanisms (AWS → Local database when needed)
- Historical backfill capabilities for multiple seasons
- Transaction-safe database operations

Pipeline Types:
- AWS Pipeline: Cloud-based with S3 storage and RDS
- Local Pipeline: Development-friendly with local PostgreSQL
- Backfill functionality: Historical data processing

For detailed setup instructions, configuration options, and execution commands, see the [Pipelines Documentation](./pipelines/README.md).

## Problem Type: Multi-Class Classification

### Primary Task: Match Outcome Prediction

The classification task predicts the final match result (`full_time_result`) based on structured match data.

Target Variable: `full_time_result`
Classes:

  * `0` → Away Win (A)
  * `1` → Draw (D)
  * `2` → Home Win (H)

### What the App Solves



Given two teams, the model forecasts the likely outcome using engineered features and historical performance data.

Example Input:

```
Home Team: Manchester City
Away Team: Liverpool
```

Example Output:

```
Prediction: Home Win (H)
Confidence:
- Home Win: 45%
- Draw: 30%
- Away Win: 25%
```

## Classification Pipeline (Psuedocode)

```python
def predict_match_outcome(home_team, away_team):
    """Main classification function"""

    # 1. Feature Engineering
    features = engineer_features(home_team, away_team)

    # 2. Classification Model
    probabilities = classifier.predict_proba([features])
    prediction = classifier.predict([features])

    # 3. Return structured output
    return {
        'predicted_outcome': ['Away Win', 'Draw', 'Home Win'][prediction[0]],
        'probabilities': {
            'away_win': probabilities[0][0],
            'draw': probabilities[0][1],
            'home_win': probabilities[0][2]
        },
        'confidence': max(probabilities[0])
    }
```

## Technical Challenges

While collecting match-level data from [football-data.co.uk](https://www.football-data.co.uk/) across more than 25 seasons (2000–2025), several reliability and formatting issues emerged:

1. Inconsistent Date Formats – Seasons used different formats such as `DD/MM/YY`, `DD/MM/YYYY`, and `YYYY-MM-DD`.
2. Corrupted Files – Some CSVs were incomplete, improperly encoded, or failed to load.
3. Non-Deterministic Columns – Column names and availability varied significantly from season to season.

### Standardization and Schema Design

To address these inconsistencies, the project includes a discovery process (`pipelines/data_schema_analysis.py`) that scans all available season files and identifies only those columns that appear reliably across every year.

```python
# Pseudocode for column standardization
common_columns = set(first_season_columns)
for season in range(2000, 2025):
    try:
        df = fetch_season_data(season)
        common_columns = common_columns ∩ df.columns  # Intersection
    except CorruptedFileError:
        skip_season(season)

# Result: Only columns present in ALL seasons
final_columns = common_columns  # 27 reliable columns
```

The resulting list of 27 required columns is stored in `config/params.yaml` and includes identifiers, results, team stats, betting odds, and derived fields.

```yaml
required_columns:
  # Match identifiers: div, date, hometeam, awayteam, referee
  # Results: fthg, ftag, ftr, hthg, htag, htr
  # Statistics: hs, as, hst, ast, hc, ac, hf, af, hy, ay, hr, ar
  # Odds: whh, whd, wha
  # Derived: season
```

### Date Normalization

Date formats are normalized using helper logic in `pipelines/helpers.py`, which attempts multiple known formats and resolves ambiguity in 2-digit year representations.

```python
def parse_match_date(date_str):
    formats = ["%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y"]

    for format in formats:
        try:
            parsed_date = pd.to_datetime(date_str, format=format)
            if parsed_date.year < 1950:  # Fix 2-digit year ambiguity
                parsed_date += 100_years
            return parsed_date
        except:
            continue

    return pd.NaT  # Failed to parse
```

## Cloud Deployment Guide

- [Environment Prerequisites](#environment-prerequisites)
  - [AWS CLI](#aws-cli)
  - [Terraform](#terraform)
  - [PostgreSQL Client](#postgresql-client)
  - [S3 Bucket for Terraform State](#s3-bucket-for-terraform-state)
- [Implementation Steps](#implementation-steps)
  - [1. Initialize Terraform](#1-initialize-terraform)
  - [2. Staged Deployment (Optional)](#2-staged-deployment-optional)
  - [3. Complete Deployment](#3-complete-deployment)
- [Useful Outputs](#useful-outputs)
- [Troubleshooting](#troubleshooting)
  - [Issue 1: Secrets Manager Conflict](#issue-1-secrets-manager-conflict)
  - [Issue 2: Database Initialization Delay](#issue-2-database-initialization-delay)

### Environment Prerequisites

Before deploying infrastructure or running the application, ensure the following tools are installed and configured on your local machine.

#### AWS CLI

Install the AWS CLI for your operating system by following [the official instructions](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html#getting-started-install-instructions).

For macOS:

```bash
brew install awscli
```

Once installed, configure your AWS credentials:

```bash
aws configure
```

This command sets up two files in `~/.aws/`:

* `credentials`: Stores your access key and secret
* `config`: Defines your default region (e.g., `eu-south-1`)

Make sure the IAM user you're using has permissions for:

* EC2
* S3
* RDS
* Secrets Manager
* CloudWatch

> ⚠️ Best practice: Avoid hardcoding credentials in your Terraform code. Use environment-based configuration instead.

#### Terraform

Install Terraform via [official instructions](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli#install-terraform).

For macOS:

```bash
brew install terraform
```

Verify installation:

```bash
terraform version
```

#### PostgreSQL Client

Install the PostgreSQL client tools. These are required primarily to check database readiness via `pg_isready`.

For macOS:

```bash
brew install postgresql
```

Verify the CLI tools:

```bash
pg_isready --version
```

#### S3 Bucket for Terraform State

Create an S3 bucket that will hold the remote Terraform state. In this example, we use:

```
epl-predictor-tf-state
```

If you use a different name, be sure to update the `terraform/backend.tf` file accordingly:

```hcl
terraform {
  backend "s3" {
    bucket = "your-custom-bucket-name"
    ...
  }
}
```

This ensures that Terraform stores your infrastructure state remotely and can support team collaboration.

### Implementation Steps

#### 1. Initialize Terraform

Navigate to the `terraform/` directory and initialize the working directory. This sets up the backend and validates the configuration:

```bash
cd terraform
terraform init && terraform validate
```

#### 2. Staged Deployment (Optional)

To begin with core services—such as S3 for storage and RDS for local MLflow testing—you can deploy only a subset of resources:

```bash
terraform apply -auto-approve \
  -target=aws_s3_bucket.mlflow_artifacts \
  -target=aws_s3_bucket.data_storage \
  -target=aws_db_instance.postgres \
  -target=aws_secretsmanager_secret_version.db_credentials \
  -target=postgresql_database.mlflow_db
```

This is useful for early-stage development or running services locally without deploying the full application stack.

##### Optional: Using the Makefile

Common Terraform commands are wrapped in a Makefile for convenience. For example, to deploy base resources:

```bash
make apply-base-infra
```

#### 3. Complete Deployment

Once you're ready to deploy the complete infrastructure, run:

```bash
terraform apply
```

This will apply all modules and provision the entire production-ready environment.

### Useful Outputs

To access useful outputs like the MLflow tracking URI, use:

```bash
terraform output -raw get_mlflow_database_uri
```

For a full list of available outputs, refer to `terraform/output.tf` or run:

```bash
terraform output
```

Use the `-raw` flag when retrieving sensitive strings such as secrets or database URIs.

### Troubleshooting

#### Issue 1: Secrets Manager Conflict

When deleting AWS Secrets Manager secrets, you may see this error:

```bash
Error: Secret with this name is already scheduled for deletion
```

This happens because secrets are not removed immediately but after a waiting period (up to 30 days).

To view all secrets—including those pending deletion—run:

```bash
aws secretsmanager list-secrets --include-planned-deletion
```

**Solution:**
Add a random suffix to secret names to avoid conflicts and disable recovery for immediate deletion:

```hcl
resource "random_id" "secret_suffix" {
  byte_length = 4
}

resource "aws_secretsmanager_secret" "db_credentials" {
  name                     = "${local.project_name}-db-credentials-${random_id.secret_suffix.hex}"
  # ...
  recovery_window_in_days   = 0  # disables recovery, allows immediate deletion
}
```

#### Issue 2: Database Initialization Delay

If you encounter this error during deployment:

```bash
Error: PostgreSQL server not ready
```

It means the database is still being created.

**Solution:**

Wait 5–10 minutes for the RDS instance to be ready, then manually create the required database:

```bash
pgcli -h $(terraform output -raw database_endpoint) -U postgres_admin -d epl-predictions

CREATE DATABASE mlflow_tracking;
```

Using `null_resource.wait_for_db` in Terraform can help automate this wait step.

## Infrastructure Overview

- [Infrastructure Architecture](#infrastructure-architecture)
- [File Organization and Structure](#file-organization-and-structure)
- [Infrastructure Components](#infrastructure-components)
- [IAM Roles and Policies](#iam-roles-and-policies)
- [Security Features](#security-features)
- [Monitoring and Observability](#monitoring--observability)
- [Advanced Terraform Techniques](#advanced-terraform-techniques)

### Infrastructure Architecture


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

### File Organization and Structure

The Terraform project follows a modular, single-directory layout with separation of concerns:

```
terraform/
├── backend.tf
├── main.tf
├── monitoring.tf
├── outputs.tf
├── providers.tf
├── scripts/
│   ├── database_check.sh
│   └── user_data.sh
└── terraform.tf
```

### Infrastructure Components

#### Compute

EC2 Instance:

* `t3.micro` Ubuntu server for application hosting
* SSH Key Pair for secure remote access
* Security Group allowing SSH and HTTP traffic
* IAM Role for accessing other AWS services

#### Storage

S3 Buckets:

* `mlflow_artifacts`: For experiment tracking data
* `data_storage`: For project dataset storage

RDS PostgreSQL:

* Managed instance
* Multi-database setup (e.g., `mlflow_tracking`, `epl_data`)
* Encrypted and password-protected

#### Networking

* Uses Default VPC
* Subnet Group for RDS (multi-AZ deployment)
* Security Groups to isolate EC2 and RDS access

### IAM Roles and Policies

#### EC2 IAM Role

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

### Security Aspects

**Credential Management:**
- Database passwords stored in AWS Secrets Manager
> [!NOTE] Access credentials using
> After applying the infrastructure
> ```bash
> aws secretsmanager get-secret-value \
> --secret-id ${aws_secretsmanager_secret.db_credentials.name} \
> --query SecretString --output text
> ```
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

### Monitoring & Observability

**CloudWatch** Integration

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
