import type { PhysicalRunOutput, PhysicalRunResult, Portfolio, Run, TransitionResult } from "../types";
import { money } from "../lib/format";
import { lazy, Suspense } from "react";
import { ResultsMap } from "../components/ResultsMap";
import { FreqCurveChart } from "../components/FreqCurveChart";

// AG-Grid is heavy (~1 MB) — load it only when a multi-asset result renders.
const AssetGrid = lazy(() =>
  import("../components/AssetGrid").then((m) => ({ default: m.AssetGrid })),
);
import { TransitionChart } from "../components/TransitionChart";
import { MethodNote } from "../components/MethodNote";
import { Aggregation } from "../components/Aggregation";
import { UncertaintyPanel } from "../components/UncertaintyPanel";

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="kpi">
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}

function PhysicalResult({ result, currency }: { result: PhysicalRunResult; currency: string }) {
  const title = result.peril.replace(/_/g, " ");
  if (result.status !== "ok") {
    return (
      <div className="card">
        <div className="section-title">{title}</div>
        <p className="hint">
          <span className="pill">{result.status}</span> {result.detail}
        </p>
      </div>
    );
  }
  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div className="section-title">Physical · {title}</div>
        <span className="pill">horizon {result.target_year}</span>
      </div>
      <div className="kpi-grid">
        <Kpi
          label={
            result.result_kind && result.result_kind !== "monetary"
              ? (result.metric_unit ?? result.result_kind)
              : "Avg annual impact"
          }
          value={`${money(result.aai_agg, currency)}/yr`}
        />
        <Kpi label="Total exposed value" value={money(result.total_value, currency)} />
        <Kpi
          label="AAI / value"
          value={`${((result.aai_agg / Math.max(result.total_value, 1)) * 100).toFixed(2)}%`}
        />
      </div>
      {result.delta_pct != null && result.present_aai_agg != null && (
        <p className="hint" style={{ marginTop: 10 }}>
          Climate change to {result.target_year}:{" "}
          <strong style={{ color: result.delta_pct >= 0 ? "var(--danger)" : "var(--accent)" }}>
            {result.delta_pct >= 0 ? "+" : ""}
            {result.delta_pct.toFixed(1)}%
          </strong>{" "}
          vs present-day baseline (AAI {money(result.present_aai_agg, currency)}/yr → {money(result.aai_agg, currency)}/yr).
        </p>
      )}
      <div style={{ marginTop: 14 }}>
        <ResultsMap impacts={result.per_asset} currency={currency} />
      </div>
      {result.per_asset.length > 1 && (
        <div style={{ marginTop: 14 }}>
          <div className="section-title" style={{ marginBottom: 6 }}>
            Per-asset expected annual impact
          </div>
          <Suspense fallback={<p className="hint">Loading grid…</p>}>
            <AssetGrid impacts={result.per_asset} currency={currency} />
          </Suspense>
        </div>
      )}
      {result.freq_curve && (
        <div style={{ marginTop: 14 }}>
          <div className="section-title" style={{ marginBottom: 6 }}>
            Return-period losses
          </div>
          <FreqCurveChart curve={result.freq_curve} currency={currency} />
        </div>
      )}
      {result.yearset && (result.result_kind ?? "monetary") === "monetary" && (
        <div style={{ marginTop: 14 }}>
          <div className="section-title" style={{ marginBottom: 6 }}>
            Annual-loss distribution ({result.yearset.n_years} sampled years)
          </div>
          <div className="kpi-grid">
            <Kpi label="Mean year (≈ AAI)" value={`${money(result.yearset.mean, currency)}/yr`} />
            <Kpi label="1-in-10-yr loss" value={money(result.yearset.p90, currency)} />
            <Kpi label="1-in-100-yr loss" value={money(result.yearset.p99, currency)} />
            <Kpi label="Worst modeled year" value={money(result.yearset.max, currency)} />
          </div>
          <p className="hint" style={{ marginTop: 6 }}>
            CLIMADA yearsets Poisson-samples events into years — the mean reproduces AAI while the
            tail shows how bad a rare year can be (a median year is often {money(result.yearset.p50, currency)}).
          </p>
        </div>
      )}
      {result.warn_levels && result.warn_levels.counts.some((c) => c > 0) && (
        <div style={{ marginTop: 14 }}>
          <div className="section-title" style={{ marginBottom: 6 }}>
            Hazard warning bands ({result.warn_levels.unit || "intensity"})
          </div>
          <div style={{ display: "flex", height: 22, borderRadius: 5, overflow: "hidden", border: "1px solid var(--border)" }}>
            {result.warn_levels.counts.map((c, i) => {
              const total = result.warn_levels!.counts.reduce((a, b) => a + b, 0) || 1;
              const hue = 120 - (i / Math.max(result.warn_levels!.n_levels - 1, 1)) * 120; // green→red
              return c > 0 ? (
                <div
                  key={i}
                  title={`Band ${i + 1}: ${c} asset(s)`}
                  style={{ width: `${(c / total) * 100}%`, background: `hsl(${hue} 65% 45%)` }}
                />
              ) : null;
            })}
          </div>
          <p className="hint" style={{ marginTop: 6 }}>
            Assets binned by peak hazard intensity (CLIMADA <code>Warn.bin_map</code>): band 1 = lowest,{" "}
            {result.warn_levels.n_levels} = highest. Counts:{" "}
            {result.warn_levels.counts.map((c, i) => `L${i + 1}:${c}`).join(" · ")}.
          </p>
        </div>
      )}
      <MethodNote>
        <strong>Probability × impact.</strong> <em>Avg Annual Impact = Σ events (frequency × damage)</em>,
        computed by CLIMADA over a probabilistic hazard event set × a per-asset vulnerability curve ×
        your asset value. The return-period curve is the loss exceeded once per N years; the delta
        compares the future horizon to a present-day baseline hazard set.
        <br />
        <strong>Data:</strong>{" "}
        {result.peril === "tropical_cyclone" ? (
          <>
            hazard — CLIMADA Data API tropical-cyclone sets (synthetic tracks perturbed from IBTrACS;
            future = RCP × reference year {result.target_year}); vulnerability — Emanuel (2011)
            wind-damage function with a per-class <code>v_half</code>.
          </>
        ) : (
          <>
            hazard — CLIMADA Data API river-flood depth sets (ISIMIP-derived; future = RCP ×
            year-range to {result.target_year}); vulnerability — per-class depth-damage curve
            (Huizinga-style).
          </>
        )}{" "}
        exposure — your inputs. ({result.detail}.)
      </MethodNote>
    </div>
  );
}

