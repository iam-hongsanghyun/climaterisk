"""Tests for the Aqueduct flood layer plans (riverine + coastal URL construction).

Pure URL/plan logic — no CLIMADA, no network — so it runs in the backend env. The
filenames must match WRI Aqueduct's S3 naming, else the /vsicurl reads 404 and the
ingest finds no usable layers.
"""

from __future__ import annotations

import sys
from pathlib import Path

WORKER = Path(__file__).resolve().parents[1] / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

from climaterisk_worker.ingest import (  # noqa: E402
    _AQ_FLOOD,
    _aq_coast_layers,
    _aq_river_layers,
)


def test_flood_dispatch_table() -> None:
    assert _AQ_FLOOD["river_flood"][0] == "RF"
    assert _AQ_FLOOD["coastal_flood"][0] == "CF"
    assert _AQ_FLOOD["river_flood"][1] is _aq_river_layers
    assert _AQ_FLOOD["coastal_flood"][1] is _aq_coast_layers


def test_river_layers_future_and_historical() -> None:
    label, urls = _aq_river_layers("rcp45", 2050)  # rcp45 -> rcp4p5, nearest year 2050
    assert "rcp4p5" in label
    assert all(u.endswith(".tif") and "inunriver_rcp4p5_" in u for _, u in urls)
    assert any("_2050_rp" in u for _, u in urls)
    hlabel, hurls = _aq_river_layers("historical", 2050)
    assert "historical" in hlabel
    assert all("inunriver_historical_" in u for _, u in hurls)


def test_coastal_layers_future() -> None:
    label, urls = _aq_coast_layers("rcp85", 2050)  # rcp85 -> rcp8p5
    assert "rcp8p5" in label and "wtsub" in label
    rps = [rp for rp, _ in urls]
    assert rps == sorted(rps) and 2 in rps and 1000 in rps
    # e.g. inuncoast_rcp8p5_wtsub_2050_rp0010_0.tif (4-digit rp, with-subsidence, slr token)
    sample = dict(urls)[10]
    assert sample.endswith("inuncoast_rcp8p5_wtsub_2050_rp0010_0.tif")


def test_coastal_layers_historical() -> None:
    label, urls = _aq_coast_layers("historical", 2050)
    assert "historical" in label
    sample = dict(urls)[100]
    assert sample.endswith("inuncoast_historical_wtsub_hist_rp0100_0.tif")
