"""Filesystem safety rules for cleanup.

Cleanup is limited to directories the *operator* configured (CLEANUP_DIRS, never the API
caller), and inside them to regular, expired files with an allow-listed extension.
Symlinks are never followed or deleted.
"""

from __future__ import annotations

import os
import stat
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

PROTECTED_PATHS = frozenset(
    Path(p)
    for p in (
        "/", "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/lib32", "/lib64", "/media",
        "/mnt", "/opt", "/proc", "/root", "/run", "/sbin", "/srv", "/sys", "/tmp", "/usr",
        "/var", "/var/lib", "/var/log", "/Users",
    )
)  # fmt: skip
_SYSTEM_TOP_LEVEL = frozenset(
    {"bin", "boot", "dev", "etc", "lib", "lib32", "lib64", "proc", "sbin", "sys", "usr"}
)
_HOME_PARENTS = frozenset({"home", "Users"})


class UnsafePathError(ValueError):
    """The configured cleanup directory is not acceptable."""


def _check(path: Path) -> None:
    if any(protected.is_relative_to(path) for protected in PROTECTED_PATHS):
        raise UnsafePathError("refusing protected or top-level directory")
    parts = path.parts
    if len(parts) < 3:
        raise UnsafePathError("directory is too close to the filesystem root")
    if parts[1] in _SYSTEM_TOP_LEVEL:
        raise UnsafePathError("refusing system directory")
    if parts[1] in _HOME_PARENTS and len(parts) < 4:
        raise UnsafePathError("refusing a user's home directory")


def validate_cleanup_dir(raw: str) -> Path:
    """Return the resolved cleanup directory or raise ``UnsafePathError``."""
    if not raw or "\x00" in raw:
        raise UnsafePathError("empty or invalid path")
    path = Path(os.path.normpath(raw))
    if not path.is_absolute():
        raise UnsafePathError("cleanup directory must be an absolute path")
    _check(path)
    resolved = Path(os.path.realpath(path))
    _check(resolved)  # a symlink must not lead somewhere protected
    return resolved


@dataclass(frozen=True)
class CleanupCandidate:
    path: Path
    size_bytes: int


@dataclass
class CleanupScan:
    directories: list[Path] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)
    candidates: list[CleanupCandidate] = field(default_factory=list)
    truncated: bool = False

    @property
    def total_bytes(self) -> int:
        return sum(c.size_bytes for c in self.candidates)


def _evaluate(
    path: Path, root: Path, extensions: Sequence[str], cutoff: float
) -> CleanupCandidate | None:
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode):  # excludes symlinks, sockets, devices, ...
            return None
        if path.suffix.lower() not in extensions or info.st_mtime > cutoff:
            return None
        if not Path(os.path.realpath(path)).is_relative_to(root):
            return None
        return CleanupCandidate(path=path, size_bytes=info.st_size)
    except OSError:
        return None


def scan_cleanup_candidates(
    directories: Iterable[str],
    extensions: Sequence[str],
    min_age_seconds: float,
    max_files: int,
    now: float | None = None,
) -> CleanupScan:
    """Find (but never delete) files eligible for cleanup. Largest first, capped."""
    cutoff = (time.time() if now is None else now) - min_age_seconds
    scan = CleanupScan()
    for raw in directories:
        try:
            root = validate_cleanup_dir(raw)
        except UnsafePathError as exc:
            scan.rejected.append({"path": raw, "reason": str(exc)})
            continue
        if not root.is_dir():
            scan.rejected.append({"path": raw, "reason": "directory does not exist"})
            continue
        scan.directories.append(root)
        for dirpath, _dirs, files in os.walk(root, followlinks=False):
            for name in files:
                candidate = _evaluate(Path(dirpath) / name, root, extensions, cutoff)
                if candidate:
                    scan.candidates.append(candidate)
    scan.candidates.sort(key=lambda c: c.size_bytes, reverse=True)
    if len(scan.candidates) > max_files:
        scan.truncated = True
        scan.candidates = scan.candidates[:max_files]
    return scan


def delete_candidates(
    scan: CleanupScan, extensions: Sequence[str]
) -> tuple[list[CleanupCandidate], list[dict[str, str]]]:
    """Delete the scanned candidates after re-checking each one. Returns (deleted, errors)."""
    deleted: list[CleanupCandidate] = []
    errors: list[dict[str, str]] = []
    for candidate in scan.candidates:
        root = next((r for r in scan.directories if candidate.path.is_relative_to(r)), None)
        if root is None or _evaluate(candidate.path, root, extensions, float("inf")) is None:
            errors.append({"path": str(candidate.path), "error": "no longer eligible"})
            continue
        try:
            os.unlink(candidate.path)
            deleted.append(candidate)
        except OSError as exc:
            errors.append({"path": str(candidate.path), "error": type(exc).__name__})
    return deleted, errors