function TransitionCard({ t, currency }: { t: TransitionResult; currency: string }) {
  if (t.years.length === 0) {
    return (
      <div className="card">
        <div className="section-title">Transition risk</div>
        <p className="hint">{t.detail}</p>
      </div>
    );
  }
  const lastIdx = t.years.length - 1;
  const proxied = t.per_asset.filter((a) => a.emissions_source === "sector_proxy").length;
  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div className="section-title">Transition · {t.scenario.replace(/_/g, " ")}</div>
        <span className="pill">NGFS · {t.base_year}–{t.years[lastIdx]}</span>
      </div>
      <div className="kpi-grid">
        <Kpi label={`Carbon cost ${t.years[lastIdx]}`} value={`${money(t.total_cost_by_year[lastIdx], currency)}/yr`} />
        <Kpi label="Carbon-cost NPV" value={money(t.total_npv, currency)} />
        <Kpi label={`Carbon cost ${t.base_year}`} value={`${money(t.total_cost_by_year[0], currency)}/yr`} />
      </div>
      <div style={{ marginTop: 14 }}>
        <div className="section-title" style={{ marginBottom: 6 }}>
          Annual carbon cost by year
        </div>
        <TransitionChart years={t.years} values={t.total_cost_by_year} currency={currency} />
      </div>
      <MethodNote>
        <strong>Policy cost passthrough.</strong> <em>cost(t) = emissions × carbon&nbsp;price(scenario, t)</em>,
        summed across assets; NPV discounts future costs at {(t.discount_rate * 100).toFixed(1)}%.
        {proxied > 0 && ` ${proxied} asset(s) used a sector-intensity emissions proxy (no reported Scope-1).`}
        <br />
        <strong>Data:</strong> carbon price — real NGFS Phase 5 (REMIND-MAgPIE, US$2010/t) via pyam;
        emissions — reported Scope-1 where given, else a sector-intensity heuristic (see Method).
      </MethodNote>
    </div>
  );
}

