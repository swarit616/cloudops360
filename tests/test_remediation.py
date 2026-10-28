"""Remediation engine: dry-run, guarded execution and safety restrictions."""

from __future__ import annotations

import os
import time

import pytest

from app.remediation.safety import UnsafePathError, scan_cleanup_candidates, validate_cleanup_dir
from tests.helpers import FakeRunner, build_snapshot, sample_value

OLD = time.time() - 3 * 24 * 3600


def make_file(path, size=100, mtime=OLD):
    path.write_bytes(b"x" * size)
    os.utime(path, (mtime, mtime))
    return path


def disk_full():
    return build_snapshot(disk=95.0)


# ------------------------------------------------------------------ status & dry-run


def test_remediation_status_defaults(client):
    body = client.get("/api/remediation/status").json()
    assert body["dry_run"] is True
    assert body["execution_enabled"] is False
    assert set(body["allowed_actions"]) == {
        "disk_cleanup",
        "restart_service",
        "report_high_cpu",
        "report_memory_pressure",
    }
    assert body["allowed_services"] == ["demo-svc"]


def test_dry_run_with_healthy_host_does_nothing(client):
    body = client.post("/api/remediation/dry-run").json()
    assert body["dry_run"] is True
    assert body["results"] == []
    assert "No issues" in body["summary"]


def test_dry_run_does_not_delete_files(make_client, cleanup_dir):
    old = make_file(cleanup_dir / "old.tmp", 500)
    client, _, _ = make_client(snapshot=disk_full())
    body = client.post("/api/remediation/dry-run").json()
    result = body["results"][0]
    assert result["action"] == "disk_cleanup"
    assert result["dry_run"] is True
    assert result["outcome"] == "dry_run"
    assert result["issue"]["type"] == "high_disk"
    assert result["data"]["eligible_files"] == 1
    assert result["verification"]["performed"] is False
    assert result["timestamp"]
    assert old.exists()


def test_dry_run_still_dry_when_dry_run_setting_is_false(make_client, cleanup_dir):
    old = make_file(cleanup_dir / "old.tmp")
    client, _, _ = make_client(snapshot=disk_full(), dry_run=False)
    body = client.post("/api/remediation/dry-run").json()
    assert body["dry_run"] is True
    assert old.exists()


def test_dry_run_reports_cpu_and_memory_without_killing(make_client):
    client, _, _ = make_client(snapshot=build_snapshot(cpu=97, memory=97))
    results = client.post("/api/remediation/dry-run").json()["results"]
    assert {r["action"] for r in results} == {"report_high_cpu", "report_memory_pressure"}
    assert all(r["outcome"] == "reported" for r in results)
    assert results[0]["data"]["top_processes"][0]["name"] == "busy-proc"


def test_dry_run_plans_service_restart_without_running_it(make_client):
    runner = FakeRunner({"demo-svc": "inactive"})
    client, _, runner = make_client(
        snapshot=build_snapshot(services={"demo-svc": "inactive"}), runner=runner
    )
    result = client.post("/api/remediation/dry-run").json()["results"][0]
    assert result["action"] == "restart_service"
    assert result["outcome"] == "dry_run"
    assert not any(call[:2] == ["systemctl", "restart"] for call in runner.calls)
    assert runner.states["demo-svc"] == "inactive"


def test_explicit_action_runs_as_preview_even_when_healthy(client):
    body = client.post("/api/remediation/dry-run", json={"actions": ["disk_cleanup"]}).json()
    assert body["results"][0]["outcome"] == "dry_run"
    assert body["results"][0]["issue"] is None


# ------------------------------------------------------------------ allowlist / injection


