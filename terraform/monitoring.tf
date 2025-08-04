# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "ec2_logs" {
  name              = "/aws/ec2/${local.project_name}"
  retention_in_days = 7

  tags = {
    Name        = "${local.project_name}-ec2-logs"
    Project     = local.project_name
    Environment = "dev"
  }
}

resource "aws_cloudwatch_log_group" "application_logs" {
  name              = "/aws/application/${local.project_name}"
  retention_in_days = 14

  tags = {
    Name        = "${local.project_name}-app-logs"
    Project     = local.project_name
    Environment = "dev"
  }
}

# CloudWatch Alarms for EC2
resource "aws_cloudwatch_metric_alarm" "ec2_cpu_high" {
  alarm_name          = "${local.project_name}-ec2-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors ec2 cpu utilization"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    InstanceId = aws_instance.app_host.id
  }

  tags = {
    Name        = "${local.project_name}-ec2-cpu-alarm"
    Project     = local.project_name
    Environment = "dev"
  }
}

resource "aws_cloudwatch_metric_alarm" "ec2_status_check" {
  alarm_name          = "${local.project_name}-ec2-status-check"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Maximum"
  threshold           = "0"
  alarm_description   = "This metric monitors ec2 status check"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    InstanceId = aws_instance.app_host.id
  }

  tags = {
    Name        = "${local.project_name}-ec2-status-alarm"
    Project     = local.project_name
    Environment = "dev"
  }
}

# CloudWatch Alarms for RDS
resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "${local.project_name}-rds-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "75"
  alarm_description   = "This metric monitors RDS cpu utilization"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.postgres.id
  }

  tags = {
    Name        = "${local.project_name}-rds-cpu-alarm"
    Project     = local.project_name
    Environment = "dev"
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  alarm_name          = "${local.project_name}-rds-free-storage-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "2000000000" # 2GB in bytes
  alarm_description   = "This metric monitors RDS free storage space"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.postgres.id
  }

  tags = {
    Name        = "${local.project_name}-rds-storage-alarm"
    Project     = local.project_name
    Environment = "dev"
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_connection_count" {
  alarm_name          = "${local.project_name}-rds-connection-count-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "15"
  alarm_description   = "This metric monitors RDS connection count"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.postgres.id
  }

  tags = {
    Name        = "${local.project_name}-rds-connections-alarm"
    Project     = local.project_name
    Environment = "dev"
  }
}

# SNS Topic for alerts
resource "aws_sns_topic" "alerts" {
  name = "${local.project_name}-alerts"

  tags = {
    Name        = "${local.project_name}-alerts"
    Project     = local.project_name
    Environment = "dev"
  }
}

# SNS Topic Subscription (replace with your email)
resource "aws_sns_topic_subscription" "email_alerts" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = "mk.bayumi@gmail.com"
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.project_name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/EC2", "CPUUtilization", "InstanceId", aws_instance.app_host.id],
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_db_instance.postgres.id]
          ]
          period = 300
          stat   = "Average"
          region = "us-east-1"  # Replace with your region
          title  = "CPU Utilization"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", aws_db_instance.postgres.id],
            ["AWS/RDS", "FreeStorageSpace", "DBInstanceIdentifier", aws_db_instance.postgres.id]
          ]
          period = 300
          stat   = "Average"
          region = "us-east-1"  # Replace with your region
          title  = "RDS Metrics"
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 12
        width  = 24
        height = 6

        properties = {
          query   = "SOURCE '/aws/ec2/${local.project_name}'\n| fields @timestamp, @message\n| sort @timestamp desc\n| limit 100"
          region  = "us-east-1"  # Replace with your region
          title   = "Recent EC2 Logs"
          view    = "table"
        }
      }
    ]
  })
}

# Update IAM role to include CloudWatch permissions
resource "aws_iam_role_policy" "ec2_cloudwatch_policy" {
  name = "${local.project_name}-ec2-cloudwatch-policy"
  role = aws_iam_role.ec2_s3_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "ec2:DescribeVolumes",
          "ec2:DescribeTags",
          "logs:PutLogEvents",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:DescribeLogStreams",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

# Custom metric for application health
resource "aws_cloudwatch_log_metric_filter" "error_count" {
  name           = "${local.project_name}-error-count"
  log_group_name = aws_cloudwatch_log_group.application_logs.name
  pattern        = "ERROR"

  metric_transformation {
    name      = "ErrorCount"
    namespace = "${local.project_name}/Application"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "application_errors" {
  alarm_name          = "${local.project_name}-application-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ErrorCount"
  namespace           = "${local.project_name}/Application"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors application errors"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Name        = "${local.project_name}-app-error-alarm"
    Project     = local.project_name
    Environment = "dev"
  }
}
