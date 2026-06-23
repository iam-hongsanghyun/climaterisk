"""Impact-function calibration — graceful degradation without EM-DAT.

EM-DAT is login-gated; the EM-DAT-path check runs before any CLIMADA import, so the
graceful path is offline-testable in the backend env.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORKER = Path(__file__).resolve().parents[1] / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

from climaterisk_worker.calibration import compute_calibration  # noqa: E402

_ASSET = {
    "id": "a",
    "name": "P",
    "lat": 35.6,
    "lon": 139.7,
    "value": 1.0e7,
    "currency": "USD",
    "tc_v_half": 70.0,
}
_REQ = {"assets": [_ASSET], "climate_scenario": "rcp45", "anchor_years": [2040]}


def test_calibration_needs_emdat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLIMATERISK_EMDAT_PATH", raising=False)
    out = compute_calibration(_REQ)
    assert out["status"] == "error"
    assert "EM-DAT" in out["detail"]


def test_calibration_no_assets() -> None:
    out = compute_calibration({"assets": [], "climate_scenario": "rcp45", "anchor_years": [2040]})
    assert out["status"] == "error"