@pytest.mark.parametrize(
    "payload",
    [
        {"actions": ["rm -rf /"]},
        {"actions": ["kill_process"]},
        {"command": "rm -rf /"},
        {"path": "/etc"},
        {"actions": ["disk_cleanup"], "cleanup_dirs": ["/etc"]},
        {"service": "demo-svc; reboot"},
        {"service": "../../etc/passwd"},
    ],
)
def test_arbitrary_input_is_rejected(client, payload):
    assert client.post("/api/remediation/dry-run", json=payload).status_code == 422
    assert client.post("/api/remediation/execute", json={**payload, "confirm": True}).status_code in (
        401,
        403,
        422,
    )


def test_service_outside_allowlist_is_rejected(client):
    response = client.post("/api/remediation/dry-run", json={"service": "ssh"})
    assert response.status_code == 422
    assert "allowlist" in response.json()["message"]


# ------------------------------------------------------------------ guarded execution


def test_execute_blocked_while_dry_run_true(client, cleanup_dir):
    old = make_file(cleanup_dir / "old.tmp")
    response = client.post(
        "/api/remediation/execute", json={"confirm": True}, headers={"X-API-Key": "test-key"}
    )
    assert response.status_code == 403
    assert "DRY_RUN" in response.json()["message"]
    assert old.exists()


def test_execute_requires_configured_key(make_client):
    client, _, _ = make_client(dry_run=False, remediation_api_key=None)
    response = client.post("/api/remediation/execute", json={"confirm": True})
    assert response.status_code == 403


def test_execute_requires_valid_api_key(make_client):
    client, _, _ = make_client(dry_run=False)
    assert client.post("/api/remediation/execute", json={"confirm": True}).status_code == 401
    wrong = client.post(
        "/api/remediation/execute", json={"confirm": True}, headers={"X-API-Key": "wrong"}
    )
    assert wrong.status_code == 401


def test_execute_requires_confirm(make_client):
    client, _, _ = make_client(dry_run=False)
    response = client.post("/api/remediation/execute", json={}, headers={"X-API-Key": "test-key"})
    assert response.status_code == 400


def test_execute_cleans_only_eligible_files_and_verifies(make_client, cleanup_dir, tmp_path):
    expired = make_file(cleanup_dir / "expired.tmp", 1000)
    (cleanup_dir / "sub").mkdir()
    expired_log = make_file(cleanup_dir / "sub" / "old.log", 10)
    fresh = make_file(cleanup_dir / "fresh.tmp", 1000, mtime=time.time())
    wrong_ext = make_file(cleanup_dir / "report.pdf", 1000)
    outside = make_file(tmp_path / "outside.tmp", 1000)
    link = cleanup_dir / "link.tmp"
    link.symlink_to(outside)

    client, _, _ = make_client(snapshot=disk_full(), dry_run=False, disk_after=70.0)
    response = client.post(
        "/api/remediation/execute", json={"confirm": True}, headers={"X-API-Key": "test-key"}
    )
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["dry_run"] is False
    assert result["outcome"] == "executed"
    assert result["data"]["deleted_files"] == 2
    assert result["verification"] == {
        "performed": True,
        "passed": True,
        "detail": "/ usage 95.0% -> 70.0% (threshold 85.0%)",
    }
    assert not expired.exists() and not expired_log.exists()
    assert fresh.exists() and wrong_ext.exists()
    assert outside.exists() and link.is_symlink()


def test_execute_skips_cleanup_when_condition_absent(make_client, cleanup_dir):
    old = make_file(cleanup_dir / "old.tmp")
    client, _, _ = make_client(dry_run=False)
    response = client.post(
        "/api/remediation/execute",
        json={"confirm": True, "actions": ["disk_cleanup"]},
        headers={"X-API-Key": "test-key"},
    )
    result = response.json()["results"][0]
    assert result["outcome"] == "skipped"
    assert old.exists()


