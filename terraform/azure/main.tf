# EXAMPLE infrastructure for CloudOps360 on Azure. Nothing here is applied automatically.
# Defaults are small (Standard_B1s, Standard_LRS disks, no public IP). Review costs before `apply`.

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}

  # null = use ARM_SUBSCRIPTION_ID or the active `az login` subscription
  subscription_id = var.subscription_id
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

resource "azurerm_resource_group" "this" {
  name     = "rg-${var.project_name}"
  location = var.location
  tags     = local.tags
}

module "network" {
  source = "./modules/network"

  name                = var.project_name
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  vnet_cidr           = var.vnet_cidr
  subnet_cidr         = var.subnet_cidr
  allowed_ssh_cidrs   = var.allowed_ssh_cidrs
  tags                = local.tags
}

module "compute" {
  source = "./modules/compute"
  count  = var.enable_vm ? 1 : 0

  name                 = var.project_name
  resource_group_name  = azurerm_resource_group.this.name
  location             = azurerm_resource_group.this.location
  subnet_id            = module.network.subnet_id
  vm_size              = var.vm_size
  admin_username       = var.admin_username
  admin_ssh_public_key = var.admin_ssh_public_key
  os_disk_size_gb      = var.os_disk_size_gb
  data_disk_size_gb    = var.data_disk_size_gb
  tags                 = local.tags
}
