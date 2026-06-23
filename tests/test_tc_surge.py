"""TC storm surge (TCSurgeBathtub) — registration + graceful degradation.

The runner derives a surge hazard from the TC wind hazard + a Copernicus DEM. With no
DEM configured it must fail with a clear, actionable error (offline-testable — the DEM
check runs before any CLIMADA import). The happy path needs a DEM and is exercised
manually / in the worker env.
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
    "name": "Port",
    "lat": 35.6,
    "lon": 139.7,
    "value": 1.0e7,
    "currency": "USD",
    "tc_v_half": 70.0,
    "flood_depth_m": [0, 0.5, 1, 2, 3, 4, 5, 6],
    "flood_mdr": [0, 0.25, 0.4, 0.6, 0.75, 0.85, 0.92, 0.95],
}


def test_tc_surge_registered() -> None:
    assert "tc_surge" in physical._RUNNERS


def test_tc_surge_requires_dem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLIMATERISK_DEM_PATH", raising=False)
    with pytest.raises(ValueError, match="DEM"):
        physical._run_tc_surge([_ASSET], "rcp45", [2040])
