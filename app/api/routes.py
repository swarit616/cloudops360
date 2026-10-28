"""Health, status, hosts and Prometheus endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, Response

from app import __version__
from app.api.deps import ContainerDep
from app.models.schemas import (
    CloudStatusSummary,
    HealthResponse,
    HostInfo,
    HostsResponse,
    Provider,
    StatusResponse,
)
from app.monitoring.system import detect_issues

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Liveness probe: the API process is up."""
    return HealthResponse(version=__version__)


@router.get("/api/status", response_model=StatusResponse, tags=["status"])
def status(container: ContainerDep) -> StatusResponse:
    """Overall status: version, mode, active issues and cloud integration state."""
    snapshot = container.collector.snapshot()
    issues = detect_issues(snapshot, container.settings)
    cloud = [
        CloudStatusSummary(
            provider=overview.provider, configured=overview.configured, message=overview.message
        )
        for overview in (container.aws.get_overview(), container.azure.get_overview())
    ]
    return StatusResponse(
        version=__version__,
        environment=container.settings.app_env,
        status="degraded" if issues else "healthy",
        hostname=snapshot.hostname,
        dry_run=container.settings.dry_run,
        uptime_seconds=round(time.time() - container.started_at, 1),
        issues=issues,
        thresholds=container.settings.thresholds(),
        cloud=cloud,
    )


@router.get("/api/hosts", response_model=HostsResponse, tags=["status"])
def hosts(container: ContainerDep) -> HostsResponse:
    """The LOCAL host plus any AWS / Azure instances discovered by the adapters."""
    snapshot = container.collector.snapshot(include_services=False)
    found = [
        HostInfo(
            provider=Provider.LOCAL,
            id=snapshot.hostname,
            name=snapshot.hostname,
            state="up",
            details={
                "platform": snapshot.platform,
                "uptime_seconds": snapshot.uptime_seconds,
                "cpu_percent": snapshot.cpu.percent,
                "memory_percent": snapshot.memory.percent,
            },
        )
    ]
    for adapter in (container.aws, container.azure):
        for instance in adapter.get_overview().instances:
            found.append(
                HostInfo(
                    provider=instance.provider,
                    id=instance.id,
                    name=instance.name or instance.id,
                    state=instance.state,
                    details={
                        "instance_type": instance.instance_type,
                        "region": instance.region,
                        "private_ip": instance.private_ip,
                        "public_ip": instance.public_ip,
                    },
                )
            )
    counts = {p.value: 0 for p in Provider}
    for host in found:
        counts[host.provider.value] += 1
    return HostsResponse(hosts=found, counts=counts)


@router.get("/metrics", tags=["metrics"], response_class=Response)
def metrics(container: ContainerDep) -> Response:
    """Prometheus exposition format."""
    payload, content_type = container.metrics.render()
    return Response(content=payload, media_type=content_type)
