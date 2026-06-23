"""Catalog-first damage perils (hail, landslide, tc_rain) — registration + graceful degradation.

These perils are not in the CLIMADA Data API, so with no locally-ingested hazard the runner
must fail with a clear "ingest first" message. The lookup runs before any CLIMADA-heavy work,
but the runner imports CLIMADA, so the graceful path is exercised in the worker env.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORKER = Path(__file__).resolve().parents[1] / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

from climaterisk_worker import physical  # noqa: E402

_ASSET = {
    "id": "a",
    "name": "Site",
    "lat": 35.6,
    "lon": 139.7,
    "value": 1.0e7,
    "currency": "USD",
    "wf_max_mdd": 0.4,
}


_PERILS = ["hail", "landslide", "tc_rain", "drought", "crop_yield", "low_flow", "heatwave"]


@pytest.mark.parametrize("peril", _PERILS)
def test_catalog_peril_registered(peril: str) -> None:
    assert peril in physical._RUNNERS
    assert peril in physical._CATALOG_PERILS


@pytest.mark.parametrize("peril", _PERILS)
def test_catalog_peril_needs_ingest(peril: str, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    pytest.importorskip("climada")
    # point the catalog at an empty dir so no hazard is found
    monkeypatch.setenv("CLIMATERISK_HAZARD_DB", str(tmp_path))
    with pytest.raises(ValueError, match="no local hazard"):
        physical._RUNNERS[peril]([_ASSET], "rcp45", [2050])
