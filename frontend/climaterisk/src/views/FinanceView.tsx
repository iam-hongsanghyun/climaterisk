import { useState } from "react";
import type { FinanceResult, FinancialProfile, Libraries, Portfolio, Run, TransitionResult } from "../types";
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

  const runDone = physRun?.status === "done";
  const ready = runDone && !!profile.capex && !!profile.annual_ebitda;
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
        <div className="row2" style={{ marginTop: 8 }}>
          {numField("capex", `CAPEX (${cur})`, "1000000")}
          {numField("annual_ebitda", `Annual EBITDA (${cur})`, "1000000")}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
          {ADVANCED.map((f) => numField(f.key, f.label, f.step))}
        </div>
        <p className="hint" style={{ marginTop: 6 }}>
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
          {runDone && (!profile.capex || !profile.annual_ebitda) && (
            <span className="hint">enter CAPEX + annual EBITDA</span>
          )}
        </div>
        {err && <div className="status-box error" style={{ marginTop: 8 }}>{err}</div>}
      </div>

      {result && (
        <div className="card">
          <div className="section-title">Portfolio result</div>
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
          <p className="hint" style={{ marginTop: 8 }}>
            Annual climate loss {money(result.total_physical_aai + result.transition_annual_cost, cur)} (physical AAI{" "}
            {money(result.total_physical_aai, cur)} + transition {money(result.transition_annual_cost, cur)}) ·
            NPV loss {money(result.portfolio.npv_loss, cur)} ({result.portfolio.npv_loss_pct_capex.toFixed(1)}% of CAPEX).
          </p>

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
        to a credit rating (Moody's Global Infrastructure 2021 / S&P Project Finance 2022) and the
        rating to a credit spread (Bloomberg US Corp Bond Index). The CRP is the spread increase from
        baseline to stressed. All thresholds/spreads live in <code>finance_reference.json</code> with
        sources; financing defaults are editable starting points.
      </MethodNote>
    </div>
  );
}
