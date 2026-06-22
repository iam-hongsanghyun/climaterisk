"""Tests for the hazard-catalog manifest logic (worker package, no CLIMADA needed).

``climaterisk_worker.catalog`` imports CLIMADA only lazily (inside load_hazard), so
its manifest/lookup logic is testable in the lightweight backend env.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORKER = Path(__file__).resolve().parents[1] / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))


def _entry(region: str, year: int, n_events: int = 10) -> dict:
    return {
        "peril": "river_flood",
        "haz_type": "RF",
        "climate_scenario": "rcp85",
        "region": region,
        "year": year,
        "units": "m",
        "file": f"river_flood/RF_rcp85_{region}_{year}.hdf5",
        "n_events": n_events,
        "n_centroids": 5,
        "source": "test",
        "license": "test",
    }


def test_register_lookup_nearest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLIMATERISK_HAZARD_DB", str(tmp_path))
    from climaterisk_worker import catalog

    assert catalog.load_manifest() == []
    catalog.register(_entry("BGD", 2050))
    catalog.register(_entry("BGD", 2070))
    assert len(catalog.load_manifest()) == 2

    # nearest-year resolution
    assert catalog.lookup("river_flood", "rcp85", "BGD", 2052)["year"] == 2050
    assert catalog.lookup("river_flood", "rcp85", "BGD", 2069)["year"] == 2070
    # no match for a different region / peril
    assert catalog.lookup("river_flood", "rcp85", "JPN", 2050) is None
    assert catalog.lookup("wildfire", "rcp85", "BGD", 2050) is None


def test_register_dedupes_by_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLIMATERISK_HAZARD_DB", str(tmp_path))
    from climaterisk_worker import catalog

    catalog.register(_entry("BGD", 2050, n_events=10))
    catalog.register(_entry("BGD", 2050, n_events=99))  # same file -> replace
    entries = catalog.load_manifest()
    assert len(entries) == 1
    assert entries[0]["n_events"] == 99
