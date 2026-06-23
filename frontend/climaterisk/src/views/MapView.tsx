import { useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMapEvents } from "react-leaflet";
import type { Asset, Libraries, LitPopResult, Portfolio, Run } from "../types";
import { AssetEditor } from "../components/AssetEditor";
import { money } from "../lib/format";

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
  const [litpopCountry, setLitpopCountry] = useState("JPN");
  const [litpopSource, setLitpopSource] = useState("litpop");
  const [litpopPeril, setLitpopPeril] = useState("tropical_cyclone");
  const selected = model.assets.find((a) => a.id === selectedId) ?? null;
  const litpop = litpopRun?.status === "done" ? (litpopRun.output as LitPopResult | null) : null;
  const litpopRunning = litpopRun?.status === "queued" || litpopRun?.status === "running";

  const addAsset = (lat: number, lon: number) => {
    const asset = newAsset(lat, lon);
    patchModel({ assets: [...model.assets, asset] });
    setSelectedId(asset.id);
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
          <ClickToAdd onAdd={addAsset} />
          {model.assets.map((a) => (
            <CircleMarker
              key={a.id}
              center={[a.lat, a.lon]}
              radius={a.id === selectedId ? 11 : 8}
              pathOptions={{
                color: a.id === selectedId ? "#3aa0ff" : "#2f9e8f",
                fillColor: a.id === selectedId ? "#3aa0ff" : "#2f9e8f",
                fillOpacity: 0.7,
                weight: 2,
              }}
              eventHandlers={{ click: () => setSelectedId(a.id) }}
            >
              <Tooltip>
                {a.name} · {a.sector}
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
