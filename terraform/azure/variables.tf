variable "subscription_id" {
  description = "Azure subscription id. Null = ARM_SUBSCRIPTION_ID or the active az login subscription."
  type        = string
  default     = null
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "eastus"
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

variable "vnet_cidr" {
  description = "Address space of the virtual network."
  type        = string
  default     = "10.30.0.0/16"
}

variable "subnet_cidr" {
  description = "Address prefix of the subnet."
  type        = string
  default     = "10.30.1.0/24"
}

variable "allowed_ssh_cidrs" {
  description = "CIDR blocks allowed to SSH (needs a route to the VM). Empty (default) = no inbound rule."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for cidr in var.allowed_ssh_cidrs : cidr != "0.0.0.0/0" && cidr != "*"])
    error_message = "Do not open SSH to the whole internet. Use your own /32."
  }
}

variable "enable_vm" {
  description = "Create the Linux VM and managed disk. Set to false to plan only the network."
  type        = bool
  default     = true
}

variable "vm_size" {
  description = "VM size (kept small to limit cost)."
  type        = string
  default     = "Standard_B1s"
}

variable "admin_username" {
  description = "Admin user name for the VM."
  type        = string
  default     = "azureuser"
}

variable "admin_ssh_public_key" {
  description = "SSH public key for the admin user (password login is disabled). Example: contents of ~/.ssh/id_ed25519.pub"
  type        = string
}

variable "os_disk_size_gb" {
  description = "OS disk size in GiB (Ubuntu image needs at least 30)."
  type        = number
  default     = 30
}

variable "data_disk_size_gb" {
  description = "Managed data disk size in GiB."
  type        = number
  default     = 8
}

variable "extra_tags" {
  description = "Additional tags for all resources."
  type        = map(string)
  default     = {}
}
