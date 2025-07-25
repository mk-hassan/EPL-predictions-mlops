
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
