variable "name" {
  description = "Name prefix."
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block."
  type        = string
}

variable "subnet_cidr" {
  description = "Subnet CIDR block."
  type        = string
}

variable "allowed_ssh_cidrs" {
  description = "CIDRs allowed to SSH."
  type        = list(string)
  default     = []
}
