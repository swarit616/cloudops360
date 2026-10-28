# Azure integration

The Azure adapter (`app/cloud/azure.py`) is **read-only** and optional. Without a subscription id or credentials:

```json
{ "provider": "AZURE", "configured": false, "message": "Azure credentials are not configured", "...": "..." }
```

## What it reads

| Area | SDK | Used for |
|---|---|---|
| Credentials | `azure-identity` `DefaultAzureCredential` | token acquisition = credential verification |
| Resource groups | `azure-mgmt-resource` | inventory |
| VMs and power state | `azure-mgmt-compute` (`list_all`, `instance_view`) | discovery, `running`/`deallocated`... |
| Managed disks | `azure-mgmt-compute` | size, SKU, state, attached VM |
| VNets and NSGs | `azure-mgmt-network` | address spaces, subnets, NSG rules open to the internet |
| Metrics | `azure-mgmt-monitor` | latest `Percentage CPU` of running VMs |

## Required configuration

`AZURE_SUBSCRIPTION_ID` (not a secret) **and** any `DefaultAzureCredential` source.

## Providing credentials safely

1. **Managed identity** when running in Azure (VM / Container Apps): nothing to store.
2. **`az login`** locally (`az account set --subscription <id>`). Works from WSL; tokens stay in `~/.azure`.
3. **Service principal with a least-privilege role**:
   ```bash
   az ad sp create-for-rbac --name cloudops360-reader --role Reader \
     --scopes /subscriptions/<SUBSCRIPTION_ID>
   ```
   Put `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` in your **git-ignored** `.env`. Prefer short-lived
   secrets or federated credentials in CI.

The built-in **Reader** role is sufficient (it includes reading VM instance views and metrics). Never grant
Contributor/Owner to a monitoring identity.

## Verify

```bash
az login && export AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
make run &
curl -s localhost:8000/api/cloud/azure | python3 -m json.tool
```

## Terraform example and cost

`terraform/azure` creates a resource group, VNet, subnet, NSG (explicit deny of other inbound, SSH only from
`allowed_ssh_cidrs`), a `Standard_B1s` Ubuntu VM (SSH key only, system-assigned identity, no public IP) and an 8 GiB
Standard_LRS managed disk. `admin_ssh_public_key` is required. A B1s VM plus disks costs a few USD per month if left
running; set `enable_vm = false` to plan only the network, and finish with `terraform destroy`.
