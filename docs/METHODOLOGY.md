# Methodology & data provenance

This platform orchestrates established open-source methods rather than inventing climate science.
Every bundled dataset must be recorded here with its **source** and **license** before it is used
in a published result.

## Physical risk — CLIMADA

- **Engine:** [CLIMADA](https://climada-python.readthedocs.io) (ETH Zürich), **GPL-3.0**. Risk =
  Hazard × Exposure × Vulnerability; probabilistic, event-based. Run in a separate conda worker.
- **Outputs used:** `aai_agg` (average annual impact), `eai_exp` (per-asset, → map layer),
  `calc_freq_curve()` (return-period curve).

### Future estimation (important)

CLIMADA has **no embedded climate model**. Future hazard is obtained per peril and frozen into the
bundled library:

| Peril | Future-hazard source |
|---|---|
| Tropical cyclone | CLIMADA Data API future sets (rcp26/45/60/85 × 2040/2060/2080); or `apply_climate_scenario_knu` (**frequency-only** scaling, Knutson 2020 / Jewson 2021) |
| River flood | ISIMIP future flood depth/fraction |
| Coastal flood / SLR | WRI Aqueduct coastal-flood future sets (rcp × ref_year) |
| Heat / drought / wildfire | Onboarded climate projections (CORDEX/CMIP-derived) |

Time: per-scenario **anchor years** with linear interpolation + present-day baseline blend.
Present→future deltas + uncertainty via CLIMADA `unsequa.CalcDeltaImpact`. The `PhysicalEngine`
interface allows adding **physrisk** (Apache-2.0, native `(scenario, year)` hazards) later.

## Transition risk (Phase 3)

- **Scenarios:** NGFS Phase 5 (Nov 2024) — frozen carbon-price + emissions snapshot, extracted via
  `pyam` to IAMC CSV. CC-BY with attribution; redistribution of substantial raw portions restricted.
- **Emission factors:** EDGAR 2024 (CC BY 4.0) — Scope-1 proxy when an asset reports no emissions.
- **Core calc:** carbon-cost passthrough `cost(t) = emissions × carbon_price(t, scenario)`,
  sector-adjusted; rolled up to EBITDA/value impact.
- **Benchmarks (later):** SBTi/PACTA sector pathways; CRREM real-estate stranding pathways.

## Perils database (local hazard catalog)

Beyond the live CLIMADA Data API, the platform can ingest **real source data** into a
local CLIMADA-ready hazard catalog (`data/hazard_db/`). A source is reduced to a
*standardized observation grid* (cells × years × intensity) and converted to a CLIMADA
`Hazard` HDF5 via `scripts/build_hazard.py` — faithfully (per-cell exceedance frequency
equals the source's annual exceedance probability). The worker resolves catalog hazards
before the Data API, which is how coastal flood / heat / drought / custom local sources
are added. See `docs/ARCHITECTURE.md` → *Perils database*. Record each ingested source's
provenance + licence in the catalog entry's `source`/`license` fields.

## Known data caveats

- **IEA WEO** free dataset is **non-commercial** — do not bundle for commercial use without a license.
- **Asset-level production data** for full PACTA alignment is not freely available → design for
  user-supplied data.

## Current status

The bundled library values in `assets/libraries/*.json` are **PLACEHOLDER** illustrative values
(sector emission intensities, impact-function catalogue). They must be replaced with the cited
sources above before any result is presented as authoritative.
