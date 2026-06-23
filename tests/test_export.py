"""Export route — per-asset row flattening (CSV/GeoJSON) from a run's output."""

from __future__ import annotations

from climaterisk.api.routers.run import _per_asset_rows


def test_flatten_physical_results() -> None:
    out = {
        "results": [
            {
                "peril": "tropical_cyclone",
                "per_asset": [{"id": "a", "lat": 1.0, "lon": 2.0, "eai": 5.0}],
            },
            {
                "peril": "river_flood",
                "per_asset": [{"id": "a", "lat": 1.0, "lon": 2.0, "eai": 3.0}],
            },
        ]
    }
    rows = _per_asset_rows(out)
    assert len(rows) == 2
    assert {r["peril"] for r in rows} == {"tropical_cyclone", "river_flood"}
    assert rows[0]["eai"] == 5.0


def test_flatten_forecast_top_level() -> None:
    out = {"per_asset": [{"id": "a", "lat": 1.0, "lon": 2.0, "eai": 9.0}]}
    rows = _per_asset_rows(out)
    assert len(rows) == 1 and rows[0]["eai"] == 9.0


def test_flatten_empty() -> None:
    assert _per_asset_rows({}) == []
