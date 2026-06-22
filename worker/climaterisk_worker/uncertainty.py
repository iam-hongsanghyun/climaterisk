"""Monte-Carlo uncertainty + sensitivity for physical risk (CLIMADA ``ImpactCalc``).

Propagates three input uncertainties through repeated impact calculations:
  - exposure value      (× U[0.8, 1.2])
  - vulnerability        (Emanuel ``v_half`` × U[0.9, 1.1])
  - hazard frequency     (× U[0.85, 1.15])

and reports the AAI distribution (mean/std/percentiles) plus a first-order
sensitivity (|Pearson correlation| of each sampled factor with AAI). This is the
tractable Monte-Carlo variant; CLIMADA's ``unsequa`` Sobol decomposition is the
deeper option (noted in the UI). TC-first.
"""

from __future__ import annotations

from typing import Any

from climaterisk_worker.cost_benefit import _tc_hazard  # reuse TC hazard resolver (catalog-first)
from climaterisk_worker.physical import (
    _TC_REF_YEARS,
    _nearest,
    _per_asset_iso3,
    _single_country_iso3,
)


def compute_uncertainty(request: dict[str, Any]) -> dict[str, Any]:
    """Run a Monte-Carlo AAI uncertainty + sensitivity analysis."""
    import numpy as np
    import pandas as pd
    from climada.engine import ImpactCalc
    from climada.entity import Exposures, ImpactFuncSet
    from climada.entity.impact_funcs.trop_cyclone import ImpfTropCyclone

    assets: list[dict[str, Any]] = request["assets"]
    scenario: str = request["climate_scenario"]
    anchor_years: list[int] = request["anchor_years"]
    n_samples = int(request.get("n_samples", 50))
    if not assets:
        return {"status": "error", "detail": "portfolio has no assets"}

    ref_year = _nearest(_TC_REF_YEARS, max(anchor_years) if anchor_years else _TC_REF_YEARS[0])
    iso3 = _single_country_iso3(
        _per_asset_iso3([a["lat"] for a in assets], [a["lon"] for a in assets])
    )
    haz = _tc_hazard(iso3, scenario, ref_year)

    lats = [float(a["lat"]) for a in assets]
    lons = [float(a["lon"]) for a in assets]
    base_values = np.array([float(a["value"]) for a in assets])
    base_vhalf = np.array([float(a["tc_v_half"]) for a in assets])

    rng = np.random.default_rng(42)
    aais, f_val, f_vul, f_freq = [], [], [], []
    for _ in range(n_samples):
        fv = float(rng.uniform(0.8, 1.2))  # exposure value
        fh = float(rng.uniform(0.9, 1.1))  # vulnerability (v_half scale)
        ff = float(rng.uniform(0.85, 1.15))  # hazard frequency

        scaled_vhalf = base_vhalf * fh
        uniq = sorted({round(v, 1) for v in scaled_vhalf})
        id_by = {v: i + 1 for i, v in enumerate(uniq)}
        impf_set = ImpactFuncSet(
            [ImpfTropCyclone.from_emanuel_usa(impf_id=i + 1, v_half=v) for i, v in enumerate(uniq)]
        )
        exp = Exposures(
            pd.DataFrame(
                {
                    "latitude": lats,
                    "longitude": lons,
                    "value": base_values * fv,
                    "impf_TC": [id_by[round(v, 1)] for v in scaled_vhalf],
                }
            )
        )
        imp = ImpactCalc(exp, impf_set, haz).impact(assign_centroids=True)
        aais.append(float(imp.aai_agg) * ff)  # frequency scales AAI linearly
        f_val.append(fv)
        f_vul.append(fh)
        f_freq.append(ff)

    aai = np.array(aais)

    def sens(factor: list[float]) -> float:
        c = np.corrcoef(factor, aai)[0, 1]
        return float(abs(c)) if np.isfinite(c) else 0.0

    return {
        "status": "ok",
        "peril": "tropical_cyclone",
        "future_year": ref_year,
        "n_samples": n_samples,
        "currency": assets[0]["currency"],
        "aai_mean": float(aai.mean()),
        "aai_std": float(aai.std()),
        "aai_p5": float(np.percentile(aai, 5)),
        "aai_p50": float(np.percentile(aai, 50)),
        "aai_p95": float(np.percentile(aai, 95)),
        "distribution": [float(x) for x in np.sort(aai)],
        "sensitivity": {
            "exposure_value": sens(f_val),
            "vulnerability": sens(f_vul),
            "hazard_frequency": sens(f_freq),
        },
        "detail": f"{iso3 or 'global'} TC; {n_samples} Monte-Carlo samples, horizon {ref_year}",
    }
