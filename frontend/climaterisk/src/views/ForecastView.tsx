import type { ForecastResult, Portfolio, Run } from "../types";
import { money } from "../lib/format";
import { ResultsMap } from "../components/ResultsMap";
import { MethodNote } from "../components/MethodNote";

export function ForecastView({
  model,
  run,
  busy,
  error,
  onRun,
}: {
  model: Portfolio;
  run: Run | null;
  busy: boolean;
  error: string | null;
  onRun: () => void;
}) {
  const cur = model.assets[0]?.currency ?? "USD";
  const running = run?.status === "queued" || run?.status === "running";
  const out = run?.status === "done" ? (run.output as ForecastResult | null) : null;

  return (
    <div className="panelview">
      <h2>Operational forecast</h2>
      <div className="card">
        <p className="hint">
          Pulls the latest <strong>ECMWF ensemble</strong> tropical-cyclone tracks and computes the
          forecast impact on the portfolio. This is a live operational feed — tracks exist only
          while a storm is active, so off-season this returns &ldquo;no active tracks&rdquo;.
        </p>
        <button
          className="btn"
          onClick={onRun}
          disabled={busy || running || model.assets.length === 0}
        >
          {running ? "Fetching ECMWF…" : busy ? "Submitting…" : "Run forecast"}
        </button>
        {running && (
          <p className="hint" style={{ marginTop: 10 }}>⏳ {run?.status}. Fetching the live feed…</p>
        )}
        {error && <p className="hint" style={{ color: "var(--danger)" }}>{error}</p>}
        {run?.status === "error" && (
          <p className="hint" style={{ color: "var(--danger)" }}>{run.detail}</p>
        )}
      </div>

      {out && out.status === "ok" && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div className="section-title">Forecast impact</div>
            <span className="pill">{out.n_tracks} ensemble tracks</span>
          </div>
          {out.n_tracks === 0 ? (
            <p className="hint">{out.detail}</p>
          ) : (
            <>
              <div className="kpi-grid">
                <div className="kpi">
                  <div className="kpi-value">{money(out.total_impact, cur)}</div>
                  <div className="kpi-label">Ensemble-mean impact</div>
                </div>
              </div>
              {out.per_asset.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <ResultsMap impacts={out.per_asset} currency={cur} />
                </div>
              )}
              <MethodNote>
                <strong>Operational forecast.</strong> Each ECMWF ensemble member is a perturbed TC
                track; CLIMADA builds the wind field and the Emanuel damage function gives the impact
                per asset. {out.detail}
              </MethodNote>
            </>
          )}
        </div>
      )}
    </div>
  );
}
