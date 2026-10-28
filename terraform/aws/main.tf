# EXAMPLE infrastructure for CloudOps360 on AWS. Nothing here is applied automatically.
# Defaults are small (t3.micro, 8 GiB volumes, no NAT gateway). Review costs before `apply`.

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.tags
  }
}

locals {
  tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Purpose     = "portfolio-example"
    },
    var.extra_tags
  )
}

module "network" {
  source = "./modules/network"

  name              = var.project_name
  vpc_cidr          = var.vpc_cidr
  subnet_cidr       = var.subnet_cidr
  allowed_ssh_cidrs = var.allowed_ssh_cidrs
}

module "iam" {
  source = "./modules/iam"

  name = var.project_name
}

module "compute" {
  source = "./modules/compute"
  count  = var.enable_ec2 ? 1 : 0

  name                  = var.project_name
  subnet_id             = module.network.subnet_id
  security_group_ids    = [module.network.security_group_id]
  instance_profile_name = module.iam.instance_profile_name
  instance_type         = var.instance_type
  ami_id                = var.ami_id
  root_volume_size_gb   = var.root_volume_size_gb
  data_volume_size_gb   = var.data_volume_size_gb
  associate_public_ip   = var.associate_public_ip
}
