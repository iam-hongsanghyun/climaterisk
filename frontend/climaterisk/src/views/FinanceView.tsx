import { useState } from "react";
import type {
  FinanceResult,
  FinancialProfile,
  Libraries,
  Portfolio,
  PowerGenBreakdown,
  RatingThreshold,
  Run,
  TransitionResult,
} from "../types";
import { computeFinance } from "../lib/api";
import { money } from "../lib/format";
import { MethodNote } from "../components/MethodNote";

// Optional advanced financing fields; placeholders show the cited reference defaults.
const ADVANCED: { key: keyof FinancialProfile; label: string; step: string }[] = [
  { key: "horizon_years", label: "Horizon (yrs)", step: "1" },
  { key: "debt_fraction", label: "Debt fraction", step: "0.05" },
  { key: "debt_tenor_years", label: "Debt tenor (yrs)", step: "1" },
  { key: "risk_free_rate", label: "Risk-free rate", step: "0.005" },
  { key: "baseline_spread_bps", label: "Baseline spread (bps)", step: "10" },
  { key: "baseline_equity_rate", label: "Equity rate", step: "0.005" },
];

function ratingColor(r: string): string {
  if (["AAA", "AA", "A", "BBB"].includes(r)) return "var(--accent)"; // investment grade
  if (["BB", "B"].includes(r)) return "var(--warn)";
  return "var(--danger)"; // CCC..D distressed
}

