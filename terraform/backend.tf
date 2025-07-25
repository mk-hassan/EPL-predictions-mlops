
terraform {
  backend "s3" {
    bucket  = "epl-predictor-tf-state"
    key     = "terraform.tfstate"
    region  = "eu-south-1"
    encrypt = true
  }
}