def test_execute_restarts_allowlisted_service_and_verifies(make_client):
    runner = FakeRunner({"demo-svc": "inactive"})
    client, _, runner = make_client(
        snapshot=build_snapshot(services={"demo-svc": "inactive"}), runner=runner, dry_run=False
    )
    response = client.post(
        "/api/remediation/execute", json={"confirm": True}, headers={"X-API-Key": "test-key"}
    )
    result = response.json()["results"][0]
    assert result["outcome"] == "executed"
    assert result["verification"]["passed"] is True
    assert ["systemctl", "restart", "demo-svc"] in runner.calls
    # Only fixed systemctl commands are ever executed.
    assert {tuple(c[:2]) for c in runner.calls} <= {("systemctl", "show"), ("systemctl", "restart")}


def test_execute_refuses_to_restart_active_service(make_client):
    runner = FakeRunner({"demo-svc": "active"})
    client, _, runner = make_client(
        snapshot=build_snapshot(services={"demo-svc": "inactive"}), runner=runner, dry_run=False
    )
    result = client.post(
        "/api/remediation/execute", json={"confirm": True}, headers={"X-API-Key": "test-key"}
    ).json()["results"][0]
    assert result["outcome"] == "skipped"
    assert not any(call[:2] == ["systemctl", "restart"] for call in runner.calls)


def test_failed_restart_is_reported(make_client):
    runner = FakeRunner({"demo-svc": "failed"}, restart_rc=1)
    client, _, _ = make_client(
        snapshot=build_snapshot(services={"demo-svc": "failed"}), runner=runner, dry_run=False
    )
    result = client.post(
        "/api/remediation/execute", json={"confirm": True}, headers={"X-API-Key": "test-key"}
    ).json()["results"][0]
    assert result["outcome"] == "failed"
    assert result["verification"]["performed"] is False


def test_history_is_recorded_and_exposed(make_client):
    client, _, _ = make_client(snapshot=build_snapshot(cpu=99))
    client.post("/api/remediation/dry-run")
    recent = client.get("/api/remediation/status").json()["recent_results"]
    assert recent[0]["action"] == "report_high_cpu"
    metrics_text = client.get("/metrics").text
    assert (
        sample_value(
            metrics_text,
            "cloudops_remediation_actions_total",
            action="report_high_cpu",
            outcome="reported",
        )
        == 1.0
    )


# ------------------------------------------------------------------ filesystem safety


@pytest.mark.parametrize(
    "path",
    ["/", "/etc", "/etc/cron.d", "/usr/local", "/tmp", "/var", "/var/log", "/home", "/home/alice",
     "/root", "relative/dir", "", "/proc/1", "/mnt"],
)  # fmt: skip
def test_dangerous_cleanup_dirs_are_refused(path):
    with pytest.raises(UnsafePathError):
        validate_cleanup_dir(path)


@pytest.mark.parametrize("path", ["/tmp/cloudops360", "/var/log/myapp", "/var/tmp/cloudops360", "/home/alice/tmp"])
def test_dedicated_cleanup_dirs_are_accepted(path):
    assert str(validate_cleanup_dir(path)).endswith(path.rsplit("/", 1)[-1])


def test_traversal_in_configured_dir_is_normalised_and_refused():
    with pytest.raises(UnsafePathError):
        validate_cleanup_dir("/tmp/cloudops360/../../etc")


def test_scan_rejects_symlinked_dir_that_points_at_protected_path(tmp_path):
    link = tmp_path / "evil"
    link.symlink_to("/etc")
    scan = scan_cleanup_candidates([str(link)], (".tmp",), 0, 10)
    assert scan.directories == []
    assert scan.rejected


def test_scan_respects_age_extension_and_cap(cleanup_dir):
    for index in range(5):
        make_file(cleanup_dir / f"f{index}.tmp", size=10 + index)
    make_file(cleanup_dir / "keep.txt")
    make_file(cleanup_dir / "new.tmp", mtime=time.time())
    scan = scan_cleanup_candidates([str(cleanup_dir)], (".tmp",), 24 * 3600, max_files=3)
    assert len(scan.candidates) == 3
    assert scan.truncated is True
    assert [c.size_bytes for c in scan.candidates] == [14, 13, 12]
