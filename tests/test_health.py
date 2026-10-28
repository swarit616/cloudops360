"""Health, status, hosts and metrics endpoints."""

from __future__ import annotations

from tests.helpers import build_snapshot, sample_value


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "cloudops360"
    assert body["version"]


def test_request_id_is_generated_and_echoed(client):
    generated = client.get("/health").headers["x-request-id"]
    assert len(generated) == 32
    echoed = client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert echoed.headers["x-request-id"] == "trace-123"


def test_unsafe_request_id_is_replaced(client):
    response = client.get("/health", headers={"X-Request-ID": "bad id\twith spaces!"})
    assert response.headers["x-request-id"] != "bad id\twith spaces!"


def test_status_healthy(client):
    body = client.get("/api/status").json()
    assert body["status"] == "healthy"
    assert body["dry_run"] is True
    assert body["issues"] == []
    assert {c["provider"] for c in body["cloud"]} == {"AWS", "AZURE"}
    assert all(c["configured"] is False for c in body["cloud"])


def test_status_degraded_when_threshold_breached(make_client):
    client, _, _ = make_client(snapshot=build_snapshot(cpu=97.0))
    body = client.get("/api/status").json()
    assert body["status"] == "degraded"
    assert body["issues"][0]["type"] == "high_cpu"


def test_hosts_lists_local_host_and_counts(client):
    body = client.get("/api/hosts").json()
    assert body["counts"] == {"LOCAL": 1, "AWS": 0, "AZURE": 0}
    assert body["hosts"][0]["provider"] == "LOCAL"
    assert body["hosts"][0]["state"] == "up"


def test_metrics_endpoint_exposes_prometheus_series(client):
    client.get("/metrics")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    for name in (
        "cloudops_cpu_percent",
        "cloudops_memory_percent",
        "cloudops_load_per_core",
        "cloudops_uptime_seconds",
        "cloudops_network_bytes_total",
        "cloudops_http_requests_total",
    ):
        assert sample_value(text, name) is not None, name
    assert sample_value(text, "cloudops_disk_percent", mountpoint="/", fstype="ext4") == 30.0
    assert sample_value(text, "cloudops_host_up") == 1.0
    assert sample_value(text, "cloudops_dry_run") == 1.0
    assert sample_value(text, "cloudops_cloud_configured", provider="AWS") == 0.0
    assert sample_value(text, "cloudops_cloud_configured", provider="AZURE") == 0.0


def test_metrics_report_active_issue(make_client):
    client, _, _ = make_client(snapshot=build_snapshot(memory=99.0))
    text = client.get("/metrics").text
    assert sample_value(text, "cloudops_issue_active", type="high_memory") == 1.0
    assert sample_value(text, "cloudops_issue_active", type="high_cpu") == 0.0


def test_unknown_route_returns_json_error(client):
    response = client.get("/nope")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert body["request_id"]
