"""Read-only view of the local hazard catalog manifest for the API.

The catalog itself (HDF5 hazards + ``catalog.json``) is built and consumed by the
CLIMADA worker (``data/hazard_db/``). The backend only needs to read the JSON
manifest to tell the UI which perils/regions have locally-ingested hazard data.
"""

from __future__ import annotations

import json
from typing import Any

from climaterisk.config import get_settings


def read_catalog() -> dict[str, Any]:
    """Return the hazard-catalog manifest: ``{dir, entries}`` (entries empty if none)."""
    catalog_path = get_settings().hazard_db_path / "catalog.json"
    if not catalog_path.is_file():
        return {"dir": str(catalog_path.parent), "entries": []}
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    return {"dir": str(catalog_path.parent), "entries": data.get("entries", [])}
