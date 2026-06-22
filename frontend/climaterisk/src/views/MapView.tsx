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
  onRunLitpop: (country: string) => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [litpopCountry, setLitpopCountry] = useState("JPN");
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
              <p className="hint">No facilities yet.</p>
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

            <div style={{ borderTop: "1px solid var(--border)", marginTop: 12, paddingTop: 12 }}>
              <div className="section-title">Modeled exposure (LitPop)</div>
              <p className="hint">
                Model a whole country's asset values from population × nightlights (CLIMADA LitPop)
                instead of hand-entering assets, then run TC impact.
              </p>
              <div style={{ display: "flex", gap: 6 }}>
                <input
                  value={litpopCountry}
                  onChange={(e) => setLitpopCountry(e.target.value.toUpperCase())}
                  maxLength={3}
                  placeholder="ISO3"
                  style={{
                    width: 70,
                    background: "var(--panel-2)",
                    border: "1px solid var(--border)",
                    color: "var(--text)",
                    borderRadius: 6,
                    padding: "7px 9px",
                  }}
                />
                <button
                  className="btn"
                  onClick={() => onRunLitpop(litpopCountry)}
                  disabled={litpopBusy || litpopRunning || litpopCountry.length !== 3}
                >
                  {litpopRunning ? "Modeling…" : "Model exposure"}
                </button>
              </div>
              {litpopErr && <p className="hint" style={{ color: "var(--danger)" }}>{litpopErr}</p>}
              {litpopRun?.status === "error" && (
                <p className="hint" style={{ color: "var(--danger)" }}>{litpopRun.detail}</p>
              )}
              {litpop && litpop.status === "ok" && (
                <p className="hint">
                  {litpop.country}: {litpop.n_points.toLocaleString()} cells ·
                  exposed {money(litpop.total_value, litpop.currency)} · AAI{" "}
                  {money(litpop.aai_agg, litpop.currency)}/yr (TC {litpop.future_year})
                </p>
              )}
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
