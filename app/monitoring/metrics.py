"""Prometheus metrics.

Local host metrics are produced by a custom collector that reads psutil at scrape time, so
values are always fresh. Cloud metrics come from the adapters' cached overviews, so a
Prometheus scrape never triggers a slow call to AWS or Azure. All cloud series carry a
``provider`` label (``AWS`` / ``AZURE``); series without it describe the LOCAL host.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, Metric

from app import __version__
from app.cloud.base import CloudAdapter
from app.config import Settings
from app.logging_config import get_logger, log_event
from app.models.schemas import IssueType, Provider
from app.monitoring.system import Collector, detect_issues

logger = get_logger("metrics")


class _LocalMetricsCollector:
    """Exposes the LOCAL host's state as Prometheus metrics."""

    def __init__(self, settings: Settings, system: Collector) -> None:
        self._settings = settings
        self._system = system

    def collect(self) -> Iterable[Metric]:
        success = GaugeMetricFamily(
            "cloudops_scrape_success", "1 if the last local collection succeeded"
        )
        try:
            snap = self._system.snapshot(cpu_interval=None)
        except Exception as exc:  # noqa: BLE001 - a scrape must never crash the endpoint
            log_event(logger, logging.ERROR, "metrics.collect_failed", error_type=type(exc).__name__)
            success.add_metric([], 0.0)
            yield success
            return
        success.add_metric([], 1.0)
        yield success

        info = GaugeMetricFamily(
            "cloudops_info", "Build and host information", labels=["version", "environment", "hostname"]
        )
        info.add_metric([__version__, self._settings.app_env, snap.hostname], 1.0)
        yield info

        host_up = GaugeMetricFamily("cloudops_host_up", "1 if the monitored local host is up")
        host_up.add_metric([], 1.0)
        yield host_up

        dry_run = GaugeMetricFamily("cloudops_dry_run", "1 if remediation is in dry-run mode")
        dry_run.add_metric([], 1.0 if self._settings.dry_run else 0.0)
        yield dry_run

        cpu = GaugeMetricFamily("cloudops_cpu_percent", "Local CPU utilization percent")
        cpu.add_metric([], snap.cpu.percent)
        yield cpu
        cpu_count = GaugeMetricFamily("cloudops_cpu_count", "Logical CPU cores")
        cpu_count.add_metric([], float(snap.cpu.count_logical))
        yield cpu_count

        mem = GaugeMetricFamily("cloudops_memory_percent", "Local memory utilization percent")
        mem.add_metric([], snap.memory.percent)
        yield mem
        mem_bytes = GaugeMetricFamily("cloudops_memory_bytes", "Local memory in bytes", labels=["type"])
        mem_bytes.add_metric(["total"], float(snap.memory.total_bytes))
        mem_bytes.add_metric(["available"], float(snap.memory.available_bytes))
        mem_bytes.add_metric(["used"], float(snap.memory.used_bytes))
        yield mem_bytes
        swap = GaugeMetricFamily("cloudops_swap_percent", "Local swap utilization percent")
        swap.add_metric([], snap.memory.swap_percent)
        yield swap

        disk_pct = GaugeMetricFamily(
            "cloudops_disk_percent", "Filesystem utilization percent", labels=["mountpoint", "fstype"]
        )
        disk_bytes = GaugeMetricFamily(
            "cloudops_disk_bytes", "Filesystem size in bytes", labels=["mountpoint", "type"]
        )
        for fs in snap.filesystems:
            disk_pct.add_metric([fs.mountpoint, fs.fstype], fs.percent)
            disk_bytes.add_metric([fs.mountpoint, "total"], float(fs.total_bytes))
            disk_bytes.add_metric([fs.mountpoint, "used"], float(fs.used_bytes))
            disk_bytes.add_metric([fs.mountpoint, "free"], float(fs.free_bytes))
        yield disk_pct
        yield disk_bytes

        if snap.disk_io is not None:
            io_bytes = CounterMetricFamily(
                "cloudops_disk_io_bytes", "Disk I/O bytes since boot", labels=["direction"]
            )
            io_bytes.add_metric(["read"], float(snap.disk_io.read_bytes))
            io_bytes.add_metric(["write"], float(snap.disk_io.write_bytes))
            yield io_bytes
            io_ops = CounterMetricFamily(
                "cloudops_disk_io_operations", "Disk I/O operations since boot", labels=["direction"]
            )
            io_ops.add_metric(["read"], float(snap.disk_io.read_count))
            io_ops.add_metric(["write"], float(snap.disk_io.write_count))
            yield io_ops

        net = snap.network
        net_bytes = CounterMetricFamily(
            "cloudops_network_bytes", "Network bytes since boot", labels=["direction"]
        )
        net_bytes.add_metric(["sent"], float(net.bytes_sent))
        net_bytes.add_metric(["received"], float(net.bytes_recv))
        yield net_bytes
        net_errors = CounterMetricFamily(
            "cloudops_network_errors", "Network errors since boot", labels=["direction"]
        )
        net_errors.add_metric(["in"], float(net.errors_in))
        net_errors.add_metric(["out"], float(net.errors_out))
        yield net_errors
        net_drops = CounterMetricFamily(
            "cloudops_network_drops", "Dropped packets since boot", labels=["direction"]
        )
        net_drops.add_metric(["in"], float(net.drops_in))
        net_drops.add_metric(["out"], float(net.drops_out))
        yield net_drops

        load = GaugeMetricFamily("cloudops_load_average", "System load average", labels=["window"])
        load.add_metric(["1m"], snap.load.load_1m)
        load.add_metric(["5m"], snap.load.load_5m)
        load.add_metric(["15m"], snap.load.load_15m)
        yield load
        load_core = GaugeMetricFamily("cloudops_load_per_core", "1-minute load divided by CPU cores")
        load_core.add_metric([], snap.load.per_core_1m)
        yield load_core

        uptime = GaugeMetricFamily("cloudops_uptime_seconds", "Host uptime in seconds")
        uptime.add_metric([], snap.uptime_seconds)
        yield uptime
        procs = GaugeMetricFamily("cloudops_processes", "Number of running processes")
        procs.add_metric([], float(snap.process_count))
        yield procs

        service_up = GaugeMetricFamily(
            "cloudops_service_up", "1 if an allow-listed service is active", labels=["service"]
        )
        for svc in snap.services:
            if svc.state == "active":
                service_up.add_metric([svc.name], 1.0)
            elif svc.state in ("inactive", "failed"):
                service_up.add_metric([svc.name], 0.0)
        yield service_up

        active = {issue.type for issue in detect_issues(snap, self._settings)}
        issue_gauge = GaugeMetricFamily(
            "cloudops_issue_active", "1 if a local threshold breach is active", labels=["type"]
        )
        for issue_type in IssueType:
            issue_gauge.add_metric([issue_type.value], 1.0 if issue_type in active else 0.0)
        yield issue_gauge

        thresholds = GaugeMetricFamily(
            "cloudops_threshold", "Configured detection thresholds", labels=["metric"]
        )
        for name, value in self._settings.thresholds().items():
            thresholds.add_metric([name], value)
        yield thresholds


