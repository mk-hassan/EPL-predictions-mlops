# Outputs for EC2 instance details
output "instance_public_ip" {
  description = "Public IP of the EC2 instance"
  value       = aws_instance.app_host.public_ip
}

output "instance_ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i ~/.ssh/epl-app-key ubuntu@${aws_instance.app_host.public_ip}"
}

# Outputs for bucket names
output "mlflow_artifacts_bucket" {
  description = "Name of the MLflow artifacts S3 bucket"
  value       = aws_s3_bucket.mlflow_artifacts.bucket
}

output "data_storage_bucket" {
  description = "Name of the data storage S3 bucket"
  value       = aws_s3_bucket.data_storage.bucket
}

# Outputs for database connection
output "database_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "database_credentials" {
  description = "Database username"
  value       = {
    user_name = aws_db_instance.postgres.username
    password  = aws_db_instance.postgres.password
  }
  sensitive   = true
}

output "created_databases_names" {
  description = "Database names"
  value       = [
    aws_db_instance.postgres.db_name,
    postgresql_database.mlflow_db.name
  ]
}


# Outputs for monitoring
output "cloudwatch_dashboard_url" {
  description = "URL to CloudWatch Dashboard"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "sns_topic_arn" {
  description = "SNS topic ARN for alerts"
  value       = aws_sns_topic.alerts.arn
}

output "log_groups" {
  description = "CloudWatch log groups"
  value = {
    ec2_logs = aws_cloudwatch_log_group.ec2_logs.name
    app_logs = aws_cloudwatch_log_group.application_logs.name
  }
}

# Useful commands
output "get_database_credentials_command" {
  description = "Command to get database credentials"
  value       = "terraform output -raw database_credentials"
}

output "get_secrets_command" {
  description = "Command to get database credentials from Secrets Manager"
  value       = "aws secretsmanager get-secret-value --secret-id ${aws_secretsmanager_secret.db_credentials.name} --query SecretString --output text"
}
