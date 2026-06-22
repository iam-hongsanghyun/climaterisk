import { useEffect, useState } from "react";
import { getHazardCatalog, getRun, submitIngest } from "../lib/api";
import type {
  DataSource,
  HazardCatalog,
  IngestResult,
  Libraries,
  Portfolio,
  Run,
} from "../types";

function accessColor(access: string): string {
  const a = access.toLowerCase();
  if (a.includes("paid") || a.includes("academic")) return "var(--danger)";
  if (a.includes("login") || a.includes("registration")) return "var(--accent-2)";
  return "var(--accent)";
}

const FETCH_LABEL: Record<string, string> = {
  manual: "manual download",
  needs_login: "login required — manual",
  operational: "live feed — not a one-time download",
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** One-click download + refine of an auto-ingestable source into the local catalog. */
function IngestControls({
  source,
  model,
  libraries,
  onIngested,
}: {
  source: DataSource;
  model: Portfolio;
  libraries: Libraries;
  onIngested: () => void;
}) {
  const climate = libraries.scenarios.climate;
  const years = libraries.scenarios.anchor_years;
  const [scenario, setScenario] = useState(model.scenario.climate || climate[0]?.id || "rcp85");
  const [year, setYear] = useState(
    model.scenario.anchor_years?.[model.scenario.anchor_years.length - 1] ??
      years[years.length - 1] ??
      2050,
  );
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">("idle");
  const [msg, setMsg] = useState<string | null>(null);

  const noAssets = model.assets.length === 0;

  async function run() {
    setStatus("running");
    setMsg(null);
    try {
      let r: Run = await submitIngest(model.id, {
        source: source.fetch!.source!,
        peril: source.fetch!.peril,
        scenario,
        year,
      });
      for (let i = 0; i < 150 && (r.status === "queued" || r.status === "running"); i++) {
        await sleep(2000);
        r = await getRun(model.id, r.id);
      }
      const out = r.output as IngestResult | null;
      if (r.status === "done" && out?.status === "ok") {
        setStatus("done");
        setMsg(out.detail ?? "Ingested into the local catalog.");
        onIngested();
      } else {
        setStatus("error");
        setMsg(out?.detail ?? r.detail ?? "Ingest failed — see worker log.");
      }
    } catch (e) {
      setStatus("error");
      setMsg(String(e));
    }
  }

  return (
    <div
      style={{
        marginTop: 8,
        padding: "8px 10px",
        background: "var(--surface-2, rgba(255,255,255,0.03))",
        borderRadius: 6,
        display: "flex",
        flexWrap: "wrap",
        gap: 8,
        alignItems: "center",
      }}
    >
      <span className="pill" style={{ color: "var(--accent)" }}>
        ⤓ auto-ingest
      </span>
      <label className="hint">
        scenario{" "}
        <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
          {climate.map((c) => (
            <option key={c.id} value={c.id}>
              {c.id}
            </option>
          ))}
        </select>
      </label>
      <label className="hint">
        year{" "}
        <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </label>
      <button
        className="btn"
        onClick={run}
        disabled={status === "running" || noAssets}
        title={noAssets ? "Place an asset on the Map first" : "Download + refine into the catalog"}
      >
        {status === "running" ? "Fetching…" : "Fetch & ingest"}
      </button>
      {noAssets && <span className="hint">place an asset on the Map first</span>}
      {msg && (
        <span
          className="hint"
          style={{
            flexBasis: "100%",
            color:
              status === "error"
                ? "var(--danger)"
                : status === "done"
                  ? "var(--accent)"
                  : "var(--muted)",
          }}
        >
          {status === "done" ? "✓ " : status === "error" ? "✕ " : ""}
          {msg}
        </span>
      )}
    </div>
  );
}

function SourceRow({
  s,
  model,
  libraries,
  onIngested,
}: {
  s: DataSource;
  model: Portfolio;
  libraries: Libraries;
  onIngested: () => void;
}) {
  const auto = s.fetch?.mode === "auto";
  const modeLabel = s.fetch && s.fetch.mode !== "auto" ? FETCH_LABEL[s.fetch.mode] : null;
  return (
    <div style={{ padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start", justifyContent: "space-between" }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600 }}>
            {s.name}{" "}
            {s.required && (
              <span className="pill" style={{ color: "var(--danger)" }}>
                required
              </span>
            )}
            {auto && (
              <span className="pill" style={{ color: "var(--accent)" }}>
                one-click
              </span>
            )}
          </div>
          <div className="hint" style={{ marginTop: 2 }}>
            {s.for}
            {s.scenarios && ` · scenarios: ${s.scenarios}`}
            {s.place_at && (
              <>
                {" · place at "}
                <code>{s.place_at}</code>
              </>
            )}
          </div>
          <div style={{ marginTop: 4 }}>
            <span className="pill" style={{ color: accessColor(s.access) }}>
              {s.access}
            </span>{" "}
            <span className="pill">{s.license}</span>
            {modeLabel && <span className="pill">{modeLabel}</span>}
          </div>
          {s.notes && (
            <div className="hint" style={{ marginTop: 3 }}>
              {s.notes}
            </div>
          )}
        </div>
        <a
          className="btn secondary"
          href={s.url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ textDecoration: "none", whiteSpace: "nowrap", flexShrink: 0 }}
        >
          {auto ? "Source ↗" : "Download ↗"}
        </a>
      </div>
      {auto && (
        <IngestControls source={s} model={model} libraries={libraries} onIngested={onIngested} />
      )}
    </div>
  );
}

export function DataView({ model, libraries }: { model: Portfolio; libraries: Libraries }) {
  const [catalog, setCatalog] = useState<HazardCatalog | null>(null);
  const refreshCatalog = () => {
    getHazardCatalog()
      .then(setCatalog)
      .catch(() => setCatalog(null));
  };
  useEffect(refreshCatalog, []);

  const { categories, sources } = libraries.data_sources;

  return (
    <div className="panelview">
      <h2>Data sources &amp; catalog</h2>
      <p className="hint">
        Download links for the public datasets each capability needs. Sources marked{" "}
        <span className="pill" style={{ color: "var(--accent)" }}>
          one-click
        </span>{" "}
        can be <strong>downloaded &amp; refined into a CLIMADA-ready hazard</strong> right here
        ("Fetch &amp; ingest") — scoped to your portfolio's region and written to the local catalog
        below, so runs use it automatically. The rest link out (login-gated, live feeds, or large
        drop-ins).
      </p>

      {categories.map((cat) => {
        const rows = sources.filter((s) => s.category === cat.id);
        if (rows.length === 0) return null;
        return (
          <div className="card" key={cat.id}>
            <div className="section-title">{cat.label}</div>
            {cat.note && <p className="hint">{cat.note}</p>}
            {rows.map((s) => (
              <SourceRow
                key={s.id}
                s={s}
                model={model}
                libraries={libraries}
                onIngested={refreshCatalog}
              />
            ))}
          </div>
        );
      })}

      <div className="card">
        <div className="section-title">Local hazard catalog (perils database)</div>
        <p className="hint">
          CLIMADA-ready hazards already ingested locally (used before the Data API). Add more with
          "Fetch &amp; ingest" above, or via <code>scripts/build_hazard.py</code>.
        </p>
        {catalog === null ? (
          <p className="hint">Loading…</p>
        ) : catalog.entries.length === 0 ? (
          <p className="hint">
            Empty — <code>{catalog.dir}</code>. Nothing ingested yet.
          </p>
        ) : (
          <table className="source-table">
            <thead>
              <tr>
                <th>Peril</th>
                <th>Scenario</th>
                <th>Region</th>
                <th>Year</th>
                <th>Events × cent.</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {catalog.entries.map((e, i) => (
                <tr key={i}>
                  <td>{e.peril.replace(/_/g, " ")}</td>
                  <td>{e.climate_scenario}</td>
                  <td>{e.region}</td>
                  <td>{e.year ?? "—"}</td>
                  <td className="num">
                    {e.n_events} × {e.n_centroids}
                  </td>
                  <td>{e.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
