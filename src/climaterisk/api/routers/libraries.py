"""Library routes — expose the bundled methodology libraries to the UI."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from climaterisk.data.libraries import load_libraries

router = APIRouter(prefix="/libraries", tags=["libraries"])


@router.get("")
def get_all_libraries() -> dict[str, dict[str, Any]]:
    """Return every bundled library (sectors, perils, scenarios, impact_functions)."""
    return load_libraries()


@router.get("/{name}")
def get_library(name: str) -> dict[str, Any]:
    """Return a single named library, or 404 if it does not exist."""
    libraries = load_libraries()
    if name not in libraries:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"unknown library: {name}")
    return libraries[name]
