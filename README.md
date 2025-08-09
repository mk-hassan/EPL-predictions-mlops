# 🏆 EPL-Predictions: A Production-Ready Football Match Predictor

##  Overview
This project is a **full-stack Machine Learning Operations (MLOps)** pipeline designed to predict outcomes of **English Premier League (EPL)** football matches. It uses historical and regularly updated match-level data, with a focus on engineering a system that automates **data ingestion**, **model training**, **model monitoring**, and **deployment**.

Rather than being a one-shot model, this project simulates a production environment where new match data is released **weekly or monthly**, and the system **retrains models**, **detects drift**, and **monitors performance** over time.


## Data Source

> [!TIP]
> League Division refers to the specific league or division the match belongs to.
This field helps identify which football competition the data is sourced from.
>
> Common league codes in the dataset:\
> **E0** → English Premier League (Top tier) [Only used]\
> **E1** → English Championship (2nd tier)\
> **E2** → English League One (3rd tier)\
> **E3** → English League Two (4th tier)
>
> ✅ In this project, we primarily focus on E0 (Premier League).

Data relies on [`football-data.co.uk`](https://www.football-data.co.uk/) — a well-maintained, structured source of historical EPL results and stats provided in csv format.

This dataset provides match-level statistics for Premier League fixtures spanning from at least the 1993/94 season up to the current season, updated twice weekly.

### 🧩 Core Game Info
| Column          | Description                                            |
| --------------- | ------------------------------------------------------ |
| `Date`          | Match date (DD/MM/YY)                                  |
| `HomeTeam`      | Home team name                                         |
| `AwayTeam`      | Away team name                                         |
| `FTHG` / `FTAG` | Full-time goals for home and away                      |
| `FTR`           | Full-time result: H = home win, D = draw, A = away win |
| `HTHG` / `HTAG` | Half-time home/away goals                              |
| `HTR`           | Half-time result (H, D, A)                             |

### 📊 Match Statistics (where available)
|Column                 | Meaning                         |
| --------------------- | ------------------------------- |
|`HS`, `AS`             | Shots by home / away teams      |
| `HST`, `AST`          | Shots on target for home / away |
| `HC`, `AC`            | Corner kicks for home / away    |
| `HF`, `AF`            | Fouls committed                 |
| `HY`, `AY`            | Yellow cards                    |
| `HR`, `AR`            | Red cards                       |


### 🎯 Betting Odds (if present)
Depending on season file:

B365H, B365D, B365A = Bet365 odds (home win, draw, away win)

May include closing odds (B365CH, B365CD, B365CA) for later seasons


## 🚧 Data Challenges & Solutions

### Challenges Faced
During data collection from football-data.co.uk spanning 25+ seasons (2000-2025), several issues emerged:

1. **📅 Inconsistent Date Formats**: Different seasons used varying date formats (`DD/MM/YY`, `DD/MM/YYYY`, `YYYY-MM-DD`)
2. **💾 Corrupted Files**: Some season files were incomplete or had encoding issues
3. **📊 Non-Deterministic Columns**: Column availability varied significantly across seasons

### Solution Approach

**Data Discovery (`pipelines/data_schema_analysis.py`)**:
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

**Required Columns Found** (`config/params.yaml`):
After analysis, these **27 columns** are consistently available across all seasons:
```yaml
required_columns:
  # Match identifiers: div, date, hometeam, awayteam, referee
  # Results: fthg, ftag, ftr, hthg, htag, htr
  # Statistics: hs, as, hst, ast, hc, ac, hf, af, hy, ay, hr, ar
  # Odds: whh, whd, wha
  # Derived: season
```

**Date Parsing (`pipelines/helpers.py`)**:
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

**Result**: Robust data pipeline handling 25+ seasons with consistent schema and reliable date parsing.

---

##  Technologies Used
| Purpose             | Tools / Stack                                         |
| ------------------- | ------------------------------------------------------|
| Language            | Python 3.11                                           |
| Orchestration       | Prefect                                               |
| Monitoring          | Grafana, Loki, Mimir, Tempo, Evidently                |
| Infrastructure      | Terraform                                             |
| Deployment          | Docker, AWS (ECS, S3, RDS, VPC, Secrets Manager, IAM) |
| Experiment Tracking | MLflow                                                |
| Linting             | pylint, Ruff, Black, isort, bandit, pre-commit        |
| Development Tools   | Commitizen, MakeFile                                  |
| Testing             | pytest, TestContainer                                 |
| CI/CD               | GitHub Actions                                        |
|


## Problem Type: Multi-Class Classification

### Primary Task: Match Outcome Prediction
- **Target Variable:** full_time_result
- **Classes:**
  - 0 = Away Win (A)
  - 1 = Draw (D)
  - 2 = Home Win (H)

### What the App Solves:
**Given two team names, predict the most likely match outcome**

Input:
```
Home Team: Manchester City
Away Team: Liverpool
```
Output:
```
Prediction: Home Win (H)
Confidence:
- Home Win: 45%
- Draw: 30%
- Away Win: 25%
```
### Classification Pipeline (Psudo)

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

## Setting Up the Environment

To activate and install the dependencies for this project, follow these steps:

1. **Activate Pipenv Shell**
   Open your terminal and navigate to the project directory:
   ```bash
   > cd /path/to/EPL-predictions
   ```

2. **Install Dependencies Using uv (Recommended)**
   If you have `uv` installed, set the environment variable and run:
   ```bash
   > export PIPENV_INSTALLER=uv
   > pipenv install
    # or install all including dev dependancies
   > pipenv shell --dev
   ```
   This will use `uv` for faster and more reliable dependency installation.

3. **If uv Is Not Found**
   If you do not have `uv` installed, Pipenv will fall back to using `pip`.
   You can install dependencies normally:
   ```bash
   > pipenv install
   ```

4. **Activate the Virtual Environment**
   After installation, activate the environment:
   ```bash
   > pipenv shell
   ```

This will set up all required packages as specified in the `Pipfile` and locking the dependancies on `Pipfile.lock`.

---

## Initializing Pre-commit Hooks

To enable automated code quality and security checks before each commit, initialize pre-commit in your project:

### Setup Tasks

- **Install pre-commit (if not already installed [dev dependancies]):**
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

This section provides a comprehensive overview of the Terraform-managed infrastructure for the EPL Predictions project, emphasizing architectural decisions, best practices, and organizational patterns.

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
├── backend.tf
├── main.tf
├── monitoring.tf
├── outputs.tf
├── providers.tf
├── scripts
│   ├── database_check.sh
│   └── user_data.sh
└── terraform.tf
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

- `aws config` stores the credentials into 2 files at `$HOME/.aws/credentiales` and `$HOME/.aws/config`
- aws cofig asks you to enter `USER` credentials besides the region to use by default, I used `eu-south-1` as it the nearest for me but you should use the appropriate region nearest to your location.
- `USER` should have access to EC2, S3, RDS, Cloud watch, Secrets manager

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
# Install PostgreSQL client tools, needed just pg_isready tool to test connectivity (See null_resource.wait_for_db)
brew install postgresql

# Verify pg_isready command
# used for checking database health
pg_isready --version
```

**Manually created S3 bucket** \
This bucket will be used to store the terraform infrastructure state.\I named the bucket as `epl-predictor-tf-state` so I will continue with this name.

if you named your bucket another name, please update `terraform/backend.tf` with the bucket name
```bash
terraform {
  backend "s3" {
    bucket  = # bucket name
    ...
  }
}
```
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
- **RDS PostgreSQL**: Managed database with multiple logical databases (MLFlow experiment tracking, actual app data as `Data warehouse`)

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

---

#### Monitoring & Observability
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

---

#### Advanced Terraform Techniques

##### State Management
```bash
# Remote state storage on S3
backend "s3" {
  bucket  = "epl-predictor-tf-state"
  key     = "terraform.tfstate"
  region  = "eu-south-1"
  encrypt = true
}
```

##### Provider Configuration
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

##### Null Resource Tricks
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

##### Local Values & Data Sources
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

#### Deployment Commands
##### Initialization
```bash
cd terraform
# Init terraform state
terraform init && terraform validate
```

##### Staged Deployment (to start with local testing and ML tracking)
```bash
# Apply the base resources
terraform apply -auto-approve \
		-target=aws_s3_bucket.mlflow_artifacts \
		-target=aws_s3_bucket.data_storage \
		-target=aws_db_instance.postgres \
		-target=aws_secretsmanager_secret_version.db_credentials \
		-target=postgresql_database.mlflow_db
```

**OR** you can simply use `MakeFile`
```bash
make apply-base-infra
```

##### Complete Deployment
```bash
terraform apply
```

#### Useful outputs
```bash
# mlflow server backend-uri
terraform output -raw get_mlflow_database_uri
```
> [!NOTE]
> For complete List of outputs lookat `terraform/output.tf` \
> Use `terraform output <output-name>` and use option `-raw` for **sensitive** outputs

#### Troubleshooting
##### Issue 1: Secrets Manager Conflict
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

##### Issue 2: Database under creation
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

---

## 🔄 Data Pipelines

The project includes robust **data ingestion pipelines** built with Prefect for orchestration, supporting both local development and AWS cloud deployments.

**Key Features:**
- **Automated data fetching** from football-data.co.uk
- **Smart caching** and retry logic for reliability
- **Fallback mechanisms** (AWS → Local database when needed)
- **Historical backfill** capabilities for multiple seasons
- **Transaction-safe** database operations

**Pipeline Types:**
- **AWS Pipeline**: Cloud-based with S3 storage and RDS
- **Local Pipeline**: Development-friendly with local PostgreSQL
- **Backfill functionality**: Historical data processing

For detailed setup instructions, configuration options, and execution commands, see the [**Pipelines Documentation**](./pipelines/README.md).

---
