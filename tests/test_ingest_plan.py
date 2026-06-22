"""Tests for the Data-API ingest plan — the (peril → fetch + catalog keys) mapping.

``climaterisk_worker.ingest`` imports CLIMADA only lazily (inside the refiners), so
``_dataapi_plan`` is pure and testable in the lightweight backend env. The key
invariant: each entry is filed under the SAME ``(scenario, year)`` keys the matching
physical runner looks up — otherwise an ingested hazard is silently never found.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORKER = Path(__file__).resolve().parents[1] / "worker"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

from climaterisk_worker.ingest import _dataapi_plan  # noqa: E402


def test_tropical_cyclone_plan() -> None:
    p = _dataapi_plan("tropical_cyclone", "rcp45", 2050, "JPN")
    assert p.data_type == "tropical_cyclone"
    assert p.catalog_scenario == "rcp45"  # runner looks up the platform scenario
    assert p.catalog_year == 2040  # nearest of (2040, 2060, 2080) to 2050
    assert p.properties["climate_scenario"] == "rcp45"
    assert p.properties["ref_year"] == "2040"
    assert p.country_only is False


def test_river_flood_plan_maps_scenario_but_keys_by_platform() -> None:
    # rcp45 maps to the Data-API's rcp60 set, but the catalog is keyed by the platform
    # scenario (rcp45) — that is what _run_river_flood passes to catalog.load_hazard.
    p = _dataapi_plan("river_flood", "rcp45", 2055, "JPN")
    assert p.data_type == "river_flood"
    assert p.properties["climate_scenario"] == "rcp60"  # mapped for the fetch
    assert p.catalog_scenario == "rcp45"  # but filed under the platform scenario
    assert p.src_scenario == "rcp60"
    assert p.catalog_year == 2070  # year 2055 falls in the 2050_2070 window
    assert p.country_only is False


def test_wildfire_plan_fixed_historical_keys() -> None:
    p = _dataapi_plan("wildfire", "rcp85", 2050, "AUS")
    assert p.data_type == "wildfire"
    assert p.catalog_scenario == "historical"  # matches _run_wildfire lookup
    assert p.catalog_year == 2020
    assert p.properties == {"spatial_coverage": "country", "country_iso3alpha": "AUS"}
    assert p.country_only is True


def test_earthquake_plan_fixed_observed_keys() -> None:
    p = _dataapi_plan("earthquake", "rcp45", 2050, "JPN")
    assert p.data_type == "earthquake"
    assert p.catalog_scenario == "observed"  # matches _run_earthquake lookup
    assert p.catalog_year == 2020
    assert p.properties["event_type"] == "observed"
    assert p.country_only is True


@pytest.mark.parametrize("peril", ["wildfire", "earthquake"])
def test_single_country_perils_reject_global(peril: str) -> None:
    with pytest.raises(ValueError, match="single-country"):
        _dataapi_plan(peril, "rcp85", 2050, "global")


def test_unsupported_peril_rejected() -> None:
    with pytest.raises(ValueError, match="does not support"):
        _dataapi_plan("hailstorm", "rcp85", 2050, "JPN")
