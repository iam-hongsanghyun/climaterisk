"""CLIMADA physical-risk computation.

Perils (climada v6.x, all hazard data from the CLIMADA Data API — no petals needed):
  - tropical_cyclone (TC): Emanuel damage function, per-asset ``v_half`` (vulnerability).
  - river_flood (RF): flood-depth hazard + per-asset depth-damage curve.

Each peril computes the FUTURE horizon and a PRESENT-day baseline, and reports the
delta. Future estimation comes from the Data API's future hazard sets:
  - TC: climate_scenario (rcp26/45/60/85) × ref_year (2040/2060/2080); present = "None".
  - RF: climate_scenario (rcp26/60/85) × year_range; present = historical / 1980_2000.

Per-asset vulnerability params (``tc_v_half``, flood depth-damage curve) are resolved
by the backend and arrive in each asset dict — this module reads them directly.

Returns plain dicts matching ``climaterisk.engines.base``.
"""

from __future__ import annotations

from typing import Any

from climaterisk_worker import catalog

_TC_REF_YEARS = (2040, 2060, 2080)
# River-flood future window midpoints available from the Data API.
_RF_YEAR_RANGES = ("2010_2030", "2030_2050", "2050_2070", "2070_2090")
# RF publishes rcp26/60/85 only; map the platform's climate scenario to the nearest.
_RF_SCENARIO_MAP = {"rcp26": "rcp26", "rcp45": "rcp60", "rcp60": "rcp60", "rcp85": "rcp85"}
_RETURN_PERIODS = [10, 25, 50, 100, 250]


def climada_available() -> bool:
    """Return True if the CLIMADA package can be imported in this environment."""
    try:
        import climada  # noqa: F401
    except ImportError:
        return False
    return True


def _nearest(options: tuple[int, ...], target: int) -> int:
    return min(options, key=lambda y: (abs(y - target), y))


def _per_asset_iso3(lats: list[float], lons: list[float]) -> list[str | None]:
    """Return the ISO3 country for each asset (None where unresolved/ocean)."""
    import numpy as np
    from climada.util import coordinates as u_coord

    codes = [int(c) for c in u_coord.get_country_code(np.array(lats), np.array(lons))]
    out: list[str | None] = []
    for c in codes:
        if c == 0:
            out.append(None)
        else:
            out.append(u_coord.country_to_iso([c], "alpha3")[0])
    return out


def _single_country_iso3(iso3s: list[str | None]) -> str | None:
    """Return the common ISO3 if all assets share one country, else None."""
    uniq = {c for c in iso3s if c is not None}
    return next(iter(uniq)) if len(uniq) == 1 and None not in iso3s else None


def _build_exposures(assets: list[dict[str, Any]], impf_col: str, impf_ids: list[int]):  # type: ignore[no-untyped-def]
    import pandas as pd
    from climada.entity import Exposures

    return Exposures(
        pd.DataFrame(
            {
                "latitude": [a["lat"] for a in assets],
                "longitude": [a["lon"] for a in assets],
                "value": [float(a["value"]) for a in assets],
                impf_col: impf_ids,
            }
        ),
        value_unit=assets[0]["currency"] if assets else "USD",
    )


def _impact(exp, impf_set, haz):  # type: ignore[no-untyped-def]
    from climada.engine import ImpactCalc

    return ImpactCalc(exp, impf_set, haz).impact(save_mat=True, assign_centroids=True)


