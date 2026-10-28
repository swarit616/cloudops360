"""Azure adapter (official SDK). Uses DefaultAzureCredential; never stores secrets."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.cloud.base import CloudAdapter, safe_error
from app.cloud.models import (
    CloudInstance,
    CloudMetricPoint,
    CloudNetwork,
    CloudOverview,
    CloudVolume,
    ResourceGroup,
)
from app.config import Settings
from app.models.schemas import Provider

_ARM_SCOPE = "https://management.azure.com/.default"
_MAX_VMS = 25
_MAX_METRIC_VMS = 5
_INTERNET_SOURCES = {"*", "internet", "0.0.0.0/0", "any"}


@dataclass
class AzureClients:
    """The management clients the adapter needs (injectable for tests)."""

    resources: Any
    compute: Any
    network: Any
    monitor: Any


def _default_credential() -> Any:
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


def _default_clients(credential: Any, subscription_id: str) -> AzureClients:
    from azure.mgmt.compute import ComputeManagementClient
    from azure.mgmt.monitor import MonitorManagementClient
    from azure.mgmt.network import NetworkManagementClient
    from azure.mgmt.resource import ResourceManagementClient

    options = {"connection_timeout": 5, "read_timeout": 15}
    return AzureClients(
        resources=ResourceManagementClient(credential, subscription_id, **options),
        compute=ComputeManagementClient(credential, subscription_id, **options),
        network=NetworkManagementClient(credential, subscription_id, **options),
        monitor=MonitorManagementClient(credential, subscription_id, **options),
    )


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _resource_group_of(resource_id: str) -> str | None:
    parts = resource_id.split("/")
    lowered = [p.lower() for p in parts]
    if "resourcegroups" in lowered:
        index = lowered.index("resourcegroups") + 1
        if index < len(parts):
            return parts[index]
    return None


class AzureAdapter(CloudAdapter):
    """VMs, managed disks, resource groups, VNets/NSGs and Azure Monitor metrics."""

    provider = Provider.AZURE

    def __init__(
        self,
        settings: Settings,
        credential_factory: Callable[[], Any] | None = None,
        clients_factory: Callable[[Any, str], AzureClients] | None = None,
        cache_ttl_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        ttl = settings.cloud_cache_ttl_seconds if cache_ttl_seconds is None else cache_ttl_seconds
        super().__init__(ttl, clock)
        self._settings = settings
        self._credential_factory = credential_factory or _default_credential
        self._clients_factory = clients_factory or _default_clients
        self._credential: Any = None

    def _collect(self) -> CloudOverview:
        if not self._settings.azure_enabled:
            return self._not_configured("Azure integration is disabled (AZURE_ENABLED=false)")
        subscription_id = self._settings.azure_subscription_id
        if not subscription_id:
            return self._not_configured(
                "Azure credentials are not configured",
                "AZURE_SUBSCRIPTION_ID is not set",
            )
        try:
            if self._credential is None:
                self._credential = self._credential_factory()
            self._credential.get_token(_ARM_SCOPE)
        except Exception as exc:  # noqa: BLE001
            self._credential = None
            name = type(exc).__name__
            message = (
                "Azure credentials are not configured"
                if name == "CredentialUnavailableError"
                else "Azure credentials could not be verified"
            )
            return self._not_configured(message, safe_error(exc))

        clients = self._clients_factory(self._credential, subscription_id)
        warnings: list[str] = []
        groups = self._section("resource_groups", lambda: self._groups(clients), [], warnings)
        instances = self._section("vms", lambda: self._vms(clients), [], warnings)
        volumes = self._section("disks", lambda: self._disks(clients), [], warnings)
        networks = self._section("network", lambda: self._networks(clients), [], warnings)
        metrics = self._section(
            "monitor", lambda: self._cpu_metrics(clients, instances), [], warnings
        )
        return CloudOverview(
            provider=self.provider,
            configured=True,
            message="Azure credentials verified",
            identity={"subscription_id": f"********{subscription_id[-4:]}"},
            resource_groups=groups,
            instances=instances,
            volumes=volumes,
            networks=networks,
            metrics=metrics,
            warnings=warnings,
        )

    # ------------------------------------------------------------------ sections

    @staticmethod
    def _groups(clients: AzureClients) -> list[ResourceGroup]:
        return [
            ResourceGroup(name=group.name, location=group.location)
            for group in clients.resources.resource_groups.list()
        ]

    @staticmethod
    def _power_state(clients: AzureClients, vm: Any) -> str:
        group = _resource_group_of(vm.id or "")
        if not group:
            return "unknown"
        view = clients.compute.virtual_machines.instance_view(group, vm.name)
        for status in getattr(view, "statuses", None) or []:
            code = getattr(status, "code", "") or ""
            if code.startswith("PowerState/"):
                return code.split("/", 1)[1]
        return "unknown"

    def _vms(self, clients: AzureClients) -> list[CloudInstance]:
        found: list[CloudInstance] = []
        for vm in clients.compute.virtual_machines.list_all():
            if len(found) >= _MAX_VMS:
                break
            try:
                state = self._power_state(clients, vm)
            except Exception:  # noqa: BLE001 - one VM failing must not hide the others
                state = "unknown"
            profile = getattr(vm, "hardware_profile", None)
            found.append(
                CloudInstance(
                    provider=Provider.AZURE,
                    id=vm.id,
                    name=vm.name,
                    state=state,
                    instance_type=_enum_value(getattr(profile, "vm_size", None)),
                    region=vm.location,
                )
            )
        return found

    @staticmethod
    def _disks(clients: AzureClients) -> list[CloudVolume]:
        found: list[CloudVolume] = []
        for disk in clients.compute.disks.list():
            if len(found) >= _MAX_VMS * 2:
                break
            managed_by = getattr(disk, "managed_by", None)
            sku = getattr(disk, "sku", None)
            found.append(
                CloudVolume(
                    provider=Provider.AZURE,
                    id=disk.id,
                    name=disk.name,
                    size_gb=getattr(disk, "disk_size_gb", None),
                    state=_enum_value(getattr(disk, "disk_state", None)),
                    volume_type=_enum_value(getattr(sku, "name", None)),
                    attached_to=managed_by.rsplit("/", 1)[-1] if managed_by else None,
                    region=disk.location,
                )
            )
        return found

    @staticmethod
    def _networks(clients: AzureClients) -> list[CloudNetwork]:
        found: list[CloudNetwork] = []
        for vnet in clients.network.virtual_networks.list_all():
            space = getattr(vnet, "address_space", None)
            found.append(
                CloudNetwork(
                    provider=Provider.AZURE,
                    id=vnet.id,
                    name=vnet.name,
                    kind="vnet",
                    cidrs=list(getattr(space, "address_prefixes", None) or []),
                    region=vnet.location,
                    details={
                        "subnets": [
                            {"name": s.name, "prefix": getattr(s, "address_prefix", None)}
                            for s in (getattr(vnet, "subnets", None) or [])
                        ]
                    },
                )
            )
        for nsg in clients.network.network_security_groups.list_all():
            rules = getattr(nsg, "security_rules", None) or []
            exposed = [
                rule.name
                for rule in rules
                if _enum_value(getattr(rule, "direction", None)) == "Inbound"
                and _enum_value(getattr(rule, "access", None)) == "Allow"
                and (getattr(rule, "source_address_prefix", "") or "").lower() in _INTERNET_SOURCES
            ]
            found.append(
                CloudNetwork(
                    provider=Provider.AZURE,
                    id=nsg.id,
                    name=nsg.name,
                    kind="nsg",
                    region=nsg.location,
                    details={"rule_count": len(rules), "inbound_allow_from_internet": exposed},
                )
            )
        return found

    @staticmethod
    def _cpu_metrics(clients: AzureClients, instances: list[CloudInstance]) -> list[CloudMetricPoint]:
        running = [i for i in instances if i.state == "running"][:_MAX_METRIC_VMS]
        end = datetime.now(UTC)
        timespan = f"{(end - timedelta(minutes=30)).isoformat()}/{end.isoformat()}"
        points: list[CloudMetricPoint] = []
        for instance in running:
            response = clients.monitor.metrics.list(
                resource_uri=instance.id,
                timespan=timespan,
                interval="PT5M",
                metricnames="Percentage CPU",
                aggregation="Average",
            )
            for metric in response.value or []:
                for series in metric.timeseries or []:
                    for point in reversed(series.data or []):
                        if point.average is not None:
                            points.append(
                                CloudMetricPoint(
                                    provider=Provider.AZURE,
                                    resource_id=instance.id,
                                    metric="Percentage CPU",
                                    value=float(point.average),
                                    unit="Percent",
                                    timestamp=point.time_stamp,
                                )
                            )
                            break
        return points
