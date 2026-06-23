"""Operational forecast — input guard + graceful degradation.

The ECMWF happy path needs a live feed (active TCs only) and is not offline-testable; the
no-assets guard and the engine-unavailable degradation are.
"""

from __future__ import annotations

import sys
from pathlib import Path

WORKER = Path(__file__).resolve().parents[1] / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

from climaterisk_worker.forecast import compute_forecast  # noqa: E402


def test_forecast_no_assets() -> None:
    out = compute_forecast({"assets": []})
    assert out["status"] == "error"
    assert "no assets" in out["detail"]
