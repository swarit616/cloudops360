"""AWS and Azure endpoints. Always HTTP 200; ``configured`` says whether data is live."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ContainerDep
from app.cloud.models import CloudOverview

router = APIRouter(prefix="/api/cloud", tags=["cloud"])


@router.get("/aws", response_model=CloudOverview)
def aws(container: ContainerDep) -> CloudOverview:
    """AWS: EC2, EBS, CloudWatch, VPC and identity (cached; see CLOUD_CACHE_TTL_SECONDS)."""
    return container.aws.get_overview()


@router.get("/azure", response_model=CloudOverview)
def azure(container: ContainerDep) -> CloudOverview:
    """Azure: VMs, disks, resource groups, VNet/NSG and Azure Monitor (cached)."""
    return container.azure.get_overview()
