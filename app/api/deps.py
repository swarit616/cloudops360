"""FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.container import AppContainer


def get_container(request: Request) -> AppContainer:
    """The application container created in ``create_app``."""
    return request.app.state.container


ContainerDep = Annotated[AppContainer, Depends(get_container)]
