"""Local Linux diagnostics endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import ContainerDep
from app.logging_config import get_logger, log_event
from app.models.schemas import DiagnosticsResponse, IssueType
from app.monitoring.system import detect_issues

router = APIRouter(prefix="/api", tags=["diagnostics"])
logger = get_logger("diagnostics")

_RECOMMENDATIONS: dict[IssueType, str] = {
    IssueType.HIGH_CPU: "Review top CPU processes below; check for runaway jobs or scale out.",
    IssueType.HIGH_LOAD: "Load per core is high: check CPU saturation, disk I/O wait and blocked processes.",
    IssueType.HIGH_MEMORY: "Review top memory consumers; look for leaks and check swap usage.",
    IssueType.HIGH_DISK: (
        "Run scripts/disk_check.sh to find large paths, then POST /api/remediation/dry-run "
        "to preview the safe cleanup."
    ),
    IssueType.SERVICE_DOWN: (
        "Inspect 'systemctl status' and 'journalctl -u <service>'; remediation can restart "
        "allow-listed services only."
    ),
}


@router.get("/diagnostics", response_model=DiagnosticsResponse)
def diagnostics(
    container: ContainerDep, top: int = Query(default=5, ge=1, le=20)
) -> DiagnosticsResponse:
    """Full local diagnostics: snapshot, threshold breaches, top processes, advice."""
    try:
        snapshot = container.collector.snapshot()
        top_cpu = container.collector.top_processes("cpu", top)
        top_memory = container.collector.top_processes("memory", top)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, logging.ERROR, "diagnostics.failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=503, detail="Diagnostics are temporarily unavailable") from exc

    issues = detect_issues(snapshot, container.settings)
    recommendations = list(dict.fromkeys(_RECOMMENDATIONS[i.type] for i in issues))
    return DiagnosticsResponse(
        healthy=not issues,
        snapshot=snapshot,
        issues=issues,
        top_cpu_processes=top_cpu,
        top_memory_processes=top_memory,
        thresholds=container.settings.thresholds(),
        recommendations=recommendations or ["No action needed: all metrics are within thresholds."],
    )
