import { useEffect, useState } from "react";
import {
  CircleMarker,
  ImageOverlay,
  MapContainer,
  Polygon,
  Polyline,
  TileLayer,
  Tooltip,
  useMapEvents,
} from "react-leaflet";
import type {
  Asset,
  HazardCatalog,
  HazardCatalogEntry,
  HazardPreviewResult,
  Libraries,
  LitPopResult,
  Portfolio,
  Run,
} from "../types";
import { AssetEditor } from "../components/AssetEditor";
import { getHazardCatalog, getRun, hazardPreviewImageUrl, submitHazardPreview } from "../lib/api";
import { money } from "../lib/format";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Turbo colormap stops (match the worker's hazard raster + the legend gradient).
const TURBO_CSS = "linear-gradient(90deg,#30123b,#28829b,#a2fc3c,#fb8023,#7a0403)";
const TURBO_STOPS = [
  [48, 18, 59],
  [40, 130, 155],
  [162, 252, 60],
  [251, 128, 35],
  [122, 4, 3],
];
/** Turbo color at fraction f∈[0,1] — used to color exposure markers by value. */
function turboAt(f: number): string {
  const x = Math.max(0, Math.min(1, f)) * (TURBO_STOPS.length - 1);
  const i = Math.floor(x);
  const t = x - i;
  const a = TURBO_STOPS[i];
  const b = TURBO_STOPS[Math.min(i + 1, TURBO_STOPS.length - 1)];
  const c = a.map((v, k) => Math.round(v + (b[k] - v) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

const EXPOSURE_LAYER = "__exposure__";

/** GeoJSON Polygon/LineString → leaflet [lat,lon][] positions (null for points/other). */
function geomPositions(geom: unknown): { kind: "polygon" | "line"; pos: [number, number][] } | null {
  const g = geom as { type?: string; coordinates?: unknown } | null;
  if (!g?.type) return null;
  if (g.type === "Polygon")
    return { kind: "polygon", pos: (g.coordinates as number[][][])[0].map(([lo, la]) => [la, lo]) };
  if (g.type === "LineString")
    return { kind: "line", pos: (g.coordinates as number[][]).map(([lo, la]) => [la, lo]) };
  return null;
}

function newAsset(lat: number, lon: number): Asset {
  return {
    id: crypto.randomUUID(),
    name: "New facility",
    lat: Number(lat.toFixed(5)),
    lon: Number(lon.toFixed(5)),
    sector: "real_estate",
    geographic_scale: "point",
    value: 0,
    currency: "USD",
    annual_emissions_tco2e: null,
    vulnerability_class: null, // follow sector default
    properties: {},
  };
}

function ClickToAdd({ onAdd }: { onAdd: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) {
      onAdd(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

export function MapView({
  model,
  libraries,
  patchModel,
  litpopRun,
  litpopBusy,
  litpopErr,
  onRunLitpop,
}: {
  model: Portfolio;
  libraries: Libraries;
  patchModel: (patch: Partial<Portfolio>) => void;
  litpopRun: Run | null;
  litpopBusy: boolean;
  litpopErr: string | null;
  onRunLitpop: (country: string, source: string, peril: string) => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawMode, setDrawMode] = useState<"point" | "polygon" | "line">("point");
  const [draft, setDraft] = useState<[number, number][]>([]); // [lat, lon] vertices in progress
  const [litpopCountry, setLitpopCountry] = useState("JPN");
  const [litpopSource, setLitpopSource] = useState("litpop");
  const [litpopPeril, setLitpopPeril] = useState("tropical_cyclone");

  // Hazard-layer preview (raster overlay of the raw hazard intensity, pre-calculation).
  const [catalog, setCatalog] = useState<HazardCatalog | null>(null);
  const [layerKey, setLayerKey] = useState("");
  const [layer, setLayer] = useState<{ data: HazardPreviewResult; url: string } | null>(null);
  const [layerBusy, setLayerBusy] = useState(false);
  const [layerErr, setLayerErr] = useState<string | null>(null);
  const [opacity, setOpacity] = useState(0.75);
  useEffect(() => {
    getHazardCatalog()
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, []);

  const entryKey = (e: HazardCatalogEntry) =>
    `${e.peril}|${e.climate_scenario}|${e.region}|${e.year ?? ""}`;

  async function showLayer(key: string) {
    setLayerKey(key);
    setLayer(null);
    setLayerErr(null);
    if (!key || key === EXPOSURE_LAYER) return; // exposure layer is client-side (asset values)
    const e = catalog?.entries.find((x) => entryKey(x) === key);
    if (!e) return;
    setLayerBusy(true);
    try {
      let r = await submitHazardPreview(model.id, e.peril, e.climate_scenario, e.region, e.year);
      for (let i = 0; i < 120 && (r.status === "queued" || r.status === "running"); i++) {
        await sleep(1500);
        r = await getRun(model.id, r.id);
      }
      const out = r.output as HazardPreviewResult | null;
      if (r.status === "done" && out?.status === "ok") {
        setLayer({ data: out, url: hazardPreviewImageUrl(model.id, r.id) });
      } else {
        setLayerErr(out?.detail ?? r.detail ?? "Preview failed.");
      }
    } catch (err) {
      setLayerErr(String(err));
    } finally {
      setLayerBusy(false);
    }
  }
  const selected = model.assets.find((a) => a.id === selectedId) ?? null;
  const litpop = litpopRun?.status === "done" ? (litpopRun.output as LitPopResult | null) : null;
  const litpopRunning = litpopRun?.status === "queued" || litpopRun?.status === "running";

  // Exposure-value layer: color asset markers by value (client-side; no run needed).
  const exposureLayer = layerKey === EXPOSURE_LAYER;
  const vals = model.assets.map((a) => a.value).filter((v) => v > 0);
  const vMin = vals.length ? Math.min(...vals) : 0;
  const vMax = vals.length ? Math.max(...vals) : 0;
  const valueFrac = (v: number) => (vMax > vMin ? (v - vMin) / (vMax - vMin) : 0.5);

  const addAsset = (
    lat: number,
    lon: number,
    geometry?: Record<string, unknown>,
    scale: Asset["geographic_scale"] = "point",
  ) => {
    const asset = { ...newAsset(lat, lon), geographic_scale: scale, geometry: geometry ?? null };
    patchModel({ assets: [...model.assets, asset] });
    setSelectedId(asset.id);
  };

  // Draw directly on the map: in polygon/line mode, clicks accumulate vertices; Finish
  // builds the geometry asset. (Point mode = the original click-to-place.)
  const onMapClick = (lat: number, lon: number) => {
    if (drawMode === "point") addAsset(lat, lon);
    else setDraft((d) => [...d, [Number(lat.toFixed(5)), Number(lon.toFixed(5))]]);
  };
  const cancelDraw = () => setDraft([]);
  const finishDraw = () => {
    const need = drawMode === "polygon" ? 3 : 2;
    if (draft.length < need) return;
    const ll = draft.map(([la, lo]) => [lo, la]); // GeoJSON is [lon, lat]
    const geometry =
      drawMode === "polygon"
        ? { type: "Polygon", coordinates: [[...ll, ll[0]]] }
        : { type: "LineString", coordinates: ll };
    const cLat = draft.reduce((s, [la]) => s + la, 0) / draft.length;
    const cLon = draft.reduce((s, [, lo]) => s + lo, 0) / draft.length;
    addAsset(cLat, cLon, geometry, "footprint");
    setDraft([]);
    setDrawMode("point");
  };
  const updateAsset = (id: string, patch: Partial<Asset>) => {
    patchModel({ assets: model.assets.map((a) => (a.id === id ? { ...a, ...patch } : a)) });
  };
  const deleteAsset = (id: string) => {
    patchModel({ assets: model.assets.filter((a) => a.id !== id) });
    if (selectedId === id) setSelectedId(null);
  };

  return (
    <div className="mapview">
      <div className="map">
        <MapContainer center={[25, 15]} zoom={2} scrollWheelZoom>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ClickToAdd onAdd={onMapClick} />
          {draft.length > 0 &&
            (drawMode === "polygon" ? (
              <Polygon positions={draft} pathOptions={{ color: "#3aa0ff", dashArray: "5" }} />
            ) : (
              <Polyline positions={draft} pathOptions={{ color: "#3aa0ff", dashArray: "5" }} />
            ))}
          {draft.map((v, i) => (
            <CircleMarker key={`draft-${i}`} center={v} radius={4} pathOptions={{ color: "#3aa0ff", fillColor: "#3aa0ff", fillOpacity: 1 }} />
          ))}
          {layer && (
            <ImageOverlay
              key={layer.url}
              url={layer.url}
              bounds={layer.data.bounds}
              opacity={opacity}
              zIndex={400}
            />
          )}
          {model.assets.map((a) => {
            const g = geomPositions(a.geometry);
            if (!g) return null;
            const opts = { color: "#2f9e8f", weight: 2, fillOpacity: 0.15 };
            return g.kind === "polygon" ? (
              <Polygon key={`g-${a.id}`} positions={g.pos} pathOptions={opts} />
            ) : (
              <Polyline key={`g-${a.id}`} positions={g.pos} pathOptions={{ ...opts, weight: 3 }} />
            );
          })}
          {model.assets.map((a) => (
            <CircleMarker
              key={a.id}
              center={[a.lat, a.lon]}
              radius={a.id === selectedId ? 11 : 8}
              pathOptions={{
                color:
                  a.id === selectedId
                    ? "#3aa0ff"
                    : exposureLayer && a.value > 0
                      ? turboAt(valueFrac(a.value))
                      : "#2f9e8f",
                fillColor:
                  a.id === selectedId
                    ? "#3aa0ff"
                    : exposureLayer && a.value > 0
                      ? turboAt(valueFrac(a.value))
                      : "#2f9e8f",
                fillOpacity: exposureLayer ? 0.85 : 0.7,
                weight: 2,
              }}
              eventHandlers={{ click: () => setSelectedId(a.id) }}
            >
              <Tooltip>
                {a.name} · {a.sector}
                {exposureLayer ? ` · ${money(a.value, a.currency)}` : ""}
              </Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      <aside className="sidepanel">
        {selected ? (
          <AssetEditor
            asset={selected}
            libraries={libraries}
            onChange={(patch) => updateAsset(selected.id, patch)}
            onDelete={() => deleteAsset(selected.id)}
            onClose={() => setSelectedId(null)}
          />
        ) : (
          <>
            <div style={{ marginBottom: 4 }}>
              <div className="section-title">Draw on map</div>
              <div className="form-row" style={{ marginTop: 6 }}>
                {(["point", "polygon", "line"] as const).map((m) => (
                  <button
                    key={m}
                    className={`btn ${drawMode === m ? "" : "secondary"}`}
                    style={{ padding: "5px 10px", textTransform: "capitalize" }}
                    onClick={() => {
                      setDraft([]);
                      setDrawMode(m);
                    }}
                  >
                    {m === "point" ? "📍 Point" : m === "polygon" ? "▢ Polygon" : "／ Line"}
                  </button>
                ))}
              </div>
              {drawMode === "point" ? (
                <p className="hint" style={{ marginTop: 6 }}>
                  Click anywhere on the map to place a facility.
                </p>
              ) : (
                <div className="control-group" style={{ marginTop: 6 }}>
                  <span className="hint" style={{ flexBasis: "100%" }}>
                    Click to add {drawMode} vertices ({draft.length} so far), then Finish — it
                    becomes a footprint asset (value split across it).
                  </span>
                  <button
                    className="btn"
                    onClick={finishDraw}
                    disabled={draft.length < (drawMode === "polygon" ? 3 : 2)}
                  >
                    Finish {drawMode}
                  </button>
                  <button className="btn secondary" onClick={cancelDraw} disabled={!draft.length}>
                    Cancel
                  </button>
                </div>
              )}
            </div>
            {((catalog?.entries.length ?? 0) > 0 || model.assets.length > 0) && (
              <div style={{ marginBottom: 4 }}>
                <div className="section-title">Map layer (preview)</div>
                <p className="hint">
                  Color the map by a raw value — before any run — so you can see what's there:
                  a peril's hazard footprint, or your exposure by value.
                </p>
                <div className="form-row" style={{ marginTop: 6 }}>
                  <select
                    className="field-inline"
                    value={layerKey}
                    onChange={(e) => showLayer(e.target.value)}
                    disabled={layerBusy}
                    style={{ flex: 1, minWidth: 0 }}
                  >
                    <option value="">No layer</option>
                    {model.assets.length > 0 && (
                      <option value={EXPOSURE_LAYER}>Exposure value (your assets)</option>
                    )}
                    {(catalog?.entries ?? []).map((e) => (
                      <option key={entryKey(e)} value={entryKey(e)}>
                        {e.peril.replace(/_/g, " ")} · {e.region} · {e.climate_scenario}
                        {e.year ? ` ${e.year}` : ""}
                      </option>
                    ))}
                  </select>
                  {layerBusy && <span className="spinner" />}
                </div>
                {layerErr && (
                  <div className="status-box error" style={{ marginTop: 6 }}>
                    {layerErr}
                  </div>
                )}
                {layer && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ height: 12, borderRadius: 3, background: TURBO_CSS }} />
                    <div
                      className="hint"
                      style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}
                    >
                      <span>{layer.data.vmin}</span>
                      <span>
                        {layer.data.peril.replace(/_/g, " ")} ({layer.data.unit})
                      </span>
                      <span>{layer.data.vmax}</span>
                    </div>
                    <label className="hint" style={{ display: "block", marginTop: 6 }}>
                      Overlay opacity
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.05}
                        value={opacity}
                        onChange={(e) => setOpacity(Number(e.target.value))}
                        style={{ width: "100%" }}
                      />
                    </label>
                  </div>
                )}
                {exposureLayer && vals.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ height: 12, borderRadius: 3, background: TURBO_CSS }} />
                    <div
                      className="hint"
                      style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}
                    >
                      <span>{money(vMin, model.assets[0]?.currency ?? "USD")}</span>
                      <span>asset value</span>
                      <span>{money(vMax, model.assets[0]?.currency ?? "USD")}</span>
                    </div>
                  </div>
                )}
              </div>
            )}
            <div className="section-title">Facilities</div>
            <p className="hint">
              Click anywhere on the map to place a facility. Select one to edit its sector,
              scale, value, and emissions.
            </p>
            {model.assets.length === 0 ? (
              <div className="empty-state" style={{ padding: "24px 12px" }}>
                <div className="empty-icon">📍</div>
                <div className="empty-title">No facilities yet</div>
                <div className="empty-hint">
                  Click anywhere on the map to place your first facility — or model a whole
                  country's exposure below.
                </div>
              </div>
            ) : (
              <div className="assetlist">
                {model.assets.map((a) => (
                  <div key={a.id} className="row" onClick={() => setSelectedId(a.id)}>
                    <div>
                      <div className="nm">{a.name}</div>
                      <div className="sub">
                        {a.sector} · {a.lat.toFixed(2)}, {a.lon.toFixed(2)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="section-divider">
              <div className="section-title">Modeled exposure</div>
              <p className="hint">
                Model a whole country's asset values instead of hand-entering assets, then run any
                peril on the grid. LitPop (population × nightlights) is built in; other sources are
                login-gated or large and report what to download if absent.
              </p>
              <div className="form-row" style={{ marginTop: 8 }}>
                <select
                  className="field-inline"
                  value={litpopSource}
                  onChange={(e) => setLitpopSource(e.target.value)}
                  title="Modeled-exposure data source"
                >
                  <option value="litpop">LitPop (nightlight × pop)</option>
                  <option value="blackmarble">BlackMarble (nightlights)</option>
                  <option value="gdp">GDP2Asset (gridded GDP)</option>
                  <option value="crop">Crop production (ISIMIP/SPAM)</option>
                  <option value="osm">OSM buildings (osm-flex)</option>
                  <option value="raster">Population raster (WorldPop/GHSL)</option>
                </select>
                <select
                  className="field-inline"
                  value={litpopPeril}
                  onChange={(e) => setLitpopPeril(e.target.value)}
                  title="Peril to run on the modeled grid"
                >
                  {libraries.perils.perils
                    .filter((p) => p.supported_mvp)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label}
                      </option>
                    ))}
                </select>
                <input
                  className="field-inline"
                  value={litpopCountry}
                  onChange={(e) => setLitpopCountry(e.target.value.toUpperCase())}
                  maxLength={3}
                  placeholder="ISO3"
                  style={{ width: 70 }}
                />
                <button
                  className="btn"
                  onClick={() => onRunLitpop(litpopCountry, litpopSource, litpopPeril)}
                  disabled={litpopBusy || litpopRunning || litpopCountry.length !== 3}
                  title={litpopCountry.length !== 3 ? "Enter a 3-letter ISO country code" : ""}
                >
                  {litpopRunning ? (
                    <>
                      <span className="spinner" /> Modeling…
                    </>
                  ) : (
                    "Model exposure"
                  )}
                </button>
              </div>
              {litpopErr && <div className="status-box error" style={{ marginTop: 8 }}>{litpopErr}</div>}
              {litpopRun?.status === "error" && (
                <div className="status-box error" style={{ marginTop: 8 }}>{litpopRun.detail}</div>
              )}
              {litpop && litpop.status === "error" && (
                <div className="status-box error" style={{ marginTop: 8 }}>{litpop.detail}</div>
              )}
              {litpop && litpop.status === "ok" && (
                <>
                  <p className="hint" style={{ marginTop: 8 }}>
                    {litpop.source_label ?? "LitPop"} · {litpop.country}:{" "}
                    {litpop.n_points.toLocaleString()} cells · exposed{" "}
                    {money(litpop.total_value, litpop.currency)} · AAI{" "}
                    {money(litpop.aai_agg, litpop.currency)}/yr ({litpop.peril.replace(/_/g, " ")}
                    {litpop.future_year ? ` ${litpop.future_year}` : ""})
                  </p>
                  {!litpop.aai_agg && litpop.interpretation && (
                    <div className="status-box info" style={{ marginTop: 6 }}>
                      {litpop.interpretation}
                    </div>
                  )}
                </>
              )}
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