export function FinanceView({
  model,
  libraries,
  patchModel,
  physRun,
  transition,
}: {
  model: Portfolio;
  libraries: Libraries;
  patchModel: (patch: Partial<Portfolio>) => void;
  physRun: Run | null;
  transition: TransitionResult | null;
}) {
  const profile = model.run_config.financial_profile ?? {};
  const cur = model.assets[0]?.currency ?? "USD";
  const defaults = (libraries.finance_reference?.financing_defaults ?? {}) as Record<
    string,
    { value: number; source: string }
  >;
  const [result, setResult] = useState<FinanceResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const setProfile = (patch: Partial<FinancialProfile>) =>
    patchModel({ run_config: { ...model.run_config, financial_profile: { ...profile, ...patch } } });

  // DSCR→rating methodology. Every grid is shown side-by-side as a compact comparison keyed by
  // a short code (explained in the legend below); the user ticks one or more "house views" to
  // compare, and can edit the Custom column to build their own grid.
  const fr = libraries.finance_reference;
  const methods = fr?.rating_methods ?? {};
  const defaultMethodId = fr?.default_rating_method ?? "moodys_sp";
  const defaultThresholds = methods[defaultMethodId]?.thresholds ?? [];
  // Rating ladder (row order), top grade first.
  const ratingScale: string[] =
    fr?.rating_scale ??
    [...defaultThresholds].sort((a, b) => b.dscr_min - a.dscr_min).map((t) => t.rating);
  const dscrLookup = (ths: RatingThreshold[]): Record<string, number> =>
    Object.fromEntries(ths.map((t) => [t.rating, t.dscr_min]));
  const customThresholds = profile.custom_rating_thresholds ?? defaultThresholds;

  // Ultra-short codes + full names; fall back when the library predates these fields
  // (e.g. a backend still serving a cached finance_reference).
  const CODE_FALLBACK: Record<string, string> = {
    moodys_sp: "Agency",
    lender_conservative: "Lender",
    equity_lenient: "Sponsor",
  };
  const FULL_FALLBACK: Record<string, string> = {
    moodys_sp: "Moody's / S&P (infrastructure & project finance)",
    lender_conservative: "Lender / banking case (conservative)",
    equity_lenient: "Sponsor / equity case (lenient)",
  };

  // Columns: every named method, then the editable Custom grid.
  const columns = [
    ...Object.entries(methods).map(([id, m]) => ({
      id,
      code: m.code ?? CODE_FALLBACK[id] ?? m.short ?? m.label,
      label: m.label ?? FULL_FALLBACK[id] ?? id,
      source: m.source,
      lookup: dscrLookup(m.thresholds),
      editable: false,
    })),
    {
      id: "custom",
      code: "Custom",
      label: "Custom (build your own)",
      source: "User-defined DSCR→rating grid",
      lookup: dscrLookup(customThresholds),
      editable: true,
    },
  ];

  // Current selection (multi-select). Default to the library default method.
  const selectedIds: string[] =
    profile.rating_methods && profile.rating_methods.length > 0
      ? profile.rating_methods
      : profile.rating_method
        ? [profile.rating_method]
        : [defaultMethodId];
  const isSelected = (id: string) => selectedIds.includes(id);

  const toggleMethod = (id: string) => {
    let next = isSelected(id) ? selectedIds.filter((m) => m !== id) : [...selectedIds, id];
    if (next.length === 0) next = [id]; // always keep at least one selected
    const patch: Partial<FinancialProfile> = { rating_methods: next, rating_method: next[0] };
    if (id === "custom" && next.includes("custom") && !profile.custom_rating_thresholds) {
      patch.custom_rating_thresholds = defaultThresholds.map((t) => ({ ...t }));
    }
    setProfile(patch);
  };
  const setCustomDscr = (rating: string, v: number) => {
    const base = profile.custom_rating_thresholds ?? defaultThresholds;
    const has = base.some((t) => t.rating === rating);
    const next = has
      ? base.map((t) => (t.rating === rating ? { ...t, dscr_min: v } : { ...t }))
      : [...base.map((t) => ({ ...t })), { rating, dscr_min: v }];
    setProfile({ custom_rating_thresholds: next });
  };

  // Asset financial model: "generic" (damage + carbon) or "power_gen" (generation channels).
  const isPower = profile.financial_model === "power_gen";
  const fc = libraries.finance_channels;
  const fuels = Object.keys(fc?.generation_defaults?.capacity_factor_by_fuel ?? {}).filter(
    (k) => !k.startsWith("_"),
  );
  const channelSource =
    `Efficiency: ${fc?.channels?.efficiency?.loss_per_degc?.source ?? "≈0.7%/°C above design temp"}. ` +
    `Outage λ: ${fc?.channels?.outage?.source_lambda ?? "Choobineh & Mohagheghi (2015)"}. ` +
    `Dispatch (전기본 / national plan) is a scenario input — the 전기본 figures are a pending data-sourcing task.`;

  const runDone = physRun?.status === "done";
  const genReady =
    !!profile.capacity_mw && !!profile.power_price && (!!profile.capacity_factor || !!profile.plant_fuel);
  const ready =
    runDone && !!profile.capex && (isPower ? genReady : !!profile.annual_ebitda);
  // steady-state annual carbon cost from the transition run (last horizon year), if present
  const transitionCost = transition?.total_cost_by_year?.length
    ? transition.total_cost_by_year[transition.total_cost_by_year.length - 1]
    : 0;

  async function run() {
    if (!physRun) return;
    setBusy(true);
    setErr(null);
    try {
      setResult(await computeFinance(model.id, physRun.id, transitionCost));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  const numField = (key: keyof FinancialProfile, label: string, step: string) => (
    <div className="field" key={key}>
      <label>{label}</label>
      <input
        type="number"
        step={step}
        value={(profile[key] as number | undefined) ?? ""}
        placeholder={defaults[key] !== undefined ? String(defaults[key].value) : ""}
        onChange={(e) => setProfile({ [key]: e.target.value === "" ? null : Number(e.target.value) })}
      />
    </div>
  );

  const Scenario = ({ label, s }: { label: string; s: FinanceResult["portfolio"]["baseline"] }) => (
    <div className="kpi">
      <div className="kpi-value" style={{ color: ratingColor(s.rating) }}>
        {s.rating}
      </div>
      <div className="kpi-label">
        {label} · DSCR {s.min_dscr === Infinity ? "∞" : s.min_dscr.toFixed(2)} · NPV{" "}
        {money(s.npv, cur)} · {s.spread_bps.toFixed(0)} bps
      </div>
    </div>
  );

  return (
    <div className="panelview">
      <h2>Climate risk premium</h2>
      <p className="hint">
        Translate the run's expected annual climate loss (physical AAI + transition carbon cost)
        into project economics: NPV / IRR / DSCR → credit rating → a counterfactual{" "}
        <strong>Climate Risk Premium (CRP)</strong> — the extra credit spread the climate cashflow
        shock costs. Reference grids: Moody's / S&P (DSCR→rating), Bloomberg (rating→spread).
      </p>

      <div className="card">
        <div className="section-title">Project financial profile (portfolio default)</div>
        <div className="form-row" style={{ marginTop: 8, alignItems: "center", gap: 8 }}>
          <label className="hint" style={{ minWidth: 96 }}>
            Financial model
          </label>
          <select
            className="field-inline"
            value={profile.financial_model ?? "generic"}
            onChange={(e) => setProfile({ financial_model: e.target.value })}
            aria-label="Financial model"
          >
            <option value="generic">Generic — damage (AAI) + carbon</option>
            <option value="power_gen">Power generation — capacity factor</option>
          </select>
        </div>
        <div className="row2" style={{ marginTop: 8 }}>
          {numField("capex", `CAPEX (${cur})`, "1000000")}
          {!isPower && numField("annual_ebitda", `Annual EBITDA (${cur})`, "1000000")}
        </div>

        {isPower && (
          <>
            <div className="section-title" style={{ marginTop: 12 }}>
              Generation
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
              {numField("capacity_mw", "Capacity (MW)", "10")}
              {numField("power_price", `Price (${cur}/MWh)`, "1")}
              {numField("capacity_factor", "Capacity factor", "0.01")}
              <div className="field">
                <label>Fuel (CF default)</label>
                <select
                  className="field-inline"
                  value={profile.plant_fuel ?? ""}
                  onChange={(e) => setProfile({ plant_fuel: e.target.value || null })}
                >
                  <option value="">—</option>
                  {fuels.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </div>
              {numField("opex_per_mwh", `Var O&M (${cur}/MWh)`, "1")}
              {numField("fixed_opex", `Fixed O&M (${cur}/yr)`, "100000")}
            </div>
            <div className="section-title" style={{ marginTop: 12 }}>
              Stressed-scenario channels (fraction 0–1)
            </div>
            <p className="hint" style={{ marginTop: 2 }}>
              How much each channel cuts the effective capacity factor under the scenario.
              Dispatch is <strong>policy</strong> (전기본 / national plan); efficiency, water derate
              and outage are <strong>physical</strong>. Damage (AAI) + carbon flow in automatically
              from the runs.
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
              {numField("dispatch_penalty", "Dispatch (policy)", "0.01")}
              {numField("efficiency_loss", "Efficiency (heat)", "0.01")}
              {numField("capacity_derate", "Water derate (drought)", "0.01")}
              {numField("outage_rate", "Outage (wildfire/storm)", "0.01")}
            </div>
            <p className="hint" style={{ marginTop: 4 }}>
              {channelSource}
            </p>
          </>
        )}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
          {ADVANCED.map((f) => numField(f.key, f.label, f.step))}
        </div>

        <div className="section-title" style={{ marginTop: 14 }}>
          Rating methodology
        </div>
        <p className="hint" style={{ marginTop: 2 }}>
          DSCR ranges differ by agency / case. Tick one or more columns to compare — each is
          assessed at the portfolio level; the first ticked is the primary (headline + per-asset
          ratings). Edit the <strong>Custom</strong> column to build your own.
        </p>
        <div className="table-wrap" style={{ marginTop: 8 }}>
          <table className="agg-table">
            <thead>
              <tr>
                <th style={{ textAlign: "left" }}>Rating · DSCR ≥</th>
                {columns.map((c) => {
                  const sel = isSelected(c.id);
                  return (
                    <th
                      key={c.id}
                      onClick={() => toggleMethod(c.id)}
                      title={c.label}
                      style={{
                        cursor: "pointer",
                        whiteSpace: "nowrap",
                        textAlign: "center",
                        background: sel ? "var(--accent)" : "var(--panel-2)",
                        color: sel ? "#06231f" : "var(--text)",
                      }}
                    >
                      <span style={{ marginRight: 4 }}>{sel ? "☑" : "☐"}</span>
                      {c.code}
                      {c.id === defaultMethodId ? " ★" : ""}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {ratingScale.map((rating) => (
                <tr key={rating}>
                  <td style={{ color: ratingColor(rating), fontWeight: 600 }}>{rating}</td>
                  {columns.map((c) => {
                    const sel = isSelected(c.id);
                    const v = c.lookup[rating];
                    const isFloor = v == null || v <= -900;
                    return (
                      <td
                        key={c.id}
                        style={{
                          textAlign: "center",
                          background: sel ? "var(--panel-2)" : undefined,
                        }}
                      >
                        {c.editable && !isFloor ? (
                          <input
                            className="field-inline"
                            type="number"
                            step="0.05"
                            style={{ width: 64 }}
                            value={v}
                            onChange={(e) => setCustomDscr(rating, Number(e.target.value))}
                          />
                        ) : isFloor ? (
                          <span className="hint">—</span>
                        ) : (
                          `≥ ${v.toFixed(2)}`
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="hint" style={{ marginTop: 6, lineHeight: 1.6 }}>
          ★ library default. Methodologies:
          <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
            {columns.map((c) => (
              <li key={c.id}>
                <strong>{c.code}</strong> — {c.label}
                {c.source ? ` · ${c.source}` : ""}
              </li>
            ))}
          </ul>
        </div>

        <p className="hint" style={{ marginTop: 10 }}>
          Blank fields use the cited defaults (placeholders). Per-asset overrides set on a
          facility produce per-asset ratings below.
        </p>
        <div className="form-row" style={{ marginTop: 10 }}>
          <button className="btn" onClick={run} disabled={!ready || busy}>
            {busy ? (
              <>
                <span className="spinner" /> Computing…
              </>
            ) : (
              "Compute climate risk premium"
            )}
          </button>
          {!runDone && <span className="hint">run a physical analysis first (Results tab)</span>}
          {runDone && !ready && (
            <span className="hint">
              {isPower
                ? "enter CAPEX + capacity (MW) + price + capacity factor (or fuel)"
                : "enter CAPEX + annual EBITDA"}
            </span>
          )}
        </div>
        {err && <div className="status-box error" style={{ marginTop: 8 }}>{err}</div>}
      </div>

      {result && (
        <div className="card">
          <div className="section-title">Portfolio result</div>
          <p className="hint" style={{ marginTop: 2 }}>
            {result.methods_compared && result.methods_compared.length > 1 ? "Primary: " : "Rated under "}
            <strong>{result.rating_method_label}</strong>
            {result.rating_method_source ? ` · ${result.rating_method_source}` : ""}
            {result.methods_compared && result.methods_compared.length > 1
              ? ` · comparing ${result.methods_compared.length} methodologies (below)`
              : ""}
          </p>
          <div
            className="kpi"
            style={{ marginTop: 8, borderColor: result.portfolio.crp_bps > 0 ? "var(--danger)" : "var(--border)" }}
          >
            <div className="kpi-value" style={{ color: result.portfolio.crp_bps > 0 ? "var(--danger)" : "var(--accent)" }}>
              {result.portfolio.crp_bps >= 0 ? "+" : ""}
              {result.portfolio.crp_bps.toFixed(0)} bps
            </div>
            <div className="kpi-label">
              Climate risk premium · {result.portfolio.baseline.rating} →{" "}
              {result.portfolio.stressed.rating}
              {result.portfolio.downgrade ? " (downgrade)" : ""}
            </div>
          </div>
          <div className="kpi-grid" style={{ marginTop: 10 }}>
            <Scenario label="Baseline" s={result.portfolio.baseline} />
            <Scenario label="Climate-stressed" s={result.portfolio.stressed} />
          </div>
          {result.financial_model === "power_gen" ? (
            (() => {
              const bd = result.portfolio_breakdown as PowerGenBreakdown;
              const ch = bd.channels;
              return (
                <p className="hint" style={{ marginTop: 8 }}>
                  Annual EBITDA shock {money(result.portfolio.annual_climate_loss, cur)} · capacity
                  factor {(bd.cf_baseline * 100).toFixed(1)}% → {(bd.cf_effective * 100).toFixed(1)}%
                  · revenue {money(bd.revenue_baseline, cur)} → {money(bd.revenue_stressed, cur)} ·
                  NPV loss {money(result.portfolio.npv_loss, cur)} (
                  {result.portfolio.npv_loss_pct_capex.toFixed(1)}% of CAPEX).
                  <br />
                  Channels — dispatch {(ch.dispatch_penalty * 100).toFixed(0)}%, efficiency{" "}
                  {(ch.efficiency_loss * 100).toFixed(0)}%, water derate{" "}
                  {(ch.capacity_derate * 100).toFixed(0)}%, outage {(ch.outage_rate * 100).toFixed(0)}%
                  · + carbon {money(bd.carbon_cost, cur)} + AAI {money(bd.annual_aai, cur)}.
                </p>
              );
            })()
          ) : (
            <p className="hint" style={{ marginTop: 8 }}>
              Annual climate loss {money(result.total_physical_aai + result.transition_annual_cost, cur)} (physical AAI{" "}
              {money(result.total_physical_aai, cur)} + transition {money(result.transition_annual_cost, cur)}) ·
              NPV loss {money(result.portfolio.npv_loss, cur)} ({result.portfolio.npv_loss_pct_capex.toFixed(1)}% of CAPEX).
            </p>
          )}

          {result.methods_compared && result.methods_compared.length > 1 && (
            <div style={{ marginTop: 12 }}>
              <div className="section-title" style={{ marginBottom: 6 }}>
                Methodology comparison
              </div>
              <div className="table-wrap">
                <table className="agg-table">
                  <thead>
                    <tr>
                      <th>Methodology</th>
                      <th>Baseline</th>
                      <th>Stressed</th>
                      <th>CRP (bps)</th>
                      <th>NPV loss</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.methods_compared.map((m, i) => (
                      <tr key={m.method}>
                        <td title={m.label}>
                          {m.code}
                          {i === 0 ? " (primary)" : ""}
                        </td>
                        <td style={{ color: ratingColor(m.scenario.baseline.rating) }}>
                          {m.scenario.baseline.rating}
                        </td>
                        <td style={{ color: ratingColor(m.scenario.stressed.rating) }}>
                          {m.scenario.stressed.rating}
                        </td>
                        <td>
                          {m.scenario.crp_bps >= 0 ? "+" : ""}
                          {m.scenario.crp_bps.toFixed(0)}
                        </td>
                        <td>{money(m.scenario.npv_loss, cur)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {result.per_asset.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="section-title" style={{ marginBottom: 6 }}>
                Per-asset (overridden facilities)
              </div>
              <div className="table-wrap">
                <table className="agg-table">
                  <thead>
                    <tr>
                      <th>Facility</th>
                      <th>Climate loss/yr</th>
                      <th>Baseline</th>
                      <th>Stressed</th>
                      <th>CRP (bps)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.per_asset.map((a) => (
                      <tr key={a.id}>
                        <td>{a.name}</td>
                        <td>{money(a.annual_climate_loss, cur)}</td>
                        <td style={{ color: ratingColor(a.baseline.rating) }}>{a.baseline.rating}</td>
                        <td style={{ color: ratingColor(a.stressed.rating) }}>{a.stressed.rating}</td>
                        <td>{a.crp_bps >= 0 ? "+" : ""}{a.crp_bps.toFixed(0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      <MethodNote>
        <strong>Counterfactual CRP.</strong> The cashflow is run twice — baseline and with annual
        EBITDA reduced by the expected climate loss. Each gives NPV, IRR and minimum DSCR; DSCR maps
        to a credit rating via the <strong>selected methodology</strong> and the rating to a credit
        spread (Bloomberg US Corp Bond Index). The CRP is the spread increase from baseline to
        stressed. The default DSCR→rating grid follows Moody's Global Infrastructure (2021) / S&P
        Project Finance (2022); a stricter lender case and a lenient sponsor case are provided as
        indicative variants, and you can build a custom grid. All thresholds/spreads live in{" "}
        <code>finance_reference.json</code> with sources; financing defaults are editable starting
        points.
      </MethodNote>
    </div>
  );
}
