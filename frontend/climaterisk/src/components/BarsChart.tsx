import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

/** Horizontal labeled bar chart (Recharts) — used for Sobol sensitivity, supply-chain
 *  sectors, and similar "name → value" breakdowns. */
export function BarsChart({
  data,
  color = "#4ea1d3",
  height,
  fmt,
}: {
  data: { name: string; value: number }[];
  color?: string;
  height?: number;
  fmt?: (v: number) => string;
}) {
  const h = height ?? Math.max(120, data.length * 34 + 24);
  return (
    <ResponsiveContainer width="100%" height={h}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
        <XAxis
          type="number"
          tick={{ fontSize: 11, fill: "#9aa4b2" }}
          tickFormatter={(v) => (fmt ? fmt(Number(v)) : String(v))}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={140}
          tick={{ fontSize: 11, fill: "#9aa4b2" }}
        />
        <Tooltip
          formatter={(v) => (typeof v === "number" && fmt ? fmt(v) : String(v))}
          contentStyle={{ background: "#23262d", border: "1px solid #3a3f47", fontSize: 12 }}
          labelStyle={{ color: "#e6e6e6" }}
        />
        <Bar dataKey="value" fill={color} radius={[0, 3, 3, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