export function ResultsView({
  model,
  run,
  transition,
  busy,
  error,
  onRun,
  uncRun,
  uncBusy,
  uncErr,
  onRunUncertainty,
  cbRunId,
  scRunId,
  fcRunId,
  calRunId,
}: {
  model: Portfolio;
  run: Run | null;
  transition: TransitionResult | null;
  busy: boolean;
  error: string | null;
  onRun: () => void;
  uncRun: Run | null;
  uncBusy: boolean;
  uncErr: string | null;
  onRunUncertainty: () => void;
  cbRunId?: string;
  scRunId?: string;
  fcRunId?: string;
  calRunId?: string;
}) {
  const currency = model.assets[0]?.currency ?? "USD";
  const running = run?.status === "queued" || run?.status === "running";

  const reportParams = new URLSearchParams();
  if (run?.id) reportParams.set("run_id", run.id);
  if (cbRunId) reportParams.set("cb_run_id", cbRunId);
  if (uncRun?.id) reportParams.set("unc_run_id", uncRun.id);
  if (scRunId) reportParams.set("sc_run_id", scRunId);
  if (fcRunId) reportParams.set("fc_run_id", fcRunId);
  if (calRunId) reportParams.set("cal_run_id", calRunId);
  const reportHref = `/api/session/${model.id}/report?${reportParams.toString()}`;

  return (
    <div className="panelview">
      <h2>Results</h2>
      <div className="card">
        <p className="hint">
          <strong>{model.assets.length}</strong> facility(ies) · climate{" "}
          <span className="pill">{model.scenario.climate}</span> · transition{" "}
          <span className="pill">{model.scenario.transition.replace(/_/g, " ")}</span> · perils{" "}
          {model.run_config.perils.map((p) => (
            <span key={p} className="pill">
              {p.replace(/_/g, " ")}
            </span>
          ))}
        </p>
        <button className="btn" onClick={onRun} disabled={busy || running || model.assets.length === 0}>
          {running ? "Running CLIMADA…" : busy ? "Submitting…" : "Run analysis"}
        </button>
        <a
          className="btn secondary"
          href={reportHref}
          style={{ marginLeft: 8, textDecoration: "none", display: "inline-block" }}
        >
          Download report
        </a>
        {run?.status === "done" && (
          <>
            <a
              className="btn secondary"
              href={`/api/session/${model.id}/run/${run.id}/export?fmt=csv`}
              style={{ marginLeft: 8, textDecoration: "none", display: "inline-block" }}
            >
              Export CSV
            </a>
            <a
              className="btn secondary"
              href={`/api/session/${model.id}/run/${run.id}/export?fmt=geojson`}
              style={{ marginLeft: 8, textDecoration: "none", display: "inline-block" }}
            >
              Export GeoJSON
            </a>
          </>
        )}
        {running && (
          <div className="status-box running" style={{ marginTop: 10 }}>
            <span className="spinner" />
            <span>
              Physical run: {run?.status}. The first run downloads hazard data and can take a minute.
            </span>
          </div>
        )}
        {error && (
          <div className="status-box error" style={{ marginTop: 10 }}>
            {error}
          </div>
        )}
      </div>

      {run?.status === "error" && (
        <div className="card">
          <div className="section-title">Physical run failed</div>
          <pre className="status-box error" style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
            {run.detail}
          </pre>
        </div>
      )}

      {run?.status === "done" &&
        (run.output as PhysicalRunOutput | null)?.results?.map((r) => (
          <PhysicalResult key={r.peril} result={r} currency={currency} />
        ))}

      {transition && <TransitionCard t={transition} currency={currency} />}

      {(run?.status === "done" || transition) && model.assets.length > 0 && (
        <Aggregation model={model} run={run} transition={transition} currency={currency} />
      )}

      {model.assets.length > 0 && (
        <UncertaintyPanel run={uncRun} busy={uncBusy} error={uncErr} onRun={onRunUncertainty} />
      )}
    </div>
  );
}
