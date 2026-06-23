"""Data routes — fetch curated open-source datasets into place (download tool)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from climaterisk.data.fetch import fetch_source

router = APIRouter(prefix="/data", tags=["data"])


@router.post("/fetch")
def fetch_open_data(source_id: str, country: str | None = None) -> dict[str, Any]:
    """Download a curated open-source dataset (by registry id) and place it where it belongs.

    ``country`` (ISO3) fills the per-country template for sources that need it. Returns the
    saved path + size, or a clear error for portal/login-gated sources.
    """
    return fetch_source(source_id, country)
