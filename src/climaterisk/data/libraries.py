"""Loader for the bundled methodology libraries (``assets/libraries/*.json``).

These are frozen, citable reference data (sectors, perils, scenarios, impact
functions). They are read-only at runtime and cached for the process lifetime.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from climaterisk.config import get_settings
from climaterisk.logger import get_logger

logger = get_logger(__name__)

_FILES = {
    "sectors": "sectors.json",
    "perils": "perils.json",
    "scenarios": "scenarios.json",
    "impact_functions": "impact_functions.json",
    "impf_presets": "impact_function_presets.json",
    "carbon_prices": "ngfs_carbon_prices.json",
    "data_sources": "data_sources.json",
}


def _load_file(filename: str) -> dict[str, Any]:
    path = get_settings().library_path / filename
    with path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


@lru_cache(maxsize=1)
def load_libraries() -> dict[str, dict[str, Any]]:
    """Load and cache all bundled libraries, keyed by name (sectors, perils, …)."""
    libraries = {name: _load_file(filename) for name, filename in _FILES.items()}
    logger.info("loaded %d bundled libraries from %s", len(libraries), get_settings().library_path)
    return libraries
