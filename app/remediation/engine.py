"""Safe remediation engine.

Design rules (see docs/security.md):

* Only actions in ``RemediationAction`` exist. The API cannot supply commands, paths or scripts.
* ``DRY_RUN=true`` by default. Dry-run never changes anything; execution needs DRY_RUN=false,
  an API key and ``confirm=true`` (enforced by the API layer *and* re-checked here).
* Execution only happens when the triggering condition is really present.
* High CPU and memory pressure are report-only: processes are never killed.
* Every action returns the detected issue, proposed action, dry-run flag, result,
  timestamp and a verification result.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.logging_config import get_logger, log_event
from app.models.schemas import (
    Issue,
    IssueType,
    RemediationAction,
    RemediationReport,
    RemediationRequest,
    RemediationResult,
    RemediationStatus,
    SystemSnapshot,
    Verification,
)
from app.monitoring.services import DOWN_STATES, ServiceChecker
from app.monitoring.system import Collector, detect_issues
from app.remediation.safety import delete_candidates, scan_cleanup_candidates

logger = get_logger("remediation")

ACTION_FOR_ISSUE: dict[IssueType, RemediationAction] = {
    IssueType.HIGH_CPU: RemediationAction.REPORT_HIGH_CPU,
    IssueType.HIGH_LOAD: RemediationAction.REPORT_HIGH_CPU,
    IssueType.HIGH_MEMORY: RemediationAction.REPORT_MEMORY_PRESSURE,
    IssueType.HIGH_DISK: RemediationAction.DISK_CLEANUP,
    IssueType.SERVICE_DOWN: RemediationAction.RESTART_SERVICE,
}

_NO_VERIFICATION = Verification(performed=False, passed=None, detail="No verification performed")


class RemediationRejected(ValueError):
    """The request asked for something outside the allowlist (HTTP 422)."""


class ExecutionNotAllowed(PermissionError):
    """Execution was requested while DRY_RUN=true (HTTP 403)."""


class RemediationEngine:
    """Plans and (only when explicitly allowed) performs allow-listed remediation."""

    def __init__(
        self,
        settings: Settings,
        collector: Collector,
        services: ServiceChecker,
        on_action: Callable[[str, str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
        history_size: int = 50,
    ) -> None:
        self._settings = settings
        self._collector = collector
        self._services = services
        self._on_action = on_action
        self._sleep = sleep
        self._clock = clock
        self._history: deque[RemediationResult] = deque(maxlen=history_size)
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()  # one remediation run at a time
        self._handlers: dict[RemediationAction, Callable[..., RemediationResult]] = {
            RemediationAction.DISK_CLEANUP: self._disk_cleanup,
            RemediationAction.RESTART_SERVICE: self._restart_service,
            RemediationAction.REPORT_HIGH_CPU: self._report_cpu,
            RemediationAction.REPORT_MEMORY_PRESSURE: self._report_memory,
        }

    # ------------------------------------------------------------------ public API

    def status(self) -> RemediationStatus:
        with self._lock:
            recent = list(self._history)[-20:]
        s = self._settings
        return RemediationStatus(
            dry_run=s.dry_run,
            execution_enabled=(not s.dry_run) and bool(s.remediation_api_key),
            allowed_actions=list(RemediationAction),
            allowed_services=list(s.allowed_services),
            cleanup_dirs=list(s.cleanup_dirs),
            cleanup_extensions=list(s.cleanup_extensions),
            cleanup_min_age_hours=s.cleanup_min_age_hours,
            cleanup_max_files=s.cleanup_max_files,
            recent_results=recent,
        )

    def run(self, request: RemediationRequest, *, execute: bool) -> RemediationReport:
        """Plan and run remediation. ``execute=False`` is always a dry run."""
        if execute and self._settings.dry_run:
            raise ExecutionNotAllowed("Execution is disabled while DRY_RUN=true")
        if request.service and request.service not in self._settings.allowed_services:
            raise RemediationRejected("Requested service is not in the allowlist")

        dry_run = not execute
        with self._run_lock:
            snapshot = self._collector.snapshot()
            issues = detect_issues(snapshot, self._settings)
            plan = self._build_plan(request, issues)
            results: list[RemediationResult] = []
            for action, issue in plan:
                result = self._run_one(action, issue, request, snapshot, dry_run)
                self._record(result)
                results.append(result)

        if not results:
            summary = "No issues detected; no remediation required"
        else:
            mode = "dry-run" if dry_run else "execution"
            summary = (
                f"{len(results)} action(s) processed in {mode} mode for {len(issues)} issue(s)"
            )
        return RemediationReport(
            dry_run=dry_run, issues_detected=len(issues), results=results, summary=summary
        )

    # ------------------------------------------------------------------ planning

    @staticmethod
    def _build_plan(
        request: RemediationRequest, issues: list[Issue]
    ) -> list[tuple[RemediationAction, Issue | None]]:
        by_action: dict[RemediationAction, list[Issue]] = {}
        for issue in issues:
            by_action.setdefault(ACTION_FOR_ISSUE[issue.type], []).append(issue)
        wanted = list(dict.fromkeys(request.actions)) if request.actions else list(by_action)

        plan: list[tuple[RemediationAction, Issue | None]] = []
        for action in wanted:
            matching = by_action.get(action, [])
            if action is RemediationAction.RESTART_SERVICE:
                if request.service:
                    matching = [i for i in matching if i.target == request.service]
                if matching:
                    plan.extend((action, issue) for issue in matching)
                else:
                    plan.append((action, None))
            else:
                plan.append((action, matching[0] if matching else None))
        return plan

    def _run_one(
        self,
        action: RemediationAction,
        issue: Issue | None,
        request: RemediationRequest,
        snapshot: SystemSnapshot,
        dry_run: bool,
    ) -> RemediationResult:
        try:
            return self._handlers[action](issue, request, snapshot, dry_run)
        except Exception as exc:  # noqa: BLE001 - report instead of crashing the API
            log_event(
                logger,
                logging.ERROR,
                "remediation.handler_error",
                action=action.value,
                error_type=type(exc).__name__,
            )
            return self._result(
                action,
                issue,
                "n/a",
                dry_run,
                "failed",
                f"Unexpected error ({type(exc).__name__}); no further action taken",
            )

    def _record(self, result: RemediationResult) -> None:
        with self._lock:
            self._history.append(result)
        if self._on_action:
            self._on_action(result.action.value, result.outcome)
        log_event(
            logger,
            logging.INFO,
            "remediation.result",
            action=result.action.value,
            outcome=result.outcome,
            dry_run=result.dry_run,
            issue=result.issue.type.value if result.issue else None,
            verification_passed=result.verification.passed,
        )

    @staticmethod
    def _result(
        action: RemediationAction,
        issue: Issue | None,
        proposed: str,
        dry_run: bool,
        outcome: str,
        detail: str,
        data: dict[str, Any] | None = None,
        verification: Verification | None = None,
    ) -> RemediationResult:
        return RemediationResult(
            issue=issue,
            action=action,
            proposed_action=proposed,
            dry_run=dry_run,
            outcome=outcome,  # type: ignore[arg-type]
            detail=detail,
            data=data or {},
            verification=verification or _NO_VERIFICATION,
            timestamp=datetime.now(UTC),
        )

    # ------------------------------------------------------------------ handlers

    def _disk_cleanup(
        self,
        issue: Issue | None,
        request: RemediationRequest,
        snapshot: SystemSnapshot,
        dry_run: bool,
    ) -> RemediationResult:
        s = self._settings
        proposed = "Delete expired temp/log files inside the configured cleanup directories only"
        scan = scan_cleanup_candidates(
            s.cleanup_dirs,
            s.cleanup_extensions,
            s.cleanup_min_age_hours * 3600,
            s.cleanup_max_files,
            now=self._clock(),
        )
        data: dict[str, Any] = {
            "directories": [str(p) for p in scan.directories],
            "rejected_directories": scan.rejected,
            "eligible_files": len(scan.candidates),
            "eligible_bytes": scan.total_bytes,
            "truncated": scan.truncated,
            "largest_files": [
                {"path": str(c.path), "size_bytes": c.size_bytes} for c in scan.candidates[:10]
            ],
        }
        if dry_run:
            return self._result(
                RemediationAction.DISK_CLEANUP,
                issue,
                proposed,
                True,
                "dry_run",
                f"Would delete {len(scan.candidates)} file(s), freeing {scan.total_bytes} bytes",
                data,
            )
        if issue is None:
            return self._result(
                RemediationAction.DISK_CLEANUP,
                None,
                proposed,
                False,
                "skipped",
                "No disk usage issue is currently detected; nothing was deleted",
                data,
            )
        if not scan.candidates:
            return self._result(
                RemediationAction.DISK_CLEANUP,
                issue,
                proposed,
                False,
                "skipped",
                "No eligible files found in the configured cleanup directories",
                data,
            )

        before = self._disk_percent(issue.target)
        deleted, errors = delete_candidates(scan, s.cleanup_extensions)
        after = self._disk_percent(issue.target)
        data.update(
            deleted_files=len(deleted),
            freed_bytes=sum(c.size_bytes for c in deleted),
            errors=errors,
        )
        passed = after is not None and after < s.disk_threshold
        detail = (
            f"{issue.target} usage {before:.1f}% -> {after:.1f}% (threshold {s.disk_threshold:.1f}%)"
            if before is not None and after is not None
            else "Disk usage could not be re-measured"
        )
        outcome = "failed" if errors and not deleted else "executed"
        return self._result(
            RemediationAction.DISK_CLEANUP,
            issue,
            proposed,
            False,
            outcome,
            f"Deleted {len(deleted)} file(s), freed {data['freed_bytes']} bytes",
            data,
            Verification(performed=True, passed=passed, detail=detail),
        )

    def _disk_percent(self, mountpoint: str) -> float | None:
        snapshot = self._collector.snapshot(cpu_interval=None, include_services=False)
        for fs in snapshot.filesystems:
            if fs.mountpoint == mountpoint:
                return fs.percent
        return None

    def _restart_service(
        self,
        issue: Issue | None,
        request: RemediationRequest,
        snapshot: SystemSnapshot,
        dry_run: bool,
    ) -> RemediationResult:
        action = RemediationAction.RESTART_SERVICE
        name = issue.target if issue else request.service
        if not name:
            allowed = ", ".join(self._settings.allowed_services) or "none"
            return self._result(
                action,
                issue,
                "n/a",
                dry_run,
                "skipped",
                f"No service is down and none was requested (allow-listed: {allowed})",
            )
        proposed = f"Restart allow-listed service '{name}' via systemctl and verify it is active"
        if dry_run:
            return self._result(
                action, issue, proposed, True, "dry_run", f"Would restart service '{name}'"
            )

        state = self._services.state(name)
        if state not in DOWN_STATES:
            return self._result(
                action,
                issue,
                proposed,
                False,
                "skipped",
                f"Service '{name}' is '{state}', not inactive/failed; refusing to restart",
                {"state": state},
            )
        result = self._services.restart(name)
        if result.returncode != 0:
            return self._result(
                action,
                issue,
                proposed,
                False,
                "failed",
                f"Restart command exited with code {result.returncode}",
                {"stderr": result.stderr.strip()[:200]},
                Verification(performed=False, passed=None, detail="Restart did not succeed"),
            )
        self._sleep(self._settings.restart_verify_delay_seconds)
        new_state = self._services.state(name)
        return self._result(
            action,
            issue,
            proposed,
            False,
            "executed" if new_state == "active" else "failed",
            f"Restarted service '{name}'",
            {"state_before": state, "state_after": new_state},
            Verification(
                performed=True,
                passed=new_state == "active",
                detail=f"Service '{name}' is '{new_state}' after restart",
            ),
        )

    def _report_cpu(
        self,
        issue: Issue | None,
        request: RemediationRequest,
        snapshot: SystemSnapshot,
        dry_run: bool,
    ) -> RemediationResult:
        top = self._collector.top_processes("cpu", 5)
        names = ", ".join(f"{p.name}({p.pid}) {p.cpu_percent:.0f}%" for p in top) or "none"
        return self._result(
            RemediationAction.REPORT_HIGH_CPU,
            issue,
            "Report the top CPU consumers (no process is ever killed)",
            dry_run,
            "reported",
            f"Top CPU consumers: {names}",
            {
                "cpu_percent": snapshot.cpu.percent,
                "load_per_core": snapshot.load.per_core_1m,
                "top_processes": [p.model_dump() for p in top],
            },
            Verification(
                performed=False, passed=None, detail="Report-only action; nothing to verify"
            ),
        )

    def _report_memory(
        self,
        issue: Issue | None,
        request: RemediationRequest,
        snapshot: SystemSnapshot,
        dry_run: bool,
    ) -> RemediationResult:
        top = self._collector.top_processes("memory", 5)
        names = ", ".join(f"{p.name}({p.pid}) {p.memory_percent:.1f}%" for p in top) or "none"
        return self._result(
            RemediationAction.REPORT_MEMORY_PRESSURE,
            issue,
            "Report the top memory consumers (no process is ever killed)",
            dry_run,
            "reported",
            f"Top memory consumers: {names}",
            {
                "memory_percent": snapshot.memory.percent,
                "swap_percent": snapshot.memory.swap_percent,
                "available_bytes": snapshot.memory.available_bytes,
                "top_processes": [p.model_dump() for p in top],
            },
            Verification(
                performed=False, passed=None, detail="Report-only action; nothing to verify"
            ),
        )
