"""Real Linux host monitoring built on psutil, plus threshold evaluation."""

from __future__ import annotations

import platform
import socket
import time
from datetime import UTC, datetime
from typing import Literal, Protocol

import psutil

from app.config import Settings
from app.models.schemas import (
    CpuInfo,
    DiskIoInfo,
    FilesystemInfo,
    Issue,
    IssueType,
    LoadInfo,
    MemoryInfo,
    NetworkInfo,
    NetworkInterface,
    ProcessInfo,
    ServiceStatus,
    Severity,
    SystemSnapshot,
)
from app.monitoring.services import DOWN_STATES, ServiceChecker

_IGNORED_FSTYPES = frozenset(
    {
        "squashfs", "tmpfs", "devtmpfs", "devfs", "proc", "sysfs", "cgroup", "cgroup2",
        "tracefs", "autofs", "9p", "fuse.lxcfs", "ramfs", "iso9660",
    }
)  # fmt: skip
_IGNORED_MOUNT_PREFIXES = (
    "/proc", "/sys", "/dev", "/run", "/snap", "/etc/", "/boot/efi", "/usr/lib/wsl", "/mnt/wsl",
)  # fmt: skip
_MAX_FILESYSTEMS = 10


class Collector(Protocol):
    """What the rest of the app needs from a monitor (replaced by a fake in tests)."""

    def snapshot(
        self, cpu_interval: float | None = 0.2, include_services: bool = True
    ) -> SystemSnapshot: ...

    def top_processes(
        self, by: Literal["cpu", "memory"] = "cpu", limit: int = 5
    ) -> list[ProcessInfo]: ...


class SystemCollector:
    """Collects a point-in-time view of the local Linux host."""

    def __init__(self, settings: Settings, service_checker: ServiceChecker | None = None) -> None:
        self._settings = settings
        self._services = service_checker
        psutil.cpu_percent(interval=None)  # prime the counter so the next call is meaningful

    # ------------------------------------------------------------------ public API

    def snapshot(
        self, cpu_interval: float | None = 0.2, include_services: bool = True
    ) -> SystemSnapshot:
        """Gather CPU, memory, disk, network, load, uptime and service state."""
        boot = psutil.boot_time()
        logical = psutil.cpu_count(logical=True) or 1
        load_1, load_5, load_15 = psutil.getloadavg()
        services: list[ServiceStatus] = []
        if include_services and self._services is not None:
            services = self._services.check_all()
        return SystemSnapshot(
            hostname=socket.gethostname(),
            platform=platform.platform(),
            uptime_seconds=round(max(time.time() - boot, 0.0), 1),
            boot_time=datetime.fromtimestamp(boot, UTC),
            cpu=self._cpu(cpu_interval, logical),
            memory=self._memory(),
            filesystems=self._filesystems(),
            disk_io=self._disk_io(),
            network=self._network(),
            load=LoadInfo(
                load_1m=round(load_1, 2),
                load_5m=round(load_5, 2),
                load_15m=round(load_15, 2),
                per_core_1m=round(load_1 / logical, 3),
            ),
            process_count=len(psutil.pids()),
            services=services,
        )

    def top_processes(
        self, by: Literal["cpu", "memory"] = "cpu", limit: int = 5
    ) -> list[ProcessInfo]:
        """Return the top consumers. Read-only: processes are only ever reported."""
        procs: list[psutil.Process] = []
        for proc in psutil.process_iter(["pid", "name", "username"]):
            try:
                proc.cpu_percent(None)  # first call primes the per-process counter
                procs.append(proc)
            except psutil.Error:
                continue
        if by == "cpu":
            time.sleep(0.25)  # sampling window for per-process CPU

        rows: list[ProcessInfo] = []
        for proc in procs:
            try:
                with proc.oneshot():
                    rows.append(
                        ProcessInfo(
                            pid=proc.pid,
                            name=proc.info.get("name") or "unknown",
                            username=proc.info.get("username"),
                            cpu_percent=round(proc.cpu_percent(None), 1),
                            memory_percent=round(proc.memory_percent(), 1),
                        )
                    )
            except psutil.Error:
                continue
        key = (lambda r: r.cpu_percent) if by == "cpu" else (lambda r: r.memory_percent)
        rows.sort(key=key, reverse=True)
        return rows[: max(limit, 0)]

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _cpu(interval: float | None, logical: int) -> CpuInfo:
        try:
            freq = psutil.cpu_freq()
        except (NotImplementedError, FileNotFoundError, OSError):
            freq = None
        return CpuInfo(
            percent=psutil.cpu_percent(interval=interval),
            count_logical=logical,
            count_physical=psutil.cpu_count(logical=False),
            frequency_mhz=round(freq.current, 1) if freq else None,
        )

    @staticmethod
    def _memory() -> MemoryInfo:
        vm = psutil.virtual_memory()
        try:
            swap = psutil.swap_memory()
            swap_total, swap_used, swap_percent = swap.total, swap.used, swap.percent
        except OSError:
            swap_total = swap_used = 0
            swap_percent = 0.0
        return MemoryInfo(
            total_bytes=vm.total,
            available_bytes=vm.available,
            used_bytes=vm.total - vm.available,
            percent=vm.percent,
            swap_total_bytes=swap_total,
            swap_used_bytes=swap_used,
            swap_percent=swap_percent,
        )

    @staticmethod
    def _usage(mountpoint: str, device: str, fstype: str) -> FilesystemInfo | None:
        try:
            usage = psutil.disk_usage(mountpoint)
        except OSError:
            return None
        if usage.total <= 0:
            return None
        return FilesystemInfo(
            mountpoint=mountpoint,
            device=device,
            fstype=fstype,
            total_bytes=usage.total,
            used_bytes=usage.used,
            free_bytes=usage.free,
            percent=usage.percent,
        )

    def _filesystems(self) -> list[FilesystemInfo]:
        found: dict[str, FilesystemInfo] = {}
        try:
            partitions = psutil.disk_partitions(all=False)
        except OSError:
            partitions = []
        for part in partitions:
            if part.fstype in _IGNORED_FSTYPES or part.mountpoint.startswith(
                _IGNORED_MOUNT_PREFIXES
            ):
                continue
            if part.mountpoint in found:
                continue
            info = self._usage(part.mountpoint, part.device, part.fstype)
            if info:
                found[part.mountpoint] = info
            if len(found) >= _MAX_FILESYSTEMS:
                break
        if self._settings.disk_path not in found:
            info = self._usage(self._settings.disk_path, "", "unknown")
            if info:
                found[self._settings.disk_path] = info
        return list(found.values())

    @staticmethod
    def _disk_io() -> DiskIoInfo | None:
        try:
            io = psutil.disk_io_counters()
        except (OSError, RuntimeError):
            return None
        if io is None:
            return None
        return DiskIoInfo(
            read_bytes=io.read_bytes,
            write_bytes=io.write_bytes,
            read_count=io.read_count,
            write_count=io.write_count,
        )

    @staticmethod
    def _network() -> NetworkInfo:
        try:
            total = psutil.net_io_counters()
            per_nic = psutil.net_io_counters(pernic=True)
            stats = psutil.net_if_stats()
        except OSError:
            return NetworkInfo()
        interfaces = [
            NetworkInterface(
                name=name,
                is_up=bool(stats[name].isup) if name in stats else False,
                bytes_sent=io.bytes_sent,
                bytes_recv=io.bytes_recv,
                errors_in=io.errin,
                errors_out=io.errout,
            )
            for name, io in sorted(per_nic.items())
        ]
        if total is None:
            return NetworkInfo(interfaces=interfaces)
        return NetworkInfo(
            bytes_sent=total.bytes_sent,
            bytes_recv=total.bytes_recv,
            packets_sent=total.packets_sent,
            packets_recv=total.packets_recv,
            errors_in=total.errin,
            errors_out=total.errout,
            drops_in=total.dropin,
            drops_out=total.dropout,
            interfaces=interfaces,
        )


