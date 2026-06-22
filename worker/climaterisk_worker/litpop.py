"""LitPop modeled exposure (CLIMADA ``LitPop``) — batch D.

Builds a gridded asset-value exposure for a country from population × nightlights
(LitPop), then runs TC impact on it. This needs the GPW population dataset, which
CLIMADA cannot auto-download (free NASA Earthdata login required) — so when it is
missing we return a clear, actionable error rather than failing opaquely.
"""

from __future__ import annotations

from typing import Any

GPW_HELP = (
    "LitPop needs the GPW v4 population GeoTIFF, which requires a free NASA Earthdata "
    "login and cannot be auto-downloaded. Download "
    "gpw-v4-population-count-rev11_2020_30_sec_tif.zip from "
    "https://sedac.ciesin.columbia.edu/data/collection/gpw-v4 and unzip it under "
    "~/climada/data/, then re-run."
)


def compute_litpop_exposure(request: dict[str, Any]) -> dict[str, Any]:
    """Build a LitPop exposure for a country and compute TC impact on it."""
    import numpy as np

    from climaterisk_worker.cost_benefit import _tc_hazard
    from climaterisk_worker.physical import _TC_REF_YEARS, _nearest

    country = request.get("country")
    if not country:
        return {"status": "error", "detail": "no country (ISO3) specified for LitPop"}
    scenario = request["climate_scenario"]
    anchor = request["anchor_years"]
    ref_year = _nearest(_TC_REF_YEARS, max(anchor) if anchor else _TC_REF_YEARS[0])

    try:
        from climada.entity import LitPop

        exp = LitPop.from_countries(country, res_arcsec=300)
    except FileNotFoundError as exc:
        return {"status": "error", "detail": f"{GPW_HELP} ({str(exc)[:120]})"}

    from climada.engine import ImpactCalc
    from climada.entity import ImpactFuncSet
    from climada.entity.impact_funcs.trop_cyclone import ImpfTropCyclone

    exp.gdf["impf_TC"] = 1
    impf_set = ImpactFuncSet([ImpfTropCyclone.from_emanuel_usa(impf_id=1)])
    haz = _tc_hazard(country, scenario, ref_year)
    imp = ImpactCalc(exp, impf_set, haz).impact(assign_centroids=True)

    eai = np.asarray(imp.eai_exp, dtype=float)
    gdf = exp.gdf
    if "geometry" in gdf and hasattr(gdf["geometry"], "x"):
        lat = gdf["geometry"].y.to_numpy()
        lon = gdf["geometry"].x.to_numpy()
    else:
        lat = gdf["latitude"].to_numpy()
        lon = gdf["longitude"].to_numpy()

    # Top points by expected annual impact for a tractable map layer.
    n_top = min(250, len(eai))
    idx = np.argsort(eai)[::-1][:n_top]
    per_point = [
        {"lat": float(lat[i]), "lon": float(lon[i]), "eai": float(eai[i])}
        for i in idx
        if eai[i] > 0
    ]
    return {
        "status": "ok",
        "country": country,
        "peril": "tropical_cyclone",
        "future_year": ref_year,
        "total_value": float(gdf["value"].sum()),
        "aai_agg": float(imp.aai_agg),
        "n_points": len(eai),
        "per_point": per_point,
        "currency": exp.value_unit or "USD",
        "detail": f"LitPop {country}: {len(eai)} cells, TC horizon {ref_year}",
    }