class _CloudMetricsCollector:
    """Exposes cached AWS / Azure overviews. Never calls a cloud API itself."""

    def __init__(self, adapters: Mapping[Provider, CloudAdapter]) -> None:
        self._adapters = adapters

    def collect(self) -> Iterable[Metric]:
        configured = GaugeMetricFamily(
            "cloudops_cloud_configured",
            "1 if the cloud provider credentials are configured and verified",
            labels=["provider"],
        )
        instances = GaugeMetricFamily(
            "cloudops_cloud_instances", "Discovered VM instances", labels=["provider", "state"]
        )
        volumes = GaugeMetricFamily(
            "cloudops_cloud_volumes", "Discovered block volumes / managed disks", labels=["provider"]
        )
        cpu = GaugeMetricFamily(
            "cloudops_cloud_instance_cpu_percent",
            "Latest CPU utilization reported by CloudWatch / Azure Monitor",
            labels=["provider", "instance"],
        )
        for provider, adapter in self._adapters.items():
            overview = adapter.peek()
            is_configured = bool(overview and overview.configured)
            configured.add_metric([provider.value], 1.0 if is_configured else 0.0)
            if overview is None or not overview.configured:
                continue
            by_state: dict[str, int] = {}
            for instance in overview.instances:
                by_state[instance.state] = by_state.get(instance.state, 0) + 1
            for state, count in sorted(by_state.items()):
                instances.add_metric([provider.value, state], float(count))
            volumes.add_metric([provider.value], float(len(overview.volumes)))
            for point in overview.metrics:
                if point.metric.lower().startswith(("cpu", "percentage cpu")):
                    cpu.add_metric([provider.value, point.resource_id.rsplit("/", 1)[-1]], point.value)
        yield configured
        yield instances
        yield volumes
        yield cpu


class CloudOpsMetrics:
    """Owns the registry, the HTTP/remediation counters and the custom collectors."""

    def __init__(
        self,
        settings: Settings,
        system: Collector,
        cloud_adapters: Mapping[Provider, CloudAdapter],
    ) -> None:
        self.registry = CollectorRegistry()
        self._http_requests = Counter(
            "cloudops_http_requests_total",
            "HTTP requests handled by the CloudOps360 API",
            ["method", "path", "status"],
            registry=self.registry,
        )
        self._http_latency = Histogram(
            "cloudops_http_request_duration_seconds",
            "HTTP request latency in seconds",
            ["method", "path"],
            registry=self.registry,
        )
        self._remediation = Counter(
            "cloudops_remediation_actions_total",
            "Remediation actions processed, by action and outcome",
            ["action", "outcome"],
            registry=self.registry,
        )
        self.registry.register(_LocalMetricsCollector(settings, system))
        self.registry.register(_CloudMetricsCollector(cloud_adapters))

    def record_http(self, method: str, path: str, status: int, duration_seconds: float) -> None:
        self._http_requests.labels(method, path, str(status)).inc()
        self._http_latency.labels(method, path).observe(duration_seconds)

    def record_remediation(self, action: str, outcome: str) -> None:
        self._remediation.labels(action, outcome).inc()

    def render(self) -> tuple[bytes, str]:
        """Return the Prometheus exposition payload and its content type."""
        return generate_latest(self.registry), CONTENT_TYPE_LATEST
