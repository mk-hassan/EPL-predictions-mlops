
terraform {
  required_version = ">= 1.2"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.92"
    }

    random = {
      source = "hashicorp/random"
      version = "~> 3.7.2"
    }

    postgresql = {
      source = "cyrilgdn/postgresql"
      version = "~> 1.25.0"
    }
  }
}
