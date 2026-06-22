# CLIMADA coverage roadmap

Goal: expose CLIMADA's user-facing analytical capabilities through the platform. "100%"
means the decision-relevant surface (engine, exposures, vulnerability, hazards, adaptation,
uncertainty, calibration, forecasting, Data API) — not every internal util/plot variant.

Executed in capability batches; each batch = worker function + JSON contract field + backend
route + UI panel + verification. Status legend: [x] done · [~] in progress · [ ] planned.

## A. Engine — impact (baseline)
- [x] `ImpactCalc` → AAI, `eai_exp`, return-period curve, present↔future delta
- [ ] Impact matrix / per-event impacts surfaced
- [ ] Exceedance curve with confidence; eai/aai map plotting layers

## B. Adaptation — cost-benefit  (DONE)
- [x] Measure / MeasureSet (hazard freq cutoff, MDD/PAA modifiers, risk transfer attach/cover)
- [x] CostBenefit.calc → averted damage (benefit), cost/benefit ratio, NPV, discount rates
- [x] Adapt view: measure editor + per-measure benefit/cost results (TC; extends to other perils)

## C. Uncertainty & sensitivity  (DONE — Monte-Carlo variant)
- [x] Monte-Carlo over exposure value / vulnerability / hazard frequency → AAI distribution
- [x] AAI mean/std/P5/P50/P95 + histogram; first-order sensitivity (|corr|) in Results
- [ ] `unsequa` Sobol decomposition + `CalcDeltaImpact`/`CalcCostBenefit` uncertainty (deeper)

## D. Exposures
- [x] User point assets (lat/lon, value, sector, impf, vulnerability class)
- [~] LitPop automated exposure — **engine + route + UI built** (Map → "Modeled exposure"),
      but the GPW population GeoTIFF needs a free NASA Earthdata download (can't auto-fetch);
      the run returns a clear "download GPW" message until provisioned, then works.
- [ ] Polygon / area exposure; gridded/raster import; OSM exposure
- [ ] Value units, region_id/category_id, deductible/cover columns

## E. Vulnerability / impact functions  (studio DONE)
- [x] Preset per-class curves (Emanuel, Schwierz, Huizinga, wildfire step)
- [x] Impact-function studio (Vuln tab): edit TC v½ / wildfire MDR / flood depth-damage;
      stored as session overrides, flow into every run
- [x] Insurance: risk-transfer attach/cover (in the Adapt cost-benefit measures)
- [ ] Calibration from observed losses (needs an observed-loss dataset)

## F. Hazards
- [x] tropical_cyclone, river_flood, wildfire, storm_europe, **earthquake** (+ local catalog)
- [ ] hail (Europe-only radar MESHS/POH, finicky dataset selection — documented, deferred)
- [ ] petals: tc_surge (coastal), drought, low_flow, landslide
- [ ] Climate-scenario scaling controls (`apply_climate_scenario_knu`), GCM ensembles
- [ ] Event-level inspection; hazard map/footprint plots

## G. Perils database (custom hazard ingestion)
- [x] Standardized-grid → CLIMADA HDF5 converter; catalog; resolver; build CLI; `/api/hazard-catalog`
- [ ] UI catalog browser + ingestion wizard
- [ ] Data-API browser/download into the catalog from the UI

## H. Forecast
- [ ] `climada.engine.Forecast` — **needs an operational forecast feed** (e.g. a live TC-track
      or NWP weather forecast hazard). Without a real feed there is nothing honest to compute, so
      this is intentionally not implemented (no faked forecast). Wire when a feed is available.

## I. Reporting / exports  (DONE)
- [x] TCFD/ISSB HTML report (physical + transition)
- [x] Report extended with cost-benefit + uncertainty sections (cb/unc run ids in the link)

## Status summary
DONE & verified: A impact · B cost-benefit · C uncertainty · E impact-function studio ·
F earthquake (+TC/RF/wildfire/windstorm) · G perils-database · I reporting.
PARTIAL/blocked-by-data: D LitPop (needs GPW download) · F hail/petals/coastal/heat/drought
(no usable Data-API future asset-damage set) · H Forecast (needs operational feed) · calibration
(needs observed losses). These are honest data/feed limits, not skipped work.

Build order: **B → C → D(LitPop) → E(studio) → F(more hazards) → H → polish.**
