import type { Libraries } from "../types";

// Methodology & data provenance — the platform orchestrates open-source methods;
// this page is the honest account of what is computed, with the actual impact
// functions and where the data comes from.
export function MethodView({ libraries }: { libraries: Libraries }) {
  const classes = libraries.impact_functions.classes;
  const depths = libraries.impact_functions.flood_depth_m;
  // Show flood MDR at a few representative depths.
  const showDepths = [0.5, 1, 2, 3];
  const depthIdx = showDepths.map((d) => depths.indexOf(d)).filter((i) => i >= 0);

  return (
    <div className="panelview method-section">
      <h2>Method &amp; data sources</h2>
      <p>
        climaterisk wires your located assets and bundled methodology data into established
        open-source engines. It does not invent climate science. Risk is framed as{" "}
        <strong>probability × impact</strong>.
      </p>

      <div className="card">
        <h3>Physical risk — CLIMADA</h3>
        <p>
          <strong>Risk = Hazard × Exposure × Vulnerability</strong>. A hazard is a probabilistic set
          of events, each with an annual <em>frequency</em>; a vulnerability curve maps hazard
          intensity at a location to a mean damage ratio; exposure is your asset value.
        </p>
        <ul>
          <li>
            <strong>Average Annual Impact</strong> = <code>Σ events (frequency × damage)</code>.
          </li>
          <li>
            <strong>Return-period curve</strong> — loss exceeded on average once per N years.
          </li>
          <li>
            <strong>Present → future delta</strong> — future-horizon AAI vs a present-day baseline
            hazard set (where the peril publishes future scenarios).
          </li>
        </ul>
      </div>

      <div className="card">
        <h3>Impact functions (vulnerability classes)</h3>
        <p>
          Each asset maps to a vulnerability class (by sector, or chosen explicitly). The class
          carries the parameters each peril's damage function needs:
        </p>
        <table className="source-table">
          <thead>
            <tr>
              <th>Class</th>
              <th>TC v½ (m/s)</th>
              <th>Wildfire max MDR</th>
              {depthIdx.map((i) => (
                <th key={i}>Flood MDR @ {depths[i]}m</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {classes.map((c) => (
              <tr key={c.id}>
                <td>{c.label}</td>
                <td>{c.tc_v_half}</td>
                <td>{c.wf_max_mdd.toFixed(2)}</td>
                {depthIdx.map((i) => (
                  <td key={i}>{c.flood_mdr[i].toFixed(2)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="hint">
          <strong>TC</strong> — Emanuel (2011) wind-damage curve; <code>v½</code> is the wind speed
          (m/s) at 50% mean damage (lower = more vulnerable). <strong>Wildfire</strong> — step
          function on brightness temperature (≈295&nbsp;K threshold) rising to the class max MDR.{" "}
          <strong>Flood</strong> — depth-damage curve (mean damage ratio vs water depth), Huizinga
          (2017) style. Lower v½ and higher MDR mean a more vulnerable asset.
        </p>
      </div>

      <div className="card">
        <h3>Perils &amp; data availability</h3>
        <table className="source-table">
          <thead>
            <tr>
              <th>Peril</th>
              <th>Status</th>
              <th>Hazard / source · or why not</th>
            </tr>
          </thead>
          <tbody>
            {libraries.perils.perils.map((p) => (
              <tr key={p.id}>
                <td>{p.label}</td>
                <td>
                  {p.supported_mvp ? (
                    <span className="pill" style={{ color: "var(--accent)" }}>
                      {p.historical_only ? "historical" : p.coverage ? p.coverage : "active"}
                    </span>
                  ) : (
                    <span className="pill" style={{ color: "var(--muted)" }}>
                      unavailable
                    </span>
                  )}
                </td>
                <td>{p.supported_mvp ? p.future_source : p.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="hint">
          Hazard availability was verified against the live CLIMADA Data API. Coastal flood, heat and
          drought have no global future asset-damage hazard set in CLIMADA — the real paths are noted
          above (Aqueduct / petals surge, OS-Climate physrisk for heat, crop-yield models for drought).
        </p>
      </div>

      <div className="card">
        <h3>Transition (policy) risk</h3>
        <p>
          Carbon-cost passthrough:{" "}
          <code>cost(t) = emissions × carbon&nbsp;price(scenario, t)</code>, summed across assets and
          discounted to NPV. Emissions are reported Scope-1 where provided, else a sector-intensity
          proxy.
        </p>
      </div>

      <div className="card">
        <h3>Data sources</h3>
        <table className="source-table">
          <thead>
            <tr><th>Input</th><th>Source</th><th>Notes / licence</th></tr>
          </thead>
          <tbody>
            <tr>
              <td>Hazard (TC, flood, wildfire, windstorm)</td>
              <td>CLIMADA Data API (data.iac.ethz.ch)</td>
              <td>Synthetic/observed event sets; future RCP/SSP where published. CLIMADA is GPL-3.0.</td>
            </tr>
            <tr>
              <td>TC vulnerability</td>
              <td>Emanuel (2011); windstorm: Schwierz et al.</td>
              <td>Calibrated impact functions.</td>
            </tr>
            <tr>
              <td>Carbon price</td>
              <td>NGFS Phase 5 (IIASA)</td>
              <td><strong>Real</strong> — REMIND-MAgPIE, US$2010/t, via <code>pyam</code> (CC-BY).</td>
            </tr>
            <tr>
              <td>Emission factors</td>
              <td>Sector-intensity heuristic</td>
              <td>Order-of-magnitude proxy; reported Scope-1 preferred.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="caveat">
        <strong>Provenance caveat.</strong> NGFS carbon prices are real. The vulnerability-curve
        values (TC v½, wildfire MDR, flood depth-damage) and sector emission intensities are
        indicative MVP values, not yet calibrated. Wildfire is historical-only (CLIMADA publishes no
        future wildfire set). European windstorm covers Europe only. Documented in
        <code>docs/METHODOLOGY.md</code>.
      </div>
    </div>
  );
}
