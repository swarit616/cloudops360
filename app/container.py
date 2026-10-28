"""Wires the application's components together (simple dependency injection)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.cloud.aws import AwsAdapter
from app.cloud.azure import AzureAdapter
from app.cloud.base import CloudAdapter
from app.cloud.refresher import CloudRefresher
from app.config import Settings, get_settings
from app.models.schemas import Provider
from app.monitoring.metrics import CloudOpsMetrics
from app.monitoring.services import CommandRunner, ServiceChecker, SubprocessRunner
from app.monitoring.system import Collector, SystemCollector
from app.remediation.engine import RemediationEngine


@dataclass
class AppContainer:
    settings: Settings
    collector: Collector
    engine: RemediationEngine
    aws: CloudAdapter
    azure: CloudAdapter
    metrics: CloudOpsMetrics
    refresher: CloudRefresher
    started_at: float = field(default_factory=time.time)


def build_container(
    settings: Settings | None = None,
    *,
    collector: Collector | None = None,
    runner: CommandRunner | None = None,
    aws: CloudAdapter | None = None,
    azure: CloudAdapter | None = None,
) -> AppContainer:
    """Build the object graph. Every collaborator can be overridden (used by tests)."""
    settings = settings or get_settings()
    checker = ServiceChecker(runner or SubprocessRunner(), settings.allowed_services)
    collector = collector or SystemCollector(settings, checker)
    aws = aws or AwsAdapter(settings)
    azure = azure or AzureAdapter(settings)
    metrics = CloudOpsMetrics(settings, collector, {Provider.AWS: aws, Provider.AZURE: azure})
    engine = RemediationEngine(
        settings, collector, checker, on_action=metrics.record_remediation
    )
    refresher = CloudRefresher([aws, azure], settings.cloud_refresh_seconds)
    return AppContainer(settings, collector, engine, aws, azure, metrics, refresher)
