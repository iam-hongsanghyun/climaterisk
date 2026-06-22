"""Download & refine real public data into CLIMADA-ready catalog entries.

This is the platform's *ingestion* layer: turn a listed data source into a
``Hazard`` the physical runners consume via the local catalog, with no manual
file handling. Two refiners are wired:

  - ``ingest_dataapi``  — a CLIMADA Data API hazard (tropical cyclone, river
    flood, wildfire, earthquake) cached to HDF5 for offline / reproducible runs.
  - ``ingest_aqueduct`` — WRI Aqueduct flood return-period GeoTIFFs, read over
    GDAL ``/vsicurl`` for ONLY the portfolio's bounding box (no multi-GB
    download), assembled into a CLIMADA flood ``Hazard`` where each return
    period is one event and the event frequency is the incremental exceedance
    probability ``1/RP_i − 1/RP_{i+1}`` (so AAI is the proper lower-sum integral
    of the exceedance curve and ``calc_freq_curve`` reconstructs the return
    periods).

The catalog key ``(peril, climate_scenario, region)`` is computed the SAME way
the runners compute it (``region`` = single-country ISO3 of the asset points,
else ``"global"``), so an ingested hazard is found by the matching runner with
no extra configuration. Runs in the CLIMADA conda env only.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from climaterisk_worker import catalog

# --- Aqueduct Floods v2 (WRI, CC-BY 4.0) ---------------------------------------
_AQ_BASE = "http://wri-projects.s3.amazonaws.com/AqueductFloodTool/download/v2"
# Return periods (years) published for riverine flood; each is one event layer.
_AQ_RIVER_RPS = (5, 10, 25, 50, 100, 250, 500, 1000)
# One representative GCM keeps the fetch deterministic (full ensemble is large).
_AQ_GCM = "00000NorESM1-M"
_AQ_FUTURE_YEARS = (2030, 2050, 2080)
# Platform climate scenario -> Aqueduct emissions scenario (only 4p5 / 8p5 exist).
_AQ_SCENARIO = {"rcp26": "rcp4p5", "rcp45": "rcp4p5", "rcp60": "rcp8p5", "rcp85": "rcp8p5"}

# --- CLIMADA Data API future windows -------------------------------------------
_TC_REF_YEARS = (2040, 2060, 2080)
_RF_YEAR_RANGES = ("2010_2030", "2030_2050", "2050_2070", "2070_2090")
_RF_SCENARIO_MAP = {"rcp26": "rcp26", "rcp45": "rcp60", "rcp60": "rcp60", "rcp85": "rcp85"}


def _nearest(options: tuple[int, ...], target: int) -> int:
    return min(options, key=lambda y: (abs(y - target), y))


def _region_for_points(points: list[list[float]]) -> str:
    """Single-country ISO3 of the asset points, else ``"global"`` (mirrors the runners)."""
    import numpy as np
    from climada.util import coordinates as u_coord

    lats = [float(p[0]) for p in points]
    lons = [float(p[1]) for p in points]
    codes = [int(c) for c in u_coord.get_country_code(np.array(lats), np.array(lons))]
    iso: set[str | None] = set()
    for c in codes:
        iso.add(u_coord.country_to_iso([c], "alpha3")[0] if c != 0 else None)
    real = {c for c in iso if c}
    return next(iter(real)) if len(real) == 1 and None not in iso else "global"


def _bbox(
    points: list[list[float]], pad: float, max_span: float
) -> tuple[float, float, float, float]:
    """Padded lon/lat bounding box of the asset points, clipped to ``max_span`` degrees."""
    lats = [float(p[0]) for p in points]
    lons = [float(p[1]) for p in points]
    minlon, maxlon = min(lons) - pad, max(lons) + pad
    minlat, maxlat = min(lats) - pad, max(lats) + pad
    # Clip an over-wide box around its centre so a sparse portfolio can't pull a global read.
    clon, clat = (minlon + maxlon) / 2, (minlat + maxlat) / 2
    if maxlon - minlon > max_span:
        minlon, maxlon = clon - max_span / 2, clon + max_span / 2
    if maxlat - minlat > max_span:
        minlat, maxlat = clat - max_span / 2, clat + max_span / 2
    return (minlon, minlat, maxlon, maxlat)


# --- Aqueduct refiner ----------------------------------------------------------


def _aq_river_layers(scenario: str, year: int) -> tuple[str, list[tuple[int, str]]]:
    """Return ``(label, [(rp, url), ...])`` for the chosen scenario/year."""
    if scenario == "historical":
        label = "historical (WATCH 1980)"
        urls = [
            (rp, f"{_AQ_BASE}/inunriver_historical_000000000WATCH_1980_rp{rp:05d}.tif")
            for rp in _AQ_RIVER_RPS
        ]
        return label, urls
    aq_scen = _AQ_SCENARIO.get(scenario, "rcp8p5")
    yr = _nearest(_AQ_FUTURE_YEARS, year)
    label = f"{aq_scen} {_AQ_GCM} {yr}"
    urls = [
        (rp, f"{_AQ_BASE}/inunriver_{aq_scen}_{_AQ_GCM}_{yr}_rp{rp:05d}.tif")
        for rp in _AQ_RIVER_RPS
    ]
    return label, urls


def _incremental_frequency(rps: list[int]):  # type: ignore[no-untyped-def]
    """Event frequency = incremental exceedance probability ``1/rp_i − 1/rp_{i+1}``."""
    import numpy as np

    inv = 1.0 / np.array(sorted(rps), dtype=float)
    freq = inv.copy()
    freq[:-1] = inv[:-1] - inv[1:]  # largest RP keeps its full 1/rp mass
    return freq


def ingest_aqueduct(request: dict[str, Any]) -> dict[str, Any]:
    """Build a CLIMADA river-flood ``Hazard`` from Aqueduct RP GeoTIFFs over the bbox."""
    import numpy as np
    import rasterio
    from climada.hazard import Hazard
    from rasterio.windows import from_bounds
    from scipy import sparse

    from climaterisk_worker.hazard_convert import _centroids

    points = request["points"]
    scenario = request["scenario"]
    year = int(request["year"])
    pad = float(request.get("pad", 0.5))
    max_span = float(request.get("max_span", 8.0))
    if not points:
        raise ValueError("aqueduct ingest needs portfolio asset points to bound the download")

    region = _region_for_points(points)
    minlon, minlat, maxlon, maxlat = _bbox(points, pad, max_span)
    label, layers = _aq_river_layers(scenario, year)

    lat = lon = None
    rows: list[Any] = []
    used_rps: list[int] = []
    for rp, url in layers:
        try:
            with rasterio.open("/vsicurl/" + url) as ds:
                win = from_bounds(minlon, minlat, maxlon, maxlat, ds.transform)
                win = win.round_offsets().round_lengths()
                arr = ds.read(1, window=win).astype(float)
                if lat is None:
                    wt = ds.window_transform(win)
                    nrows, ncols = arr.shape
                    xs = wt.c + (np.arange(ncols) + 0.5) * wt.a
                    ys = wt.f + (np.arange(nrows) + 0.5) * wt.e
                    lon_g, lat_g = np.meshgrid(xs, ys)
                    lon, lat = lon_g.ravel(), lat_g.ravel()
                nd = ds.nodata
            flat = arr.ravel()
            if nd is not None:
                flat[flat == nd] = 0.0
            flat[~np.isfinite(flat)] = 0.0
            flat[flat < 0] = 0.0
        except Exception:  # a missing RP layer should not abort the whole ingest
            continue
        rows.append(flat)
        used_rps.append(rp)

    if len(used_rps) < 2 or lat is None:
        raise ValueError(f"Aqueduct returned no usable flood layers for bbox/{label}")

    order = np.argsort(used_rps)
    rps_sorted = [used_rps[i] for i in order]
    intensity = np.vstack([rows[i] for i in order])
    freq = _incremental_frequency(rps_sorted)
    n_ev = len(rps_sorted)

    haz = Hazard(
        haz_type="RF",
        units="m",
        centroids=_centroids(lat, lon),
        event_id=np.arange(1, n_ev + 1),
        event_name=[f"rp{rp}" for rp in rps_sorted],
        date=np.full(n_ev, int(f"{year if scenario != 'historical' else 1980}0701")),
        frequency=freq,
        intensity=sparse.csr_matrix(intensity),
        fraction=sparse.csr_matrix((intensity > 0).astype(float)),
    )
    haz.check()

    db = catalog.catalog_dir()
    peril_dir = db / "river_flood"
    peril_dir.mkdir(parents=True, exist_ok=True)
    fname = f"RF_{scenario}_{region}_{year}.hdf5"
    haz.write_hdf5(str(peril_dir / fname))
    return {
        "peril": "river_flood",
        "haz_type": "RF",
        "climate_scenario": scenario,
        "region": region,
        "year": year,
        "units": "m",
        "file": f"river_flood/{fname}",
        "n_events": int(haz.size),
        "n_centroids": int(haz.centroids.size),
        "source": f"WRI Aqueduct Floods v2 ({label}, RPs {rps_sorted})",
        "license": "CC-BY 4.0",
    }


# --- CLIMADA Data API refiner --------------------------------------------------


class _DataApiPlan(NamedTuple):
    """How to fetch a Data-API hazard and which keys to file it under in the catalog."""

    data_type: str
    properties: dict[str, str]
    catalog_scenario: str  # scenario key the matching runner looks up
    catalog_year: int  # year key the matching runner looks up
    src_scenario: str  # the Data-API-side scenario (for the provenance label)
    country_only: bool  # True => single-country fetch only (no global fallback)


def _dataapi_plan(peril: str, scenario: str, year: int, region: str) -> _DataApiPlan:
    """Map a platform ``(peril, scenario, year, region)`` to a Data-API fetch + catalog keys.

    Pure (no CLIMADA / network), so the mapping is unit-testable. ``catalog_scenario`` /
    ``catalog_year`` are the keys the matching physical runner looks up — for the
    geophysical / observed perils these are fixed (wildfire → ``historical``/2020,
    earthquake → ``observed``/2020), independent of the requested climate scenario.
    """
    if peril == "tropical_cyclone":
        ref_year = _nearest(_TC_REF_YEARS, year)
        props = {
            "event_type": "synthetic",
            "model_name": "random_walk",
            "climate_scenario": scenario,
            "ref_year": str(ref_year),
        }
        return _DataApiPlan("tropical_cyclone", props, scenario, ref_year, scenario, False)
    if peril == "river_flood":
        rf_scen = _RF_SCENARIO_MAP.get(scenario, "rcp60")
        year_range = next(
            (r for r in _RF_YEAR_RANGES if int(r[:4]) <= year <= int(r[5:])), "2030_2050"
        )
        props = {"climate_scenario": rf_scen, "year_range": year_range}
        return _DataApiPlan("river_flood", props, scenario, int(year_range[5:]), rf_scen, False)
    if peril == "wildfire":
        if region == "global":
            raise ValueError(
                "wildfire ingest needs a single-country portfolio (global set too large)"
            )
        props = {"spatial_coverage": "country", "country_iso3alpha": region}
        return _DataApiPlan("wildfire", props, "historical", 2020, "historical", True)
    if peril == "earthquake":
        if region == "global":
            raise ValueError(
                "earthquake ingest needs a single-country portfolio (global set too large)"
            )
        props = {
            "spatial_coverage": "country",
            "country_iso3alpha": region,
            "event_type": "observed",
        }
        return _DataApiPlan("earthquake", props, "observed", 2020, "observed", True)
    raise ValueError(f"Data API ingest does not support peril '{peril}'")


def ingest_dataapi(request: dict[str, Any]) -> dict[str, Any]:
    """Cache a CLIMADA Data API hazard (TC / river flood / wildfire / earthquake) to the catalog."""
    from climada.util.api_client import Client

    points = request["points"]
    peril = request["peril"]
    region = _region_for_points(points)
    plan = _dataapi_plan(peril, request["scenario"], int(request["year"]), region)
    client = Client()
    if plan.country_only:
        haz = client.get_hazard(plan.data_type, properties=dict(plan.properties))
    else:
        haz = _fetch_country_or_global(client, plan.data_type, dict(plan.properties), region)

    db = catalog.catalog_dir()
    peril_dir = db / peril
    peril_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{haz.haz_type}_{plan.catalog_scenario}_{region}_{plan.catalog_year}.hdf5"
    haz.write_hdf5(str(peril_dir / fname))
    return {
        "peril": peril,
        "haz_type": haz.haz_type,
        "climate_scenario": plan.catalog_scenario,
        "region": region,
        "year": plan.catalog_year,
        "units": haz.units,
        "file": f"{peril}/{fname}",
        "n_events": int(haz.size),
        "n_centroids": int(haz.centroids.size),
        "source": f"CLIMADA Data API ({peril}, {plan.src_scenario}, cached)",
        "license": "per CLIMADA Data API",
    }


def _fetch_country_or_global(client: Any, data_type: str, props: dict[str, str], region: str):  # type: ignore[no-untyped-def]
    """Fetch a country-coverage hazard if the region is known, else the global set."""
    if region != "global":
        try:
            return client.get_hazard(
                data_type,
                properties={**props, "spatial_coverage": "country", "country_iso3alpha": region},
            )
        except Exception:
            pass
    return client.get_hazard(data_type, properties={**props, "spatial_coverage": "global"})


# --- dispatch ------------------------------------------------------------------

_REFINERS = {"dataapi": ingest_dataapi, "aqueduct": ingest_aqueduct}


def run_ingest(request: dict[str, Any]) -> dict[str, Any]:
    """Dispatch an ingest request, register the result in the catalog, and report it."""
    source = request.get("source", "")
    refiner = _REFINERS.get(source)
    if refiner is None:
        return {"status": "error", "source": source, "detail": f"unknown ingest source '{source}'"}
    entry = refiner(request)
    catalog.register(entry)
    return {
        "status": "ok",
        "source": source,
        "peril": entry["peril"],
        "entry": entry,
        "detail": (
            f"Ingested {entry['peril']} → local catalog "
            f"({entry['n_events']} events × {entry['n_centroids']} centroids, "
            f"{entry['climate_scenario']} {entry['region']} {entry.get('year')})."
        ),
    }
