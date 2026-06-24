"""Footprint/polygon exposure: value-conserving disaggregation + per-asset re-aggregation.

``_eai_by_asset`` is pure (numpy) and runs in the backend env; ``_footprint_points``
needs shapely (worker env) and is skipped where absent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORKER = Path(__file__).resolve().parents[1] / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

from climaterisk_worker import physical  # noqa: E402

_SQUARE = {
    "type": "Polygon",
    "coordinates": [[[139.6, 35.6], [139.8, 35.6], [139.8, 35.8], [139.6, 35.8], [139.6, 35.6]]],
}


def test_eai_by_asset_aggregates_subpoints_back_to_assets() -> None:
    import numpy as np

    class _Imp:
        eai_exp = np.array([1.0, 2.0, 3.0, 4.0])

    # rows 0,1 -> asset 0 ; rows 2,3 -> asset 1
    out = physical._eai_by_asset(_Imp(), np.array([0, 0, 1, 1]), 2)
    assert out == [3.0, 7.0]


def test_footprint_points_disaggregates_polygon() -> None:
    pytest.importorskip("shapely")
    pts = physical._footprint_points(_SQUARE, res_deg=0.05)
    assert len(pts) >= 4
    assert all(35.6 <= lat <= 35.8 and 139.6 <= lon <= 139.8 for lat, lon in pts)


def test_footprint_points_caps_at_max() -> None:
    pytest.importorskip("shapely")
    pts = physical._footprint_points(_SQUARE, res_deg=0.005, max_points=16)
    assert len(pts) == 16


def test_footprint_points_samples_along_a_line() -> None:
    pytest.importorskip("shapely")
    line = {"type": "LineString", "coordinates": [[139.0, 35.0], [139.5, 35.2], [140.0, 35.0]]}
    pts = physical._footprint_points(line, res_deg=0.05)
    assert len(pts) >= 2  # a line has no interior — points are interpolated ALONG it
    assert pts[0] == (35.0, 139.0) and pts[-1] == (35.0, 140.0)  # endpoints preserved
    assert all(139.0 <= lon <= 140.0 for _, lon in pts)


def test_footprint_tiny_polygon_falls_back_to_centroid() -> None:
    pytest.importorskip("shapely")
    tiny = {
        "type": "Polygon",
        "coordinates": [[[0.0, 0.0], [0.001, 0.0], [0.001, 0.001], [0.0, 0.001], [0.0, 0.0]]],
    }
    pts = physical._footprint_points(tiny, res_deg=1.0)
    assert len(pts) == 1
