variable "name" {
  description = "Name prefix."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group name."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "subnet_id" {
  description = "Subnet id for the network interface."
  type        = string
}

variable "vm_size" {
  description = "VM size."
  type        = string
}

variable "admin_username" {
  description = "Admin user name."
  type        = string
}

variable "admin_ssh_public_key" {
  description = "SSH public key."
  type        = string
}

variable "os_disk_size_gb" {
  description = "OS disk size in GiB."
  type        = number
}

variable "data_disk_size_gb" {
  description = "Data disk size in GiB."
  type        = number
}

variable "tags" {
  description = "Tags for all resources."
  type        = map(string)
  default     = {}
}
