"""Diagnostics endpoint, threshold logic and configuration parsing."""

from __future__ import annotations

import pytest

from app.config import ConfigError, Settings
from app.models.schemas import IssueType, Severity
from app.monitoring.system import SystemCollector, detect_issues
from tests.helpers import build_snapshot


def types(issues):
    return [i.type for i in issues]


def test_diagnostics_endpoint_structure(client):
    response = client.get("/api/diagnostics?top=2")
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "LOCAL"
    assert body["healthy"] is True
    assert body["snapshot"]["hostname"] == "test-host"
    assert len(body["top_cpu_processes"]) == 2
    assert body["recommendations"] == ["No action needed: all metrics are within thresholds."]


def test_diagnostics_validates_top_parameter(client):
    assert client.get("/api/diagnostics?top=0").status_code == 422
    assert client.get("/api/diagnostics?top=999").status_code == 422


def test_diagnostics_reports_issues_and_recommendations(make_client):
    client, _, _ = make_client(snapshot=build_snapshot(disk=95.0))
    body = client.get("/api/diagnostics").json()
    assert body["healthy"] is False
    assert body["issues"][0]["type"] == "high_disk"
    assert "dry-run" in body["recommendations"][0]


def test_real_collector_returns_sane_snapshot(tmp_path):
    from tests.helpers import make_settings

    snapshot = SystemCollector(make_settings(tmp_path, disk_path="/")).snapshot(cpu_interval=0.05)
    assert 0 <= snapshot.cpu.percent <= 100
    assert 0 <= snapshot.memory.percent <= 100
    assert snapshot.cpu.count_logical >= 1
    assert snapshot.uptime_seconds > 0
    assert snapshot.process_count > 0
    assert snapshot.filesystems


def test_no_issues_below_thresholds():
    assert detect_issues(build_snapshot(), Settings()) == []


def test_threshold_is_strictly_greater_than():
    settings = Settings(cpu_threshold=85.0)
    assert detect_issues(build_snapshot(cpu=85.0), settings) == []
    assert types(detect_issues(build_snapshot(cpu=85.1), settings)) == [IssueType.HIGH_CPU]


def test_each_threshold_type_is_detected():
    snap = build_snapshot(cpu=90, memory=91, disk=92, load_per_core=2.0)
    assert set(types(detect_issues(snap, Settings()))) == {
        IssueType.HIGH_CPU,
        IssueType.HIGH_MEMORY,
        IssueType.HIGH_DISK,
        IssueType.HIGH_LOAD,
    }


def test_thresholds_come_from_settings_not_code():
    snap = build_snapshot(cpu=60.0)
    assert detect_issues(snap, Settings(cpu_threshold=85.0)) == []
    assert types(detect_issues(snap, Settings(cpu_threshold=50.0))) == [IssueType.HIGH_CPU]


def test_severity_escalates_with_margin():
    settings = Settings(cpu_threshold=85.0)
    assert detect_issues(build_snapshot(cpu=90), settings)[0].severity is Severity.WARNING
    assert detect_issues(build_snapshot(cpu=96), settings)[0].severity is Severity.CRITICAL


def test_only_down_services_raise_issues():
    snap = build_snapshot(
        services={
            "a": "active",
            "b": "inactive",
            "c": "failed",
            "d": "not-found",
            "e": "unavailable",
        }
    )
    issues = detect_issues(snap, Settings())
    assert [(i.type, i.target) for i in issues] == [
        (IssueType.SERVICE_DOWN, "b"),
        (IssueType.SERVICE_DOWN, "c"),
    ]


def test_settings_from_env_reads_thresholds():
    settings = Settings.from_env(
        {
            "CPU_THRESHOLD": "70",
            "MEMORY_THRESHOLD": "75.5",
            "DISK_THRESHOLD": "90",
            "LOAD_THRESHOLD": "2",
        }
    )
    assert (settings.cpu_threshold, settings.memory_threshold) == (70.0, 75.5)
    assert (settings.disk_threshold, settings.load_threshold) == (90.0, 2.0)


def test_settings_defaults_are_safe():
    settings = Settings.from_env({})
    assert settings.dry_run is True
    assert settings.remediation_api_key is None
    assert settings.cpu_threshold == 85.0


@pytest.mark.parametrize(
    "env",
    [
        {"CPU_THRESHOLD": "abc"},
        {"CPU_THRESHOLD": "150"},
        {"DISK_THRESHOLD": "0"},
        {"DRY_RUN": "maybe"},
        {"LOG_LEVEL": "LOUD"},
        {"ALLOWED_SERVICES": "ok,bad name;rm -rf /"},
    ],
)
def test_invalid_settings_fail_fast(env):
    with pytest.raises(ConfigError):
        Settings.from_env(env)


def test_public_settings_never_include_secret():
    settings = Settings(remediation_api_key="super-secret")
    assert "super-secret" not in str(settings.public_dict())
    assert "super-secret" not in repr(settings)
