import type { CostBenefitResult, MeasureSpec, Portfolio, Run } from "../types";
import { money } from "../lib/format";

const DEFAULT_MEASURE: MeasureSpec = {
  name: "Retrofit",
  cost: 1_000_000,
  damage_reduction: 0.3,
  risk_transf_attach: 0,
  risk_transf_cover: 0,
};

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="kpi">
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}

export function AdaptationView({
  model,
  measures,
  setMeasures,
  run,
  busy,
  error,
  onRun,
}: {
  model: Portfolio;
  measures: MeasureSpec[];
  setMeasures: (updater: (ms: MeasureSpec[]) => MeasureSpec[]) => void;
  run: Run | null;
  busy: boolean;
  error: string | null;
  onRun: () => void;
}) {
  const currency = model.assets[0]?.currency ?? "USD";
  const start = onRun;

  const update = (i: number, patch: Partial<MeasureSpec>) =>
    setMeasures((ms) => ms.map((m, j) => (j === i ? { ...m, ...patch } : m)));
  const addMeasure = () =>
    setMeasures((ms) => [...ms, { ...DEFAULT_MEASURE, name: `Measure ${ms.length + 1}` }]);
  const removeMeasure = (i: number) => setMeasures((ms) => ms.filter((_, j) => j !== i));

  const running = run?.status === "queued" || run?.status === "running";
  const cb = run?.status === "done" ? (run.output as CostBenefitResult | null) : null;

  return (
    <div className="panelview">
      <h2>Adaptation — cost-benefit</h2>
      <div className="card">
        <div className="section-title">Adaptation measures</div>
        <p className="hint">
          Define measures; CLIMADA computes the NPV of averted damage (benefit) vs cost over the
          portfolio, present → future. Damage reduction scales the vulnerability curve; insurance
          attach/cover models a risk-transfer layer. Peril: tropical cyclone.
        </p>
        {measures.map((m, i) => (
          <div key={i} className="card" style={{ background: "var(--panel-2)", marginBottom: 8 }}>
            <div className="row2">
              <div className="field">
                <label>Name</label>
                <input value={m.name} onChange={(e) => update(i, { name: e.target.value })} />
              </div>
              <div className="field">
                <label>Cost ({currency})</label>
                <input
                  type="number"
                  value={m.cost}
                  onChange={(e) => update(i, { cost: Number(e.target.value) })}
                />
              </div>
            </div>
            <div className="row2">
              <div className="field">
                <label>Damage reduction (%)</label>
                <input
                  type="number"
                  value={Math.round(m.damage_reduction * 100)}
                  onChange={(e) => update(i, { damage_reduction: Number(e.target.value) / 100 })}
                />
              </div>
              <div className="field">
                <label>Insurance attach / cover</label>
                <div style={{ display: "flex", gap: 6 }}>
                  <input
                    type="number"
                    placeholder="attach"
                    value={m.risk_transf_attach ?? 0}
                    onChange={(e) => update(i, { risk_transf_attach: Number(e.target.value) })}
                  />
                  <input
                    type="number"
                    placeholder="cover"
                    value={m.risk_transf_cover ?? 0}
                    onChange={(e) => update(i, { risk_transf_cover: Number(e.target.value) })}
                  />
                </div>
              </div>
            </div>
            {measures.length > 1 && (
              <button className="btn danger" style={{ padding: "4px 10px" }} onClick={() => removeMeasure(i)}>
                Remove
              </button>
            )}
          </div>
        ))}
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button className="btn secondary" onClick={addMeasure}>
            + Add measure
          </button>
          <button className="btn" onClick={start} disabled={busy || running || model.assets.length === 0}>
            {running ? "Running CLIMADA…" : busy ? "Submitting…" : "Run cost-benefit"}
          </button>
        </div>
        {running && <p className="hint" style={{ marginTop: 10 }}>⏳ {run?.status}…</p>}
        {error && <p className="hint" style={{ color: "var(--danger)" }}>{error}</p>}
      </div>

      {run?.status === "error" && (
        <div className="card">
          <div className="section-title">Run failed</div>
          <pre style={{ whiteSpace: "pre-wrap", color: "var(--danger)", fontSize: 12 }}>{run.detail}</pre>
        </div>
      )}

      {cb && cb.status === "ok" && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div className="section-title">Result · {cb.peril.replace(/_/g, " ")}</div>
            <span className="pill">horizon {cb.future_year} · disc {(cb.discount_rate * 100).toFixed(1)}%</span>
          </div>
          <div className="kpi-grid" style={{ gridTemplateColumns: "1fr" }}>
            <Kpi label="Total climate risk (NPV, unaverted)" value={money(cb.tot_climate_risk, cb.currency)} />
          </div>
          <table className="agg-table" style={{ marginTop: 12 }}>
            <thead>
              <tr><th>Measure</th><th>Cost</th><th>Benefit (NPV averted)</th><th>Benefit / cost</th><th></th></tr>
            </thead>
            <tbody>
              {cb.measures.map((m) => {
                const bc = m.benefit_cost_ratio;
                return (
                  <tr key={m.name}>
                    <td>{m.name}</td>
                    <td className="num">{money(m.cost, cb.currency)}</td>
                    <td className="num">{money(m.benefit, cb.currency)}</td>
                    <td className="num">{bc == null ? "—" : bc.toFixed(2)}</td>
                    <td>
                      {bc != null && (
                        <span className="pill" style={{ color: bc >= 1 ? "var(--accent)" : "var(--muted)" }}>
                          {bc >= 1 ? "cost-effective" : "below 1"}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="hint">{cb.detail}</p>
        </div>
      )}
    </div>
  );
}
