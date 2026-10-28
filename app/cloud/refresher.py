"""Background refresh of cloud overviews so /metrics never waits on a cloud API."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterable

from app.cloud.base import CloudAdapter, safe_error
from app.logging_config import get_logger, log_event

logger = get_logger("cloud.refresher")


class CloudRefresher:
    """Periodically refreshes each adapter in a daemon thread (disabled when interval <= 0)."""

    def __init__(self, adapters: Iterable[CloudAdapter], interval_seconds: float) -> None:
        self._adapters = list(adapters)
        self._interval = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._interval <= 0 or self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="cloud-refresher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            for adapter in self._adapters:
                try:
                    adapter.get_overview(force=True)
                except Exception as exc:  # noqa: BLE001
                    log_event(
                        logger, logging.ERROR, "cloud.refresh_failed", error=safe_error(exc)
                    )
            self._stop.wait(self._interval)
