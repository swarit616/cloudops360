variable "name" {
  description = "Name prefix."
  type        = string
}

variable "subnet_id" {
  description = "Subnet to launch into."
  type        = string
}

variable "security_group_ids" {
  description = "Security groups for the instance."
  type        = list(string)
}

variable "instance_profile_name" {
  description = "IAM instance profile name."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type."
  type        = string
}

variable "ami_id" {
  description = "AMI id; empty = latest Amazon Linux 2023."
  type        = string
  default     = ""
}

variable "root_volume_size_gb" {
  description = "Root volume size in GiB."
  type        = number
}

variable "data_volume_size_gb" {
  description = "Data volume size in GiB."
  type        = number
}

variable "associate_public_ip" {
  description = "Associate a public IPv4 address."
  type        = bool
}
