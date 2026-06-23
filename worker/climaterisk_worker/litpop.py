"""Modeled-exposure run (CLIMADA ``LitPop`` and other builders) — batch D.

Builds a gridded asset-value exposure for a country (LitPop population × nightlights
by default, or another source from :mod:`climaterisk_worker.exposures`), then runs TC
impact on it. The underlying data is login-gated/large, so missing data degrades with
a clear, actionable message rather than failing opaquely.
"""

from __future__ import annotations

from typing import Any


def compute_litpop_exposure(request: dict[str, Any]) -> dict[str, Any]:
    """Build a modeled country exposure and compute TC impact on it.

    The exposure source defaults to LitPop but can be any builder in
    :mod:`climaterisk_worker.exposures` (BlackMarble, GDP2Asset, …); gated/large
    sources degrade with an actionable message rather than failing opaquely.
    """
    import numpy as np

    from climaterisk_worker.cost_benefit import _tc_hazard
    from climaterisk_worker.exposures import EXPOSURE_SOURCES, ExposureUnavailable, build_exposure
    from climaterisk_worker.physical import _TC_REF_YEARS, _nearest

    country = request.get("country")
    if not country:
        return {"status": "error", "detail": "no country (ISO3) specified for modeled exposure"}
    source = str(request.get("exposure_source", "litpop"))
    source_label = EXPOSURE_SOURCES.get(source, {}).get("label", source)
    scenario = request["climate_scenario"]
    anchor = request["anchor_years"]
    ref_year = _nearest(_TC_REF_YEARS, max(anchor) if anchor else _TC_REF_YEARS[0])

    try:
        exp = build_exposure(source, country, res_arcsec=300)
    except ExposureUnavailable as exc:
        return {"status": "error", "source": source, "detail": exc.detail}

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
        "exposure_source": source,
        "source_label": source_label,
        "peril": "tropical_cyclone",
        "future_year": ref_year,
        "total_value": float(gdf["value"].sum()),
        "aai_agg": float(imp.aai_agg),
        "n_points": len(eai),
        "per_point": per_point,
        "currency": exp.value_unit or "USD",
        "detail": f"{source_label} {country}: {len(eai)} cells, TC horizon {ref_year}",
    }
