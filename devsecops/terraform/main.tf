#TF Configuration for AWS S3 Bucket

#Warning: This is intentionally Misconfigured

terraform {
  
  required_providers {
    aws={
        source = "hashicorp/aws"
        version = "~>5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

#S3 bucket for app data

resource "aws_s3_bucket" "app_data" {
  bucket = "devsecops-learning-bucket-${random_id.bucket_suffix.hex}"
  tags = {
    Name = "Application Data Bucket"
    Environment = "Dev"
  }
}

#Security Issue: PUBLIC ACCESS ENABLED! IF WE PUT FALSE, BUCKET IS PUBLIC

/*resource "aws_s3_bucket_public_access_block" "app_data" {
  bucket = aws_s3_bucket.app_data
  block_public_acls = false
  block_public_policy = false
  ignore_public_acls = false
  restrict_public_buckets = false
}*/

resource "aws_s3_bucket_public_access_block" "app_data" {
  bucket = aws_s3_bucket.app_data
  block_public_acls = true
  block_public_policy = true
  ignore_public_acls = true
  restrict_public_buckets = true
}

# Random suffix to ensure unique bucket name
resource "random_id" "bucket_suffix" {
  byte_length = 4
}