# ---------------------------------------------------------------------- threshold logic


def _severity(value: float, threshold: float, margin: float) -> Severity:
    return Severity.CRITICAL if value >= threshold + margin else Severity.WARNING


def detect_issues(snapshot: SystemSnapshot, settings: Settings) -> list[Issue]:
    """Compare a snapshot against the configured thresholds (strictly greater than)."""
    issues: list[Issue] = []

    cpu = snapshot.cpu.percent
    if cpu > settings.cpu_threshold:
        issues.append(
            Issue(
                type=IssueType.HIGH_CPU,
                severity=_severity(cpu, settings.cpu_threshold, 10),
                message=f"CPU utilization {cpu:.1f}% exceeds threshold {settings.cpu_threshold:.1f}%",
                target="cpu",
                value=cpu,
                threshold=settings.cpu_threshold,
            )
        )

    mem = snapshot.memory.percent
    if mem > settings.memory_threshold:
        issues.append(
            Issue(
                type=IssueType.HIGH_MEMORY,
                severity=_severity(mem, settings.memory_threshold, 10),
                message=(
                    f"Memory utilization {mem:.1f}% exceeds threshold "
                    f"{settings.memory_threshold:.1f}%"
                ),
                target="memory",
                value=mem,
                threshold=settings.memory_threshold,
            )
        )

    for fs in snapshot.filesystems:
        if fs.percent > settings.disk_threshold:
            issues.append(
                Issue(
                    type=IssueType.HIGH_DISK,
                    severity=_severity(fs.percent, settings.disk_threshold, 10),
                    message=(
                        f"Disk usage on {fs.mountpoint} is {fs.percent:.1f}% "
                        f"(threshold {settings.disk_threshold:.1f}%)"
                    ),
                    target=fs.mountpoint,
                    value=fs.percent,
                    threshold=settings.disk_threshold,
                )
            )

    load = snapshot.load.per_core_1m
    if load > settings.load_threshold:
        issues.append(
            Issue(
                type=IssueType.HIGH_LOAD,
                severity=_severity(load, settings.load_threshold, settings.load_threshold),
                message=(
                    f"1-minute load per core {load:.2f} exceeds threshold "
                    f"{settings.load_threshold:.2f}"
                ),
                target="load",
                value=load,
                threshold=settings.load_threshold,
            )
        )

    for service in snapshot.services:
        if service.state in DOWN_STATES:
            issues.append(
                Issue(
                    type=IssueType.SERVICE_DOWN,
                    severity=Severity.CRITICAL,
                    message=f"Service {service.name} is {service.state}",
                    target=service.name,
                )
            )
    return issues
