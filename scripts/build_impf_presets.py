"""Regenerate ``assets/libraries/impact_function_presets.json`` from CLIMADA.

These are *authentic* published impact-function presets the Vulnerability studio
offers as one-click starting points:

  - Tropical cyclone: regionally-calibrated Emanuel ``v_half`` (Eberenz et al. 2021),
    median quantile, ``v_thresh = 25.7 m/s``. Mapped onto the studio's ``tc_v_half``.
  - River flood: JRC continental depth-damage curves (Huizinga et al. 2017),
    residential sector, sampled at the studio's flood-depth breakpoints. Mapped
    onto the studio's ``flood_mdr``.

The values are baked into the committed JSON so the backend (which never imports
CLIMADA — GPL boundary) and the frontend can read them offline. Re-run in the
worker env to refresh:

    ./.climada-env/bin/python scripts/build_impf_presets.py

Run from the repo root.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

# Depth breakpoints must match assets/libraries/impact_functions.json "flood_depth_m".
FLOOD_DEPTHS_M = [0.0, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
TC_V_THRESH_MS = 25.7  # Emanuel (2011) threshold used by the calibrated regional set.

# Eberenz et al. (2021) region codes → human labels.
TC_REGION_LABELS = {
    "NA1": "Caribbean & Mexico",
    "NA2": "USA & Canada",
    "NI": "North Indian",
    "OC": "Oceania (AU/NZ/Pacific)",
    "SI": "South Indian",
    "WP1": "South East Asia",
    "WP2": "Philippines",
    "WP3": "China mainland",
    "WP4": "North West Pacific",
    "ROW": "Rest of the world",
}

# JRC continental curves (Huizinga et al. 2017), residential sector.
FLOOD_REGIONS = {
    "Africa": "Africa",
    "Asia": "Asia",
    "Europe": "Europe",
    "NorthAmerica": "North America",
    "Oceania": "Oceania",
    "SouthAmerica": "South America",
}


def _tc_presets() -> list[dict[str, Any]]:
    from climada.entity.impact_funcs.trop_cyclone import ImpfSetTropCyclone

    v_half = ImpfSetTropCyclone.calibrated_regional_vhalf(q=0.5)
    prov = f"Eberenz et al. (2021) regional calibration, v_thresh={TC_V_THRESH_MS} m/s"
    presets = [
        {
            "id": "tc_eberenz_emanuel_usa",
            "peril": "tc",
            "label": "TC — Emanuel default (USA)",
            "tc_v_half": 74.7,
            "provenance": "Emanuel (2011), ImpfTropCyclone.from_emanuel_usa default v_half",
        }
    ]
    for code, label in TC_REGION_LABELS.items():
        if code not in v_half:
            continue
        presets.append(
            {
                "id": f"tc_eberenz_{code.lower()}",
                "peril": "tc",
                "label": f"TC — {label} ({code})",
                "tc_v_half": round(float(v_half[code]), 1),
                "provenance": prov,
            }
        )
    return presets


def _flood_presets() -> list[dict[str, Any]]:
    from climada_petals.entity.impact_funcs.river_flood import ImpfRiverFlood

    presets = []
    for code, label in FLOOD_REGIONS.items():
        f = ImpfRiverFlood.from_jrc_region_sector(code, "residential")
        mdr = [round(float(np.interp(d, f.intensity, f.mdd * f.paa)), 3) for d in FLOOD_DEPTHS_M]
        presets.append(
            {
                "id": f"flood_jrc_{code.lower()}",
                "peril": "flood",
                "label": f"Flood — {label} (JRC residential)",
                "flood_mdr": mdr,
                "provenance": "Huizinga et al. (2017) JRC global depth-damage, residential",
            }
        )
    return presets


def build() -> dict[str, Any]:
    """Build the presets payload (TC + flood)."""
    return {
        "_meta": {
            "description": (
                "Authentic published impact-function presets the Vulnerability studio applies "
                "with one click. TC presets set tc_v_half (Emanuel form, v_thresh=25.7 m/s); "
                "flood presets set flood_mdr at the standard depth breakpoints."
            ),
            "flood_depth_m": FLOOD_DEPTHS_M,
            "generator": "scripts/build_impf_presets.py (run in the CLIMADA worker env)",
        },
        "presets": _tc_presets() + _flood_presets(),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = root / "assets" / "libraries" / "impact_function_presets.json"
    payload = build()
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(payload['presets'])} presets → {out}")


if __name__ == "__main__":
    main()
