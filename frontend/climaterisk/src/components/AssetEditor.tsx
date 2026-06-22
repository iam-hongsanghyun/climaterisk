import type { Asset, Libraries } from "../types";

export function AssetEditor({
  asset,
  libraries,
  onChange,
  onDelete,
  onClose,
}: {
  asset: Asset;
  libraries: Libraries;
  onChange: (patch: Partial<Asset>) => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  const num = (v: string): number => (v === "" ? 0 : Number(v));

  const sectorDefaultClass =
    libraries.sectors.sectors.find((s) => s.id === asset.sector)?.default_vulnerability_class ?? "";
  const classes = libraries.impact_functions.classes;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div className="section-title">Edit facility</div>
        <button className="btn secondary" style={{ padding: "4px 8px" }} onClick={onClose}>
          ← list
        </button>
      </div>

      <div className="field">
        <label>Name</label>
        <input value={asset.name} onChange={(e) => onChange({ name: e.target.value })} />
      </div>

      <div className="field">
        <label>Sector</label>
        <select value={asset.sector} onChange={(e) => onChange({ sector: e.target.value })}>
          {libraries.sectors.sectors.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label>Geographic scale</label>
        <select
          value={asset.geographic_scale}
          onChange={(e) =>
            onChange({ geographic_scale: e.target.value as Asset["geographic_scale"] })
          }
        >
          <option value="point">Point</option>
          <option value="footprint">Footprint</option>
          <option value="regional">Regional</option>
          <option value="national">National</option>
        </select>
      </div>

      <div className="row2">
        <div className="field">
          <label>Latitude</label>
          <input
            type="number"
            value={asset.lat}
            step="0.0001"
            onChange={(e) => onChange({ lat: num(e.target.value) })}
          />
        </div>
        <div className="field">
          <label>Longitude</label>
          <input
            type="number"
            value={asset.lon}
            step="0.0001"
            onChange={(e) => onChange({ lon: num(e.target.value) })}
          />
        </div>
      </div>

      <div className="row2">
        <div className="field">
          <label>Value</label>
          <input
            type="number"
            value={asset.value}
            onChange={(e) => onChange({ value: num(e.target.value) })}
          />
        </div>
        <div className="field">
          <label>Currency</label>
          <input value={asset.currency} onChange={(e) => onChange({ currency: e.target.value })} />
        </div>
      </div>

      <div className="field">
        <label>Annual emissions (tCO₂e) — optional</label>
        <input
          type="number"
          value={asset.annual_emissions_tco2e ?? ""}
          placeholder="proxy from sector if blank"
          onChange={(e) =>
            onChange({
              annual_emissions_tco2e: e.target.value === "" ? null : num(e.target.value),
            })
          }
        />
      </div>

      <div className="field">
        <label>Vulnerability class</label>
        <select
          value={asset.vulnerability_class ?? ""}
          onChange={(e) => onChange({ vulnerability_class: e.target.value || null })}
        >
          <option value="">— sector default ({sectorDefaultClass}) —</option>
          {classes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
      </div>

      <button className="btn danger" onClick={onDelete}>
        Delete facility
      </button>
    </div>
  );
}
