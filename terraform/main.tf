
data "aws_caller_identity" "current_identity" {}

locals {
  account_id   = data.aws_caller_identity.current_identity.account_id
  project_name = "epl-predictions"
}

data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  owners = ["099720109477"] # Canonical
}

resource "aws_key_pair" "deployer" {
  key_name   = "${local.project_name}-deployer-key"
  public_key = file("~/.ssh/epl-app-key.pub")

  tags = {
    Name        = "${local.project_name}-deployer-key"
    Project     = local.project_name
  }
}

resource "aws_security_group" "ec2_sg" {
  name        = "${local.project_name}-ec2-sg"
  description = "Allow SSH"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Application Port"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# S3 bucket for MLflow artifacts (models, plots, etc.)
resource "aws_s3_bucket" "mlflow_artifacts" {
  bucket = "${local.project_name}-mlflow-artifacts-${local.account_id}"

  tags = {
    Name        = "${local.project_name}-mlflow-artifacts"
    Project     = local.project_name
    Purpose     = "MLflow artifacts storage"
  }
}

# S3 bucket for data storage (raw data, processed datasets)
resource "aws_s3_bucket" "data_storage" {
  bucket = "${local.project_name}-data-storage-${local.account_id}"

  tags = {
    Name        = "${local.project_name}-data-storage"
    Project     = local.project_name
    Purpose     = "Data storage"
  }
}

# IAM role for EC2 to access S3 buckets
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

# Instance profile for EC2
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${local.project_name}-ec2-profile"
  role = aws_iam_role.ec2_s3_role.name
}

resource "aws_instance" "app_host" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"
  key_name      = aws_key_pair.deployer.key_name

  vpc_security_group_ids = [aws_security_group.ec2_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  user_data = base64encode(templatefile("${path.module}/scripts/user_data.sh", {
    project_name = local.project_name
    mlflow_artifacts_bucket = aws_s3_bucket.mlflow_artifacts.bucket
    data_storage_bucket    = aws_s3_bucket.data_storage.bucket
  }))

  tags = {
    Name        = "${local.project_name}-app"
    Project     = local.project_name
  }
}

# Initializing RDS PostgreSQL database
# Generate a random password for the database
resource "random_password" "db_password" {
  length           = 16
  special         = true
  upper           = true
  lower           = true
  numeric         = true
}

# DB subnet group for RDS (uses default VPC subnets)
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_db_subnet_group" "postgres_subnet_group" {
  name       = "${local.project_name}-db-subnet-group"
  subnet_ids = data.aws_subnets.default.ids

  tags = {
    Name        = "${local.project_name}-db-subnet-group"
    Project     = local.project_name
  }
}

# Security group for RDS
resource "aws_security_group" "rds_sg" {
  name        = "${local.project_name}-rds-sg"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = data.aws_vpc.default.id

  # Allow PostgreSQL access from EC2 security group
  ingress {
    description     = "PostgreSQL from EC2"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2_sg.id]
  }

  # Allow PostgreSQL access from anywhere (for development - remove in production)
  ingress {
    description = "PostgreSQL public access"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${local.project_name}-rds-sg"
    Project     = local.project_name
  }
}

# RDS PostgreSQL instance
resource "aws_db_instance" "postgres" {
  identifier = "${local.project_name}-app"

  # Database configuration
  engine         = "postgres"
  engine_version = "17.4"
  instance_class = "db.t3.micro"

  # Storage
  allocated_storage     = 5
  max_allocated_storage = 20
  storage_type         = "gp2"
  storage_encrypted    = true

  # Database name and credentials
  db_name  = replace("${local.project_name}", "-", "_")
  username = "postgres_admin"
  password = random_password.db_password.result

  # Network configuration
  db_subnet_group_name   = aws_db_subnet_group.postgres_subnet_group.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  publicly_accessible    = true  # Set to false for production

  # Backup and maintenance
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"

  # Disable deletion protection for development
  deletion_protection = false
  skip_final_snapshot = true

  tags = {
    Name        = "${local.project_name}-postgres"
    Project     = local.project_name
  }
}

# Generate random suffix for unique naming
resource "random_id" "secret_suffix" {
  byte_length = 4
}

# Store database password in AWS Secrets Manager
resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "${local.project_name}-db-credentials-${random_id.secret_suffix.hex}"
  description = "Database credentials for ${local.project_name}"
  recovery_window_in_days = 0 # Disable recovery to allow immediate deletion

  tags = {
    Name        = "${local.project_name}-db-credentials"
    Project     = local.project_name
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = aws_db_instance.postgres.username
    password = random_password.db_password.result
    host     = aws_db_instance.postgres.address
    port     = aws_db_instance.postgres.port
    dbname   = aws_db_instance.postgres.db_name
  })
}

# Update IAM policy to include Secrets Manager access
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

# Add a null resource to wait for RDS availability
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

# Create additional databases
resource "postgresql_database" "mlflow_db" {
  name  = "mlflow"
  owner = aws_db_instance.postgres.username

  depends_on = [
    aws_db_instance.postgres,
    null_resource.wait_for_db
  ]
}
