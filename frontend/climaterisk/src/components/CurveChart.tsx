import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

/** Line plot of an impact-function curve (x = intensity, y = mean damage ratio). */
export function CurveChart({
  data,
  xLabel,
  color = "#4ea1d3",
  height = 150,
}: {
  data: { x: number; y: number }[];
  xLabel?: string;
  color?: string;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ left: 0, right: 12, top: 6, bottom: 18 }}>
        <CartesianGrid stroke="#2a2f37" />
        <XAxis
          dataKey="x"
          type="number"
          tick={{ fontSize: 11, fill: "#9aa4b2" }}
          label={
            xLabel
              ? { value: xLabel, position: "insideBottom", offset: -8, fill: "#9aa4b2", fontSize: 11 }
              : undefined
          }
        />
        <YAxis tick={{ fontSize: 11, fill: "#9aa4b2" }} domain={[0, 1]} />
        <Tooltip
          contentStyle={{ background: "#23262d", border: "1px solid #3a3f47", fontSize: 12 }}
          labelStyle={{ color: "#e6e6e6" }}
        />
        <Line dataKey="y" stroke={color} dot={{ r: 2 }} strokeWidth={2} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
