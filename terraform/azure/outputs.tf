output "resource_group_name" {
  description = "Resource group name."
  value       = azurerm_resource_group.this.name
}

output "vnet_id" {
  description = "Virtual network id."
  value       = module.network.vnet_id
}

output "subnet_id" {
  description = "Subnet id."
  value       = module.network.subnet_id
}

output "nsg_id" {
  description = "Network security group id."
  value       = module.network.nsg_id
}

output "vm_id" {
  description = "Linux VM id (null when enable_vm = false)."
  value       = one(module.compute[*].vm_id)
}

output "data_disk_id" {
  description = "Managed data disk id (null when enable_vm = false)."
  value       = one(module.compute[*].data_disk_id)
}
