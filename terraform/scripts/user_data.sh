#!/bin/bash
# user_data.sh

echo "Setting up ${project_name} app..."

apt update -y
apt upgrade -y

# Install necessary packages
apt install -y docker.io python3-pip

systemctl start docker
systemctl enable docker

# Add ubuntu user to docker group
usermod -aG docker ubuntu

# Configure AWS CLI environment variables
echo "export DATA_STORAGE_BUCKET=${data_storage_bucket}" >> /home/ubuntu/.bashrc
echo "export MLFLOW_ARTIFACTS_BUCKET=${mlflow_artifacts_bucket}" >> /home/ubuntu/.bashrc
echo "export PROJECT_NAME=${project_name}" >> /home/ubuntu/.bashrc

source ~/.bashrc

# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
dpkg -i -E amazon-cloudwatch-agent.deb

# Configure CloudWatch agent
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << 'EOF'
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "cwagent"
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/syslog",
            "log_group_name": "/aws/ec2/${project_name}",
            "log_stream_name": "{instance_id}/syslog"
          },
          {
            "file_path": "/var/log/auth.log",
            "log_group_name": "/aws/ec2/${project_name}",
            "log_stream_name": "{instance_id}/auth"
          },
          {
            "file_path": "/home/ubuntu/${project_name}/logs/app.log",
            "log_group_name": "/aws/application/${project_name}",
            "log_stream_name": "{instance_id}/application"
          }
        ]
      }
    }
  },
  "metrics": {
    "namespace": "CWAgent",
    "metrics_collected": {
      "cpu": {
        "measurement": [
          "cpu_usage_idle",
          "cpu_usage_iowait",
          "cpu_usage_user",
          "cpu_usage_system"
        ],
        "metrics_collection_interval": 60
      },
      "disk": {
        "measurement": [
          "used_percent"
        ],
        "metrics_collection_interval": 60,
        "resources": [
          "*"
        ]
      },
      "diskio": {
        "measurement": [
          "io_time"
        ],
        "metrics_collection_interval": 60,
        "resources": [
          "*"
        ]
      },
      "mem": {
        "measurement": [
          "mem_used_percent"
        ],
        "metrics_collection_interval": 60
      }
    }
  }
}
EOF

# Start CloudWatch agent
systemctl enable amazon-cloudwatch-agent
systemctl start amazon-cloudwatch-agent

# Create application log directory
mkdir -p /home/ubuntu/${project_name}/logs
chown ubuntu:ubuntu /home/ubuntu/${project_name}/logs


echo "CloudWatch monitoring configured!"
echo "Setup complete for ${project_name}!"
echo "Data storage bucket: ${data_storage_bucket}"
echo "MLflow artifacts bucket: ${mlflow_artifacts_bucket}"
