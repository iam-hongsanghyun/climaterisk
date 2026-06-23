import { money } from "../lib/format";

// Carbon-cost trajectory: linear x (years), linear y (annual cost).
export function TransitionChart({
  years,
  values,
  currency,
}: {
  years: number[];
  values: number[];
  currency: string;
}) {
  const W = 460;
  const H = 240;
  const m = { l: 64, r: 16, t: 16, b: 36 };
  const iw = W - m.l - m.r;
  const ih = H - m.t - m.b;
  if (years.length === 0) return null;

  const xMin = years[0];
  const xMax = years[years.length - 1];
  const yMax = Math.max(...values, 1);
  const px = (y: number) => m.l + (xMax === xMin ? iw / 2 : ((y - xMin) / (xMax - xMin)) * iw);
  const py = (v: number) => m.t + ih - (v / yMax) * ih;
  const points = years.map((y, i) => `${px(y)},${py(values[i])}`).join(" ");
  const ticks = years.filter((y) => y % 5 === 0);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Carbon-cost trajectory">
      <line x1={m.l} y1={m.t} x2={m.l} y2={m.t + ih} stroke="var(--border)" />
      <line x1={m.l} y1={m.t + ih} x2={m.l + iw} y2={m.t + ih} stroke="var(--border)" />
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line
            x1={m.l}
            y1={py(yMax * f)}
            x2={m.l + iw}
            y2={py(yMax * f)}
            stroke="var(--border)"
            strokeDasharray="2 4"
            opacity={0.5}
          />
          <text x={m.l - 8} y={py(yMax * f) + 4} textAnchor="end" fontSize="10" fill="var(--muted)">
            {money(yMax * f, currency)}
          </text>
        </g>
      ))}
      {ticks.map((y) => (
        <text key={y} x={px(y)} y={m.t + ih + 16} textAnchor="middle" fontSize="10" fill="var(--muted)">
          {y}
        </text>
      ))}
      <text x={m.l + iw / 2} y={H - 2} textAnchor="middle" fontSize="10" fill="var(--muted)">
        year · annual carbon cost
      </text>
      <polyline points={points} fill="none" stroke="var(--color-carbon)" strokeWidth={2} />
    </svg>
  );
}
