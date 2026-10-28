"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.config import SERVICE_NAME_RE


def utcnow() -> datetime:
    """Timezone-aware current UTC time."""
    return datetime.now(UTC)


class Provider(StrEnum):
    """Where a resource or metric comes from."""

    LOCAL = "LOCAL"
    AWS = "AWS"
    AZURE = "AZURE"


class Severity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"


class IssueType(StrEnum):
    HIGH_CPU = "high_cpu"
    HIGH_MEMORY = "high_memory"
    HIGH_DISK = "high_disk"
    HIGH_LOAD = "high_load"
    SERVICE_DOWN = "service_down"


# --------------------------------------------------------------------------- system snapshot


class CpuInfo(BaseModel):
    percent: float
    count_logical: int
    count_physical: int | None = None
    frequency_mhz: float | None = None


class MemoryInfo(BaseModel):
    total_bytes: int
    available_bytes: int
    used_bytes: int
    percent: float
    swap_total_bytes: int = 0
    swap_used_bytes: int = 0
    swap_percent: float = 0.0


class FilesystemInfo(BaseModel):
    mountpoint: str
    device: str
    fstype: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float


class DiskIoInfo(BaseModel):
    read_bytes: int
    write_bytes: int
    read_count: int
    write_count: int


class NetworkInterface(BaseModel):
    name: str
    is_up: bool
    bytes_sent: int
    bytes_recv: int
    errors_in: int
    errors_out: int


class NetworkInfo(BaseModel):
    bytes_sent: int = 0
    bytes_recv: int = 0
    packets_sent: int = 0
    packets_recv: int = 0
    errors_in: int = 0
    errors_out: int = 0
    drops_in: int = 0
    drops_out: int = 0
    interfaces: list[NetworkInterface] = Field(default_factory=list)


class LoadInfo(BaseModel):
    load_1m: float
    load_5m: float
    load_15m: float
    per_core_1m: float


class ProcessInfo(BaseModel):
    pid: int
    name: str
    username: str | None = None
    cpu_percent: float
    memory_percent: float


class ServiceStatus(BaseModel):
    """State of an allow-listed service (``active``, ``inactive``, ``not-found`` ...)."""

    name: str
    state: str
    source: str = "systemd"


class SystemSnapshot(BaseModel):
    provider: Provider = Provider.LOCAL
    hostname: str
    platform: str
    timestamp: datetime = Field(default_factory=utcnow)
    uptime_seconds: float
    boot_time: datetime
    cpu: CpuInfo
    memory: MemoryInfo
    filesystems: list[FilesystemInfo]
    disk_io: DiskIoInfo | None = None
    network: NetworkInfo
    load: LoadInfo
    process_count: int
    services: list[ServiceStatus] = Field(default_factory=list)


class Issue(BaseModel):
    """A threshold breach or unhealthy service detected on the local host."""

    type: IssueType
    severity: Severity
    message: str
    target: str
    value: float | None = None
    threshold: float | None = None
    source: Provider = Provider.LOCAL


# --------------------------------------------------------------------------- API responses


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "cloudops360"
    version: str
    timestamp: datetime = Field(default_factory=utcnow)


class CloudStatusSummary(BaseModel):
    provider: Provider
    configured: bool
    message: str


class StatusResponse(BaseModel):
    service: str = "cloudops360"
    version: str
    environment: str
    status: Literal["healthy", "degraded"]
    hostname: str
    dry_run: bool
    uptime_seconds: float
    issues: list[Issue]
    thresholds: dict[str, float]
    cloud: list[CloudStatusSummary]
    timestamp: datetime = Field(default_factory=utcnow)


class HostInfo(BaseModel):
    provider: Provider
    id: str
    name: str
    state: str
    details: dict[str, Any] = Field(default_factory=dict)


class HostsResponse(BaseModel):
    hosts: list[HostInfo]
    counts: dict[str, int]
    timestamp: datetime = Field(default_factory=utcnow)


class DiagnosticsResponse(BaseModel):
    provider: Provider = Provider.LOCAL
    healthy: bool
    snapshot: SystemSnapshot
    issues: list[Issue]
    top_cpu_processes: list[ProcessInfo]
    top_memory_processes: list[ProcessInfo]
    thresholds: dict[str, float]
    recommendations: list[str]
    timestamp: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- remediation


class RemediationAction(StrEnum):
    """The complete allowlist of actions the engine can ever perform."""

    DISK_CLEANUP = "disk_cleanup"
    RESTART_SERVICE = "restart_service"
    REPORT_HIGH_CPU = "report_high_cpu"
    REPORT_MEMORY_PRESSURE = "report_memory_pressure"


class RemediationRequest(BaseModel):
    """Request body for dry-run / execute. Unknown fields are rejected on purpose, so there
    is no place to smuggle in a command, path or script."""

    model_config = ConfigDict(extra="forbid")

    actions: list[RemediationAction] | None = Field(
        default=None,
        max_length=4,
        description="Limit to specific allow-listed actions. Default: act on detected issues.",
    )
    service: str | None = Field(
        default=None,
        max_length=64,
        pattern=SERVICE_NAME_RE.pattern,
        description="Restrict restart_service to one allow-listed service.",
    )
    confirm: bool = Field(
        default=False,
        description="Must be true for /execute. Ignored by /dry-run.",
    )


class Verification(BaseModel):
    performed: bool
    passed: bool | None = None
    detail: str


class RemediationResult(BaseModel):
    issue: Issue | None = None
    action: RemediationAction
    proposed_action: str
    dry_run: bool
    outcome: Literal["dry_run", "executed", "reported", "skipped", "failed"]
    detail: str
    data: dict[str, Any] = Field(default_factory=dict)
    verification: Verification
    timestamp: datetime = Field(default_factory=utcnow)


class RemediationReport(BaseModel):
    dry_run: bool
    issues_detected: int
    results: list[RemediationResult]
    summary: str
    timestamp: datetime = Field(default_factory=utcnow)


class RemediationStatus(BaseModel):
    dry_run: bool
    execution_enabled: bool
    allowed_actions: list[RemediationAction]
    allowed_services: list[str]
    cleanup_dirs: list[str]
    cleanup_extensions: list[str]
    cleanup_min_age_hours: float
    cleanup_max_files: int
    recent_results: list[RemediationResult]
    timestamp: datetime = Field(default_factory=utcnow)
