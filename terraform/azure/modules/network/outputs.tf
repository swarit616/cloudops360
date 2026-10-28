output "vnet_id" {
  description = "Virtual network id."
  value       = azurerm_virtual_network.this.id
}

output "subnet_id" {
  description = "Subnet id."
  value       = azurerm_subnet.this.id
}

output "nsg_id" {
  description = "Network security group id."
  value       = azurerm_network_security_group.this.id
}
