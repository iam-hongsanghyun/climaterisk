import type { Portfolio, Run, SupplyChainResult } from "../types";
import { money } from "../lib/format";
import { MethodNote } from "../components/MethodNote";
import { BarsChart } from "../components/BarsChart";

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="kpi">
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}

export function SupplyChainView({
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
  const out = run?.status === "done" ? (run.output as SupplyChainResult | null) : null;

  return (
    <div className="panelview">
      <h2>Supply-chain (indirect impact)</h2>
      <div className="card">
        <p className="hint">
          Propagates the portfolio&apos;s direct tropical-cyclone damage through a
          Multi-Regional Input-Output table (climada_petals static Leontief model) to estimate
          <strong> indirect</strong> losses rippling across economic sectors.
        </p>
        <button
          className="btn"
          onClick={onRun}
          disabled={busy || running || model.assets.length === 0}
        >
          {running ? "Running I/O model…" : busy ? "Submitting…" : "Run supply-chain"}
        </button>
        {running && (
          <p className="hint" style={{ marginTop: 10 }}>
            ⏳ {run?.status}. The first run downloads the MRIO table (large) — this can take a
            few minutes.
          </p>
        )}
        {error && <p className="hint" style={{ color: "var(--danger)" }}>{error}</p>}
        {run?.status === "error" && (
          <p className="hint" style={{ color: "var(--danger)" }}>{run.detail}</p>
        )}
      </div>

      {out && out.status === "ok" && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div className="section-title">Indirect impact</div>
            <span className="pill">{out.mriot}</span>
          </div>
          <div className="kpi-grid">
            <Kpi label="Direct AAI/yr" value={`${money(out.total_direct, cur)}`} />
            <Kpi label="Indirect (rippled)" value={`${money(out.total_indirect, cur)}`} />
            <Kpi
              label="Amplification ×"
              value={out.amplification != null ? `${out.amplification.toFixed(2)}×` : "—"}
            />
          </div>
          {out.by_sector.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <div className="section-title" style={{ marginBottom: 6 }}>
                Indirect impact by sector
              </div>
              <BarsChart
                data={out.by_sector.map((s) => ({ name: s.sector, value: s.indirect }))}
                fmt={(v) => money(v, cur)}
              />
            </div>
          )}
          <MethodNote>
            <strong>Input-output propagation.</strong> Direct asset damage becomes a demand/supply
            shock to the affected sectors; the Leontief inverse of the MRIO technical-coefficient
            matrix spreads it to upstream/downstream sectors. {out.detail}
          </MethodNote>
        </div>
      )}
    </div>
  );
}
