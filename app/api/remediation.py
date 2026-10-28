"""Remediation endpoints: status, dry-run (always safe) and guarded execution."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Body, Header, HTTPException

from app.api.deps import ContainerDep
from app.models.schemas import RemediationReport, RemediationRequest, RemediationStatus
from app.remediation.engine import ExecutionNotAllowed, RemediationRejected

router = APIRouter(prefix="/api/remediation", tags=["remediation"])


@router.get("/status", response_model=RemediationStatus)
def remediation_status(container: ContainerDep) -> RemediationStatus:
    """Mode, allowlists and the most recent remediation results."""
    return container.engine.status()


@router.post("/dry-run", response_model=RemediationReport)
def dry_run(
    container: ContainerDep,
    body: Annotated[RemediationRequest | None, Body()] = None,
) -> RemediationReport:
    """Preview what remediation *would* do. Never changes the host, whatever DRY_RUN says."""
    try:
        return container.engine.run(body or RemediationRequest(), execute=False)
    except RemediationRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/execute", response_model=RemediationReport)
def execute(
    container: ContainerDep,
    body: RemediationRequest,
    x_api_key: Annotated[str | None, Header()] = None,
) -> RemediationReport:
    """Controlled execution. Requires DRY_RUN=false, REMEDIATION_API_KEY and confirm=true."""
    settings = container.settings
    if settings.dry_run:
        raise HTTPException(
            status_code=403,
            detail="Execution is disabled (DRY_RUN=true). Use /api/remediation/dry-run.",
        )
    if not settings.remediation_api_key:
        raise HTTPException(
            status_code=403, detail="Execution requires REMEDIATION_API_KEY to be configured"
        )
    if not x_api_key or not hmac.compare_digest(
        x_api_key.encode(), settings.remediation_api_key.encode()
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to execute remediation")
    try:
        return container.engine.run(body, execute=True)
    except RemediationRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExecutionNotAllowed as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