def _run_tropical_cyclone(
    assets: list[dict[str, Any]],
    climate_scenario: str,
    anchor_years: list[int],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from climada.entity import ImpactFuncSet
    from climada.entity.impact_funcs.trop_cyclone import ImpfTropCyclone
    from climada.util.api_client import Client

    ref_year = _nearest(_TC_REF_YEARS, max(anchor_years) if anchor_years else _TC_REF_YEARS[0])
    iso3s = _per_asset_iso3([a["lat"] for a in assets], [a["lon"] for a in assets])
    iso3 = _single_country_iso3(iso3s)

    # One Emanuel impact function per distinct v_half; assign each asset to its id.
    v_halves = sorted({round(float(a["tc_v_half"]), 1) for a in assets})
    impf_id_by_v = {v: i + 1 for i, v in enumerate(v_halves)}
    impf_set = ImpactFuncSet(
        [ImpfTropCyclone.from_emanuel_usa(impf_id=i + 1, v_half=v) for i, v in enumerate(v_halves)]
    )
    impf_ids = [impf_id_by_v[round(float(a["tc_v_half"]), 1)] for a in assets]
    exp = _build_exposures(assets, "impf_TC", impf_ids)

    client = Client()

    def fetch(scenario: str, year: int | None):  # type: ignore[no-untyped-def]
        props: dict[str, str] = {
            "event_type": "synthetic",
            "model_name": "random_walk",
            "climate_scenario": scenario,
        }
        if year is not None:
            props["ref_year"] = str(year)
        if iso3 is not None:
            try:
                return client.get_hazard(
                    "tropical_cyclone",
                    properties={**props, "spatial_coverage": "country", "country_iso3alpha": iso3},
                )
            except Exception:
                pass
        return client.get_hazard(
            "tropical_cyclone", properties={**props, "spatial_coverage": "global"}
        )

    # Future-hazard resolution: local catalog first; then either the Data API's future
    # set (default) or Knutson/Jewson climate-change scaling of the present hazard
    # (opt-in via options["tc_future_method"]=="knutson" — derives a future for any
    # scenario/year, frequency-scaled per Jewson 2022).
    use_knutson = bool(options and options.get("tc_future_method") == "knutson")
    cat_haz = catalog.load_hazard("tropical_cyclone", climate_scenario, iso3 or "global", ref_year)
    present_haz = fetch("None", None)
    if cat_haz is not None:
        future_haz, src = cat_haz, "local catalog"
    elif use_knutson:
        rcp = {"rcp26": "2.6", "rcp45": "4.5", "rcp60": "6.0", "rcp85": "8.5"}.get(
            climate_scenario, "4.5"
        )
        future_haz = present_haz.apply_climate_scenario_knu(scenario=rcp, target_year=ref_year)
        src = f"Knutson/Jewson scaling (rcp{rcp}, {ref_year})"
    else:
        future_haz, src = fetch(climate_scenario, ref_year), f"{iso3 or 'global'} Data API"
    future = _impact(exp, impf_set, future_haz)
    present = _impact(exp, impf_set, present_haz)

    eai = [float(x) for x in future.eai_exp]
    fc = future.calc_freq_curve(_RETURN_PERIODS)
    present_aai = float(present.aai_agg)
    future_aai = float(future.aai_agg)
    delta = ((future_aai - present_aai) / present_aai * 100.0) if present_aai > 0 else None

    return {
        "peril": "tropical_cyclone",
        "status": "ok",
        "target_year": ref_year,
        "aai_agg": future_aai,
        "present_aai_agg": present_aai,
        "delta_pct": delta,
        "total_value": float(sum(a["value"] for a in assets)),
        "per_asset": [
            {"id": a["id"], "lat": a["lat"], "lon": a["lon"], "eai": eai[i], "country": iso3s[i]}
            for i, a in enumerate(assets)
        ],
        "freq_curve": {
            "return_periods": [float(x) for x in fc.return_per],
            "impact": [float(x) for x in fc.impact],
        },
        "detail": f"{src}; Emanuel v_half {v_halves}",
    }


def _run_river_flood(
    assets: list[dict[str, Any]],
    climate_scenario: str,
    anchor_years: list[int],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import numpy as np
    from climada.entity import ImpactFunc, ImpactFuncSet
    from climada.util.api_client import Client

    scenario = _RF_SCENARIO_MAP.get(climate_scenario, "rcp60")
    target = max(anchor_years) if anchor_years else 2050
    year_range = next(
        (r for r in _RF_YEAR_RANGES if int(r[:4]) <= target <= int(r[5:])), "2030_2050"
    )
    iso3s = _per_asset_iso3([a["lat"] for a in assets], [a["lon"] for a in assets])
    iso3 = _single_country_iso3(iso3s)

    # One depth-damage ImpactFunc per distinct curve; assign each asset to its id.
    curve_key = [tuple(round(float(x), 4) for x in a["flood_mdr"]) for a in assets]
    distinct = sorted(set(curve_key))
    id_by_curve = {c: i + 1 for i, c in enumerate(distinct)}
    funcs = []
    for curve, fid in id_by_curve.items():
        depths = np.array(assets[curve_key.index(curve)]["flood_depth_m"], dtype=float)
        funcs.append(
            ImpactFunc(
                haz_type="RF",
                id=fid,
                intensity=depths,
                mdd=np.array(curve, dtype=float),
                paa=np.ones_like(depths),
                intensity_unit="m",
                name=f"flood_class_{fid}",
            )
        )
    impf_set = ImpactFuncSet(funcs)
    impf_ids = [id_by_curve[c] for c in curve_key]
    exp = _build_exposures(assets, "impf_RF", impf_ids)

    client = Client()

    def fetch(scen: str, yr: str):  # type: ignore[no-untyped-def]
        props = {"climate_scenario": scen, "year_range": yr}
        if iso3 is not None:
            try:
                return client.get_hazard(
                    "river_flood",
                    properties={**props, "spatial_coverage": "country", "country_iso3alpha": iso3},
                )
            except Exception:
                pass
        return client.get_hazard("river_flood", properties={**props, "spatial_coverage": "global"})

    cat_haz = catalog.load_hazard("river_flood", climate_scenario, iso3 or "global", target)
    future = _impact(exp, impf_set, cat_haz or fetch(scenario, year_range))
    present = _impact(exp, impf_set, fetch("historical", "1980_2000"))
    src = "local catalog" if cat_haz is not None else f"{iso3 or 'global'} {scenario} {year_range}"

    eai = [float(x) for x in future.eai_exp]
    fc = future.calc_freq_curve(_RETURN_PERIODS)
    present_aai = float(present.aai_agg)
    future_aai = float(future.aai_agg)
    delta = ((future_aai - present_aai) / present_aai * 100.0) if present_aai > 0 else None

    return {
        "peril": "river_flood",
        "status": "ok",
        "target_year": int(year_range[5:]),
        "aai_agg": future_aai,
        "present_aai_agg": present_aai,
        "delta_pct": delta,
        "total_value": float(sum(a["value"] for a in assets)),
        "per_asset": [
            {"id": a["id"], "lat": a["lat"], "lon": a["lon"], "eai": eai[i], "country": iso3s[i]}
            for i, a in enumerate(assets)
        ],
        "freq_curve": {
            "return_periods": [float(x) for x in fc.return_per],
            "impact": [float(x) for x in fc.impact],
        },
        "detail": f"{src} RF set",
    }


def _run_wildfire(
    assets: list[dict[str, Any]],
    climate_scenario: str,
    anchor_years: list[int],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import numpy as np
    from climada.entity import ImpactFunc, ImpactFuncSet
    from climada.util.api_client import Client

    iso3s = _per_asset_iso3([a["lat"] for a in assets], [a["lon"] for a in assets])
    iso3 = _single_country_iso3(iso3s)
    if iso3 is None:
        raise ValueError("wildfire requires a single-country portfolio (global set too large)")

    cat_haz = catalog.load_hazard("wildfire", "historical", iso3, 2020)
    haz = cat_haz or Client().get_hazard(
        "wildfire", properties={"spatial_coverage": "country", "country_iso3alpha": iso3}
    )
    wf_src = "local catalog" if cat_haz is not None else "Data API"
    htype = haz.haz_type  # "WFseason"; intensity is brightness temperature (K)

    # One step damage function per distinct class max (wf_max_mdd); ramp above ~295 K.
    intens = np.array([0.0, 294.0, 295.0, 320.0, 360.0, 500.0])
    shape = np.array([0.0, 0.0, 0.25, 0.5, 0.85, 1.0])  # fraction of the class maximum
    maxes = sorted({round(float(a["wf_max_mdd"]), 3) for a in assets})
    id_by = {m: i + 1 for i, m in enumerate(maxes)}
    impf_set = ImpactFuncSet(
        [
            ImpactFunc(
                haz_type=htype,
                id=fid,
                intensity=intens,
                mdd=shape * m,
                paa=np.ones_like(intens),
                intensity_unit="K",
                name=f"wildfire_{fid}",
            )
            for m, fid in id_by.items()
        ]
    )
    impf_ids = [id_by[round(float(a["wf_max_mdd"]), 3)] for a in assets]
    exp = _build_exposures(assets, f"impf_{htype}", impf_ids)
    imp = _impact(exp, impf_set, haz)
    eai = [float(x) for x in imp.eai_exp]
    fc = imp.calc_freq_curve(_RETURN_PERIODS)
    return {
        "peril": "wildfire",
        "status": "ok",
        "target_year": 2020,
        "aai_agg": float(imp.aai_agg),
        "present_aai_agg": None,  # historical-only: no future wildfire set in CLIMADA
        "delta_pct": None,
        "total_value": float(sum(a["value"] for a in assets)),
        "per_asset": [
            {"id": a["id"], "lat": a["lat"], "lon": a["lon"], "eai": eai[i], "country": iso3s[i]}
            for i, a in enumerate(assets)
        ],
        "freq_curve": {
            "return_periods": [float(x) for x in fc.return_per],
            "impact": [float(x) for x in fc.impact],
        },
        "detail": f"{iso3} wildfire ({wf_src}; historical 2001–2020, no future set)",
    }


def _run_european_windstorm(
    assets: list[dict[str, Any]],
    climate_scenario: str,
    anchor_years: list[int],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from climada.entity import ImpactFuncSet
    from climada.entity.impact_funcs.storm_europe import ImpfStormEurope
    from climada.util.api_client import Client

    ssp = {"rcp26": "ssp126", "rcp45": "ssp245", "rcp60": "ssp370", "rcp85": "ssp585"}.get(
        climate_scenario, "ssp585"
    )
    iso3s = _per_asset_iso3([a["lat"] for a in assets], [a["lon"] for a in assets])

    client = Client()
    # CMIP6 future windstorm hazard is published with Europe-wide coverage (not per-country);
    # it covers any European asset. Pick one GCM dataset and fetch by its exact properties.
    base = {"data_source": "CMIP6", "spatial_coverage": "Europe"}
    fut_infos = client.list_dataset_infos(
        data_type="storm_europe", properties={**base, "climate_scenario": ssp}
    )
    if not fut_infos:
        raise ValueError(f"no storm_europe CMIP6 Europe dataset under {ssp}")
    fut = fut_infos[0]
    gcm = fut.properties.get("gcm")

    impf_set = ImpactFuncSet([ImpfStormEurope.from_schwierz()])  # haz_type WS, id 1 (calibrated)
    exp = _build_exposures(assets, "impf_WS", [1] * len(assets))
    future = _impact(exp, impf_set, client.get_hazard("storm_europe", properties=fut.properties))

    present_aai: float | None = None
    pre_infos = client.list_dataset_infos(
        data_type="storm_europe", properties={**base, "climate_scenario": "None"}
    )
    if pre_infos:
        try:
            present = client.get_hazard("storm_europe", properties=pre_infos[0].properties)
            present_aai = float(_impact(exp, impf_set, present).aai_agg)
        except Exception:
            present_aai = None

    eai = [float(x) for x in future.eai_exp]
    fc = future.calc_freq_curve(_RETURN_PERIODS)
    future_aai = float(future.aai_agg)
    delta = (
        ((future_aai - present_aai) / present_aai * 100.0)
        if present_aai and present_aai > 0
        else None
    )
    return {
        "peril": "european_windstorm",
        "status": "ok",
        "target_year": None,
        "aai_agg": future_aai,
        "present_aai_agg": present_aai,
        "delta_pct": delta,
        "total_value": float(sum(a["value"] for a in assets)),
        "per_asset": [
            {"id": a["id"], "lat": a["lat"], "lon": a["lon"], "eai": eai[i], "country": iso3s[i]}
            for i, a in enumerate(assets)
        ],
        "freq_curve": {
            "return_periods": [float(x) for x in fc.return_per],
            "impact": [float(x) for x in fc.impact],
        },
        "detail": f"Europe storm_europe CMIP6 {gcm} {ssp} (Schwierz impf; SSP future vs present)",
    }


def _run_earthquake(
    assets: list[dict[str, Any]],
    climate_scenario: str,
    anchor_years: list[int],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Earthquake (geophysical — observed catalogue, no climate scenario; MMI intensity)."""
    import numpy as np
    from climada.entity import ImpactFunc, ImpactFuncSet
    from climada.util.api_client import Client

    iso3s = _per_asset_iso3([a["lat"] for a in assets], [a["lon"] for a in assets])
    iso3 = _single_country_iso3(iso3s)
    if iso3 is None:
        raise ValueError("earthquake requires a single-country portfolio (global set too large)")

    cat_haz = catalog.load_hazard("earthquake", "observed", iso3, 2020)
    eq_props = {"spatial_coverage": "country", "country_iso3alpha": iso3, "event_type": "observed"}
    haz = cat_haz or Client().get_hazard("earthquake", properties=eq_props)
    htype = haz.haz_type  # "EQ"; intensity is Modified Mercalli Intensity (MMI)
    # Indicative MMI damage function (rises from ~MMI 5 to total by ~MMI 10).
    impf = ImpactFunc(
        haz_type=htype,
        id=1,
        intensity=np.array([0, 5, 6, 7, 8, 9, 10, 12], dtype=float),
        mdd=np.array([0, 0, 0.02, 0.08, 0.25, 0.5, 0.8, 1.0], dtype=float),
        paa=np.ones(8),
        intensity_unit="MMI",
        name="earthquake_mmi",
    )
    exp = _build_exposures(assets, f"impf_{htype}", [1] * len(assets))
    imp = _impact(exp, ImpactFuncSet([impf]), haz)
    eai = [float(x) for x in imp.eai_exp]
    fc = imp.calc_freq_curve(_RETURN_PERIODS)
    return {
        "peril": "earthquake",
        "status": "ok",
        "target_year": None,
        "aai_agg": float(imp.aai_agg),
        "present_aai_agg": None,
        "delta_pct": None,
        "total_value": float(sum(a["value"] for a in assets)),
        "per_asset": [
            {"id": a["id"], "lat": a["lat"], "lon": a["lon"], "eai": eai[i], "country": iso3s[i]}
            for i, a in enumerate(assets)
        ],
        "freq_curve": {
            "return_periods": [float(x) for x in fc.return_per],
            "impact": [float(x) for x in fc.impact],
        },
        "detail": f"{iso3} earthquake (observed catalogue; geophysical, no climate scenario)",
    }


def _run_coastal_flood(
    assets: list[dict[str, Any]],
    climate_scenario: str,
    anchor_years: list[int],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Coastal flood / sea-level rise — depth-damage on a locally-ingested Aqueduct hazard.

    Coastal flood is not in the CLIMADA Data API, so this runner is catalog-only: ingest
    WRI Aqueduct coastal layers first (``source='aqueduct'``, ``peril='coastal_flood'``).
    Uses the same depth-damage curve fields as river flood (intensity = inundation m).
    """
    import numpy as np
    from climada.entity import ImpactFunc, ImpactFuncSet

    target = max(anchor_years) if anchor_years else 2050
    iso3s = _per_asset_iso3([a["lat"] for a in assets], [a["lon"] for a in assets])
    iso3 = _single_country_iso3(iso3s)
    region = iso3 or "global"

    future = catalog.load_hazard("coastal_flood", climate_scenario, region, target)
    if future is None:
        raise ValueError(
            "coastal flood has no local hazard for this portfolio — ingest WRI Aqueduct "
            "coastal layers first (Data tab → Fetch & ingest, source 'aqueduct')."
        )

    # One depth-damage ImpactFunc per distinct curve; assign each asset to its id.
    curve_key = [tuple(round(float(x), 4) for x in a["flood_mdr"]) for a in assets]
    distinct = sorted(set(curve_key))
    id_by_curve = {c: i + 1 for i, c in enumerate(distinct)}
    funcs = []
    for curve, fid in id_by_curve.items():
        depths = np.array(assets[curve_key.index(curve)]["flood_depth_m"], dtype=float)
        funcs.append(
            ImpactFunc(
                haz_type="CF",
                id=fid,
                intensity=depths,
                mdd=np.array(curve, dtype=float),
                paa=np.ones_like(depths),
                intensity_unit="m",
                name=f"coastal_flood_{fid}",
            )
        )
    impf_set = ImpactFuncSet(funcs)
    impf_ids = [id_by_curve[c] for c in curve_key]
    exp = _build_exposures(assets, "impf_CF", impf_ids)

    fut = _impact(exp, impf_set, future)
    present = catalog.load_hazard("coastal_flood", "historical", region, None)
    present_aai = float(_impact(exp, impf_set, present).aai_agg) if present is not None else None

    eai = [float(x) for x in fut.eai_exp]
    fc = fut.calc_freq_curve(_RETURN_PERIODS)
    future_aai = float(fut.aai_agg)
    delta = (
        ((future_aai - present_aai) / present_aai * 100.0)
        if present_aai and present_aai > 0
        else None
    )
    return {
        "peril": "coastal_flood",
        "status": "ok",
        "target_year": target,
        "aai_agg": future_aai,
        "present_aai_agg": present_aai,
        "delta_pct": delta,
        "total_value": float(sum(a["value"] for a in assets)),
        "per_asset": [
            {"id": a["id"], "lat": a["lat"], "lon": a["lon"], "eai": eai[i], "country": iso3s[i]}
            for i, a in enumerate(assets)
        ],
        "freq_curve": {
            "return_periods": [float(x) for x in fc.return_per],
            "impact": [float(x) for x in fc.impact],
        },
        "detail": f"local catalog coastal flood (WRI Aqueduct), region {region}",
    }


_RUNNERS = {
    "tropical_cyclone": _run_tropical_cyclone,
    "river_flood": _run_river_flood,
    "wildfire": _run_wildfire,
    "european_windstorm": _run_european_windstorm,
    "earthquake": _run_earthquake,
    "coastal_flood": _run_coastal_flood,
}


def compute_physical_risk(request: dict[str, Any]) -> dict[str, Any]:
    """Run the physical-risk engine for each requested peril.

    Returns a PhysicalRunOutput as a plain dict (one result per peril).
    """
    perils: list[str] = request["perils"]
    scenario: str = request["climate_scenario"]
    anchor_years: list[int] = request["anchor_years"]
    assets: list[dict[str, Any]] = request["assets"]
    options: dict[str, Any] = request.get("options", {})

    results: list[dict[str, Any]] = []
    for peril in perils:
        runner = _RUNNERS.get(peril)
        if runner is None:
            results.append(
                {
                    "peril": peril,
                    "status": "engine_not_ready",
                    "detail": f"peril '{peril}' is not yet implemented (Phase 2+).",
                }
            )
            continue
        try:
            results.append(runner(assets, scenario, anchor_years, options))
        except Exception as exc:
            results.append(
                {"peril": peril, "status": "error", "detail": f"{type(exc).__name__}: {exc}"}
            )

    ok = [r for r in results if r["status"] == "ok"]
    if ok and len(ok) == len(results):
        overall = "ok"
    elif ok:
        overall = "partial"
    elif any(r["status"] == "error" for r in results):
        overall = "error"
    else:
        overall = "engine_not_ready"

    return {"status": overall, "climate_scenario": scenario, "results": results, "detail": None}
