variable "region" {
  description = "AWS region to deploy the example into."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name prefix for all resources."
  type        = string
  default     = "cloudops360-example"
}

variable "environment" {
  description = "Environment tag."
  type        = string
  default     = "example"
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "subnet_cidr" {
  description = "CIDR block of the subnet."
  type        = string
  default     = "10.20.1.0/24"
}

variable "allowed_ssh_cidrs" {
  description = "CIDR blocks allowed to SSH to the instance. Empty (default) = no SSH; use SSM Session Manager."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for cidr in var.allowed_ssh_cidrs : cidr != "0.0.0.0/0"])
    error_message = "Do not open SSH to the whole internet (0.0.0.0/0). Use your own /32."
  }
}

variable "enable_ec2" {
  description = "Create the EC2 instance and EBS volume. Set to false to plan only the network and IAM."
  type        = bool
  default     = true
}

variable "instance_type" {
  description = "EC2 instance type (kept small to limit cost)."
  type        = string
  default     = "t3.micro"
}

variable "ami_id" {
  description = "Optional AMI id. Empty = latest Amazon Linux 2023."
  type        = string
  default     = ""
}

variable "root_volume_size_gb" {
  description = "Root EBS volume size in GiB."
  type        = number
  default     = 8
}

variable "data_volume_size_gb" {
  description = "Additional encrypted EBS data volume size in GiB."
  type        = number
  default     = 8
}

variable "associate_public_ip" {
  description = "Give the instance a public IPv4 address (needed for SSM without VPC endpoints; small hourly charge)."
  type        = bool
  default     = true
}

variable "extra_tags" {
  description = "Additional tags for all resources."
  type        = map(string)
  default     = {}
}
