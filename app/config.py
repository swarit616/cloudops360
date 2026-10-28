"""Application configuration, loaded from environment variables.

Every tunable value (thresholds, allowlists, feature switches) lives here so that
business logic never hardcodes it. Values are validated at start-up so that a typo in
``.env`` fails fast with a readable message instead of misbehaving later.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

# Service names are validated everywhere they are used (config, API, command builder).
SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,64}$")

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class ConfigError(ValueError):
    """Raised when an environment variable holds an invalid value."""


def _get_str(env: Mapping[str, str], name: str, default: str | None) -> str | None:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def _get_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigError(f"{name} must be true or false")


def _get_float(
    env: Mapping[str, str],
    name: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be between {minimum:g} and {maximum:g}")
    return value


def _get_list(env: Mapping[str, str], name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = env.get(name)
    if raw is None:
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings. Construct directly in tests, or use ``from_env``."""

    app_env: str = "development"
    log_level: str = "INFO"

    # Remediation safety. DRY_RUN=true means nothing is ever changed on the host.
    dry_run: bool = True
    remediation_api_key: str | None = field(default=None, repr=False)

    # Detection thresholds. Load is expressed per logical CPU core (1.0 = fully busy).
    cpu_threshold: float = 85.0
    memory_threshold: float = 85.0
    disk_threshold: float = 85.0
    load_threshold: float = 1.5

    # Local diagnostics / remediation scope.
    disk_path: str = "/"
    cleanup_dirs: tuple[str, ...] = ("/tmp/cloudops360",)  # noqa: S108 - dedicated demo dir
    cleanup_extensions: tuple[str, ...] = (".tmp", ".log", ".gz", ".old")
    cleanup_min_age_hours: float = 24.0
    cleanup_max_files: int = 100
    allowed_services: tuple[str, ...] = ("cloudops-demo",)
    restart_verify_delay_seconds: float = 2.0

    # Cloud integrations (credentials are never stored here; SDK credential chains are used).
    aws_enabled: bool = True
    aws_region: str = "us-east-1"
    aws_profile: str | None = None
    azure_enabled: bool = True
    azure_subscription_id: str | None = None
    cloud_cache_ttl_seconds: float = 60.0
    cloud_refresh_seconds: float = 60.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build settings from ``env`` (defaults to ``os.environ``)."""
        env = os.environ if env is None else env

        log_level = (_get_str(env, "LOG_LEVEL", "INFO") or "INFO").upper()
        if not isinstance(logging.getLevelName(log_level), int):
            raise ConfigError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL")

        services = _get_list(env, "ALLOWED_SERVICES", cls.allowed_services)
        for name in services:
            if not SERVICE_NAME_RE.fullmatch(name):
                raise ConfigError("ALLOWED_SERVICES contains an invalid service name")

        extensions = tuple(
            ext if ext.startswith(".") else f".{ext}"
            for ext in (
                e.lower() for e in _get_list(env, "CLEANUP_EXTENSIONS", cls.cleanup_extensions)
            )
        )

        return cls(
            app_env=_get_str(env, "APP_ENV", "development") or "development",
            log_level=log_level,
            dry_run=_get_bool(env, "DRY_RUN", True),
            remediation_api_key=_get_str(env, "REMEDIATION_API_KEY", None),
            cpu_threshold=_get_float(env, "CPU_THRESHOLD", 85.0, 1, 100),
            memory_threshold=_get_float(env, "MEMORY_THRESHOLD", 85.0, 1, 100),
            disk_threshold=_get_float(env, "DISK_THRESHOLD", 85.0, 1, 100),
            load_threshold=_get_float(env, "LOAD_THRESHOLD", 1.5, 0.1, 100),
            disk_path=_get_str(env, "DISK_PATH", "/") or "/",
            cleanup_dirs=_get_list(env, "CLEANUP_DIRS", cls.cleanup_dirs),
            cleanup_extensions=extensions,
            cleanup_min_age_hours=_get_float(env, "CLEANUP_MIN_AGE_HOURS", 24.0, 0, 8760),
            cleanup_max_files=int(_get_float(env, "CLEANUP_MAX_FILES", 100, 1, 10000)),
            allowed_services=services,
            restart_verify_delay_seconds=_get_float(
                env, "RESTART_VERIFY_DELAY_SECONDS", 2.0, 0, 60
            ),
            aws_enabled=_get_bool(env, "AWS_ENABLED", True),
            aws_region=_get_str(env, "AWS_DEFAULT_REGION", "us-east-1") or "us-east-1",
            aws_profile=_get_str(env, "AWS_PROFILE", None),
            azure_enabled=_get_bool(env, "AZURE_ENABLED", True),
            azure_subscription_id=_get_str(env, "AZURE_SUBSCRIPTION_ID", None),
            cloud_cache_ttl_seconds=_get_float(env, "CLOUD_CACHE_TTL_SECONDS", 60.0, 0, 3600),
            cloud_refresh_seconds=_get_float(env, "CLOUD_REFRESH_SECONDS", 60.0, 0, 3600),
        )

    def thresholds(self) -> dict[str, float]:
        """Detection thresholds as a plain mapping (used by the API and metrics)."""
        return {
            "cpu_percent": self.cpu_threshold,
            "memory_percent": self.memory_threshold,
            "disk_percent": self.disk_threshold,
            "load_per_core": self.load_threshold,
        }

    def public_dict(self) -> dict[str, Any]:
        """Settings that are safe to expose in logs or API responses (no secrets)."""
        return {
            "app_env": self.app_env,
            "dry_run": self.dry_run,
            "remediation_execution_configured": bool(self.remediation_api_key),
            "thresholds": self.thresholds(),
            "disk_path": self.disk_path,
            "allowed_services": list(self.allowed_services),
            "aws_enabled": self.aws_enabled,
            "azure_enabled": self.azure_enabled,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings for the running process."""
    return Settings.from_env()
