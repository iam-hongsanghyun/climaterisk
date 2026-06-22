import type { Libraries, Portfolio } from "../types";

export function ScenariosView({
  model,
  libraries,
  patchModel,
}: {
  model: Portfolio;
  libraries: Libraries;
  patchModel: (patch: Partial<Portfolio>) => void;
}) {
  const { scenario, run_config } = model;

  const setScenario = (patch: Partial<Portfolio["scenario"]>) =>
    patchModel({ scenario: { ...scenario, ...patch } });
  const setRun = (patch: Partial<Portfolio["run_config"]>) =>
    patchModel({ run_config: { ...run_config, ...patch } });

  const togglePeril = (id: string) => {
    const has = run_config.perils.includes(id);
    setRun({
      perils: has ? run_config.perils.filter((p) => p !== id) : [...run_config.perils, id],
    });
  };
  const toggleYear = (y: number) => {
    const has = scenario.anchor_years.includes(y);
    setScenario({
      anchor_years: (has
        ? scenario.anchor_years.filter((x) => x !== y)
        : [...scenario.anchor_years, y]
      ).sort((a, b) => a - b),
    });
  };

  return (
    <div className="panelview">
      <h2>Scenarios &amp; horizon</h2>

      <div className="card">
        <div className="section-title">Physical — climate forcing</div>
        <div className="field" style={{ marginTop: 10 }}>
          <label>Climate scenario (RCP / SSP)</label>
          <select
            value={scenario.climate}
            onChange={(e) => setScenario({ climate: e.target.value })}
          >
            {libraries.scenarios.climate.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="card">
        <div className="section-title">Transition — policy pathway</div>
        <div className="field" style={{ marginTop: 10 }}>
          <label>NGFS scenario</label>
          <select
            value={scenario.transition}
            onChange={(e) => setScenario({ transition: e.target.value })}
          >
            {libraries.scenarios.transition.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Discount rate</label>
          <input
            type="number"
            step="0.005"
            value={run_config.discount_rate}
            onChange={(e) => setRun({ discount_rate: Number(e.target.value) })}
          />
        </div>
      </div>

      <div className="card">
        <div className="section-title">Perils</div>
        {libraries.perils.perils.map((p) => (
          <label
            key={p.id}
            className={`checkrow ${p.supported_mvp ? "" : "disabled"}`}
            title={p.supported_mvp ? p.future_source : p.reason}
          >
            <input
              type="checkbox"
              disabled={!p.supported_mvp}
              checked={run_config.perils.includes(p.id)}
              onChange={() => togglePeril(p.id)}
            />
            {p.label}
            {p.historical_only && <span className="pill">historical</span>}
            {p.coverage && <span className="pill">{p.coverage}</span>}
            {!p.supported_mvp && <span className="pill">no data</span>}
          </label>
        ))}
      </div>

      <div className="card">
        <div className="section-title">Horizon — anchor years</div>
        <div style={{ display: "flex", gap: 14, marginTop: 10, flexWrap: "wrap" }}>
          {libraries.scenarios.anchor_years.map((y) => (
            <label key={y} className="checkrow">
              <input
                type="checkbox"
                checked={scenario.anchor_years.includes(y)}
                onChange={() => toggleYear(y)}
              />
              {y}
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
