terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Store state in S3 — create the bucket manually once before first apply
  backend "s3" {
    bucket         = "mokshagpt-terraform-state"
    key            = "backend/terraform.tfstate"
    region         = "ap-south-1"
    encrypt        = true
    dynamodb_table = "mokshagpt-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
}

# ── Data sources ──────────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
  name       = "mokshagpt-backend"
  tags = {
    Project     = "mokshagpt"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
