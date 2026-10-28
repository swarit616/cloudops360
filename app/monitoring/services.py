"""Safe command execution and service-state checks.

The only commands CloudOps360 can ever run are built in this module from fixed templates
and a validated, allow-listed service name. There is no shell and no user-supplied argv.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.config import SERVICE_NAME_RE
from app.models.schemas import ServiceStatus

# States that mean "the service should be running but is not".
DOWN_STATES = frozenset({"inactive", "failed"})


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner(Protocol):
    """Anything that can run a fixed argv list. Swapped for a fake in tests."""

    def run(self, args: Sequence[str], timeout: float = 5.0) -> CommandResult: ...


class SubprocessRunner:
    """Runs a command without a shell. Callers must only pass fixed, validated argv."""

    def run(self, args: Sequence[str], timeout: float = 5.0) -> CommandResult:
        try:
            proc = subprocess.run(  # noqa: S603 - argv is built from fixed templates only
                list(args),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                shell=False,
            )
        except FileNotFoundError:
            return CommandResult(127, stderr="command not found")
        except subprocess.TimeoutExpired:
            return CommandResult(124, stderr="command timed out")
        except OSError:
            return CommandResult(126, stderr="command could not be executed")
        return CommandResult(proc.returncode, proc.stdout, proc.stderr)


class ServiceChecker:
    """Reads and (for allow-listed names only) restarts systemd services."""

    def __init__(self, runner: CommandRunner, services: Sequence[str]) -> None:
        for name in services:
            if not SERVICE_NAME_RE.fullmatch(name):
                raise ValueError("invalid service name in allowlist")
        self._runner = runner
        self._services = tuple(services)

    @property
    def services(self) -> tuple[str, ...]:
        return self._services

    def _require_allowed(self, name: str) -> None:
        if name not in self._services or not SERVICE_NAME_RE.fullmatch(name):
            raise ValueError("service is not in the allowlist")

    def state(self, name: str) -> str:
        """Return ``active``/``inactive``/``failed``/... or ``not-found``/``unavailable``."""
        self._require_allowed(name)
        result = self._runner.run(
            ["systemctl", "show", name, "--property=LoadState", "--property=ActiveState"],
            timeout=3.0,
        )
        if result.returncode in (124, 126, 127):
            return "unavailable"
        props = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        if props.get("LoadState") == "not-found":
            return "not-found"
        return props.get("ActiveState") or "unknown"

    def check_all(self) -> list[ServiceStatus]:
        return [ServiceStatus(name=name, state=self.state(name)) for name in self._services]

    def restart(self, name: str) -> CommandResult:
        """Restart one allow-listed service. Needs sufficient privileges on the host."""
        self._require_allowed(name)
        return self._runner.run(["systemctl", "restart", name], timeout=30.0)
