variable "name" {
  description = "Name prefix."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group to create resources in."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "vnet_cidr" {
  description = "Virtual network address space."
  type        = string
}

variable "subnet_cidr" {
  description = "Subnet address prefix."
  type        = string
}

variable "allowed_ssh_cidrs" {
  description = "CIDRs allowed to SSH."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags for all resources."
  type        = map(string)
  default     = {}
}
