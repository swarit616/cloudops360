"""Shared fakes and builders for the test-suite (no cloud, no real systemd)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from prometheus_client.parser import text_string_to_metric_families

from app.config import Settings
from app.models.schemas import (
    CpuInfo,
    FilesystemInfo,
    LoadInfo,
    MemoryInfo,
    NetworkInfo,
    ProcessInfo,
    ServiceStatus,
    SystemSnapshot,
)
from app.monitoring.services import CommandResult


def build_snapshot(
    cpu: float = 10.0,
    memory: float = 20.0,
    disk: float = 30.0,
    load_per_core: float = 0.2,
    services: dict[str, str] | None = None,
    mountpoint: str = "/",
) -> SystemSnapshot:
    """A synthetic, fully controllable snapshot."""
    total = 100 * 1024**3
    return SystemSnapshot(
        hostname="test-host",
        platform="Linux-test",
        uptime_seconds=3600.0,
        boot_time=datetime(2026, 1, 1, tzinfo=UTC),
        cpu=CpuInfo(percent=cpu, count_logical=4, count_physical=2),
        memory=MemoryInfo(
            total_bytes=total,
            available_bytes=int(total * (100 - memory) / 100),
            used_bytes=int(total * memory / 100),
            percent=memory,
        ),
        filesystems=[
            FilesystemInfo(
                mountpoint=mountpoint,
                device="/dev/test",
                fstype="ext4",
                total_bytes=total,
                used_bytes=int(total * disk / 100),
                free_bytes=int(total * (100 - disk) / 100),
                percent=disk,
            )
        ],
        network=NetworkInfo(),
        load=LoadInfo(
            load_1m=load_per_core * 4,
            load_5m=load_per_core * 4,
            load_15m=load_per_core * 4,
            per_core_1m=load_per_core,
        ),
        process_count=100,
        services=[ServiceStatus(name=n, state=s) for n, s in (services or {}).items()],
    )


class StaticCollector:
    """Collector returning canned data. ``disk_after`` simulates cleanup freeing space."""

    def __init__(self, snapshot: SystemSnapshot, disk_after: float | None = None) -> None:
        self._snapshot = snapshot
        self._disk_after = disk_after
        self.snapshot_calls = 0

    def snapshot(
        self, cpu_interval: float | None = 0.2, include_services: bool = True
    ) -> SystemSnapshot:
        self.snapshot_calls += 1
        snap = self._snapshot
        if self._disk_after is not None and self.snapshot_calls > 2:
            snap = snap.model_copy(deep=True)
            snap.filesystems[0].percent = self._disk_after
        return snap

    def top_processes(
        self, by: Literal["cpu", "memory"] = "cpu", limit: int = 5
    ) -> list[ProcessInfo]:
        return [
            ProcessInfo(
                pid=1, name="busy-proc", username="root", cpu_percent=90.0, memory_percent=5.0
            ),
            ProcessInfo(
                pid=2, name="big-proc", username="app", cpu_percent=1.0, memory_percent=40.0
            ),
        ][:limit]


class FakeRunner:
    """Fake systemctl. Records every argv; ``restart`` flips the service to active."""

    def __init__(self, states: dict[str, str] | None = None, restart_rc: int = 0) -> None:
        self.states = dict(states or {})
        self.restart_rc = restart_rc
        self.calls: list[list[str]] = []

    def run(self, args: Sequence[str], timeout: float = 5.0) -> CommandResult:
        argv = list(args)
        self.calls.append(argv)
        if argv[:2] == ["systemctl", "show"]:
            state = self.states.get(argv[2], "not-found")
            if state == "not-found":
                return CommandResult(0, "LoadState=not-found\nActiveState=inactive\n")
            return CommandResult(0, f"LoadState=loaded\nActiveState={state}\n")
        if argv[:2] == ["systemctl", "restart"]:
            if self.restart_rc == 0:
                self.states[argv[2]] = "active"
            return CommandResult(self.restart_rc, "", "boom" if self.restart_rc else "")
        return CommandResult(1, "", "unexpected command")


def make_settings(tmp_path, **overrides) -> Settings:
    """Settings that never touch real cloud accounts or system directories."""
    values = {
        "dry_run": True,
        "remediation_api_key": "test-key",
        "cleanup_dirs": (str(tmp_path / "cleanup"),),
        "allowed_services": ("demo-svc",),
        "restart_verify_delay_seconds": 0.0,
        "aws_enabled": False,
        "azure_enabled": False,
        "cloud_refresh_seconds": 0.0,
    }
    values.update(overrides)
    return Settings(**values)


def sample_value(text: str, name: str, **labels: str) -> Any:
    """Find one sample in Prometheus exposition text (independent of label order)."""
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            if sample.name == name and all(sample.labels.get(k) == v for k, v in labels.items()):
                return sample.value
    return None
