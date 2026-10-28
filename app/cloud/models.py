"""Provider-neutral models for discovered cloud resources."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.schemas import Provider, utcnow


class CloudInstance(BaseModel):
    provider: Provider
    id: str
    name: str | None = None
    state: str
    instance_type: str | None = None
    region: str | None = None
    zone: str | None = None
    private_ip: str | None = None
    public_ip: str | None = None
    launch_time: datetime | None = None


class CloudVolume(BaseModel):
    provider: Provider
    id: str
    name: str | None = None
    size_gb: int | None = None
    state: str | None = None
    volume_type: str | None = None
    encrypted: bool | None = None
    attached_to: str | None = None
    region: str | None = None


class CloudNetwork(BaseModel):
    """A VPC / subnet (AWS) or VNet / NSG (Azure)."""

    provider: Provider
    id: str
    name: str | None = None
    kind: str
    cidrs: list[str] = Field(default_factory=list)
    region: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ResourceGroup(BaseModel):
    provider: Provider = Provider.AZURE
    name: str
    location: str | None = None


class CloudMetricPoint(BaseModel):
    provider: Provider
    resource_id: str
    metric: str
    value: float
    unit: str | None = None
    timestamp: datetime | None = None


class CloudOverview(BaseModel):
    """What ``GET /api/cloud/<provider>`` returns.

    When credentials are missing only ``provider``, ``configured`` and ``message`` carry
    information, e.g. ``{"configured": false, "message": "AWS credentials are not configured"}``.
    """

    provider: Provider
    configured: bool
    message: str
    detail: str | None = None
    region: str | None = None
    identity: dict[str, Any] | None = None
    instances: list[CloudInstance] = Field(default_factory=list)
    volumes: list[CloudVolume] = Field(default_factory=list)
    networks: list[CloudNetwork] = Field(default_factory=list)
    resource_groups: list[ResourceGroup] = Field(default_factory=list)
    metrics: list[CloudMetricPoint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    collected_at: datetime = Field(default_factory=utcnow)
