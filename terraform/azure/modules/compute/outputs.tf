output "vm_id" {
  description = "Linux VM id."
  value       = azurerm_linux_virtual_machine.this.id
}

output "data_disk_id" {
  description = "Managed data disk id."
  value       = azurerm_managed_disk.data.id
}
