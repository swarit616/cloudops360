"""Pytest fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.container import build_container
from app.main import create_app
from tests.helpers import FakeRunner, StaticCollector, build_snapshot, make_settings


@pytest.fixture
def cleanup_dir(tmp_path):
    path = tmp_path / "cleanup"
    path.mkdir()
    return path


@pytest.fixture
def make_client(tmp_path, cleanup_dir):
    """Factory: ``make_client(snapshot=..., runner=..., **settings_overrides)``."""

    def _make(snapshot=None, runner=None, disk_after=None, **overrides):
        settings = make_settings(tmp_path, **overrides)
        collector = StaticCollector(snapshot or build_snapshot(), disk_after=disk_after)
        runner = runner or FakeRunner({"demo-svc": "active"})
        container = build_container(settings, collector=collector, runner=runner)
        return TestClient(create_app(container)), container, runner

    return _make


@pytest.fixture
def client(make_client):
    return make_client()[0]
