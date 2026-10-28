"""Shared behaviour for cloud adapters: caching, safe errors and account masking."""

from __future__ import annotations

import logging
import re
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

from app.cloud.models import CloudOverview
from app.logging_config import get_logger, log_event
from app.models.schemas import Provider

logger = get_logger("cloud")
T = TypeVar("T")

_ACCOUNT_ID = re.compile(r"\b\d{8}(\d{4})\b")


def mask_account_ids(text: str | None) -> str | None:
    """Mask 12-digit AWS account ids, keeping the last four digits."""
    if text is None:
        return None
    return _ACCOUNT_ID.sub(r"********\1", text)


def safe_error(exc: BaseException) -> str:
    """A short, non-sensitive description of an exception (error code or class name)."""
    response: Any = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = response.get("Error", {}).get("Code")
        if code:
            return str(code)
    return type(exc).__name__


class CloudAdapter(ABC):
    """Base class: one cached overview per provider, never raises to the caller."""

    provider: Provider

    def __init__(
        self, cache_ttl_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._ttl = cache_ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._cached: CloudOverview | None = None
        self._cached_at = 0.0

    def get_overview(self, force: bool = False) -> CloudOverview:
        """Return the cached overview, collecting a fresh one when the cache is stale."""
        with self._lock:
            fresh = self._cached is not None and (self._clock() - self._cached_at) < self._ttl
            if fresh and not force and self._cached is not None:
                return self._cached
            try:
                overview = self._collect()
            except Exception as exc:  # noqa: BLE001 - adapters must never break the API
                log_event(
                    logger,
                    logging.ERROR,
                    "cloud.collect_failed",
                    provider=self.provider.value,
                    error=safe_error(exc),
                )
                overview = self._not_configured(
                    f"{self.provider.value} data collection failed", safe_error(exc)
                )
            self._cached = overview
            self._cached_at = self._clock()
            return overview

    def peek(self) -> CloudOverview | None:
        """Last collected overview without triggering any cloud call."""
        return self._cached

    @abstractmethod
    def _collect(self) -> CloudOverview:
        """Collect a fresh overview (may call the cloud provider)."""

    def _not_configured(self, message: str, detail: str | None = None) -> CloudOverview:
        return CloudOverview(
            provider=self.provider, configured=False, message=message, detail=detail
        )

    def _section(self, label: str, func: Callable[[], T], default: T, warnings: list[str]) -> T:
        """Run one collection step; on failure record a warning and keep going."""
        try:
            return func()
        except Exception as exc:  # noqa: BLE001
            code = safe_error(exc)
            warnings.append(f"{label}: {code}")
            log_event(
                logger,
                logging.WARNING,
                "cloud.section_failed",
                provider=self.provider.value,
                section=label,
                error=code,
            )
            return default
