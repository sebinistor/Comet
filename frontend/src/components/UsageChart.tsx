import { useState } from "react";
import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HistoryResponse } from "../lib/api";

interface Props {
  data: HistoryResponse | undefined;
  range: "day" | "cycle";
  onRangeChange: (r: "day" | "cycle") => void;
}

export function UsageChart({ data, range, onRangeChange }: Props) {
  const [showPrice, setShowPrice] = useState(true);

  const rows = (data?.points ?? []).map((p) => ({
    ts: p.ts,
    label:
      range === "day"
        ? new Date(p.ts).toLocaleTimeString([], { hour: "2-digit" })
        : new Date(p.ts).toLocaleDateString([], { month: "numeric", day: "numeric" }),
    price: p.price_cents ?? 0,
    kwh: p.kwh ?? 0,
    cumulative: p.cumulative_cost ?? 0,
  }));

  return (
    <section className="tile chart-card">
      <header>
        <span>Usage &amp; cost</span>
        <div className="seg">
          <button className={range === "day" ? "on" : ""} onClick={() => onRangeChange("day")}>
            Today
          </button>
          <button className={range === "cycle" ? "on" : ""} onClick={() => onRangeChange("cycle")}>
            This cycle
          </button>
          <button className={showPrice ? "on" : ""} onClick={() => setShowPrice((v) => !v)}>
            Price
          </button>
        </div>
      </header>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={rows} margin={{ top: 10, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--grid)" strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--muted)" }} minTickGap={16} />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 11, fill: "var(--muted)" }}
              label={{ value: "kWh", angle: -90, position: "insideLeft", fill: "var(--muted)", fontSize: 11 }}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 11, fill: "var(--muted)" }}
              label={{ value: "$", angle: 90, position: "insideRight", fill: "var(--muted)", fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{ background: "var(--bg-elev)", border: "1px solid var(--grid)", borderRadius: 8 }}
              formatter={(v: number, name: string) => [
                name === "Cumulative $" ? `$${v.toFixed(2)}` : name === "Price ¢/kWh" ? `${v.toFixed(2)}¢` : `${v.toFixed(2)}`,
                name,
              ]}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar yAxisId="left" dataKey="kwh" name="kWh" fill="var(--accent-2)" radius={[3, 3, 0, 0]} />
            {showPrice && (
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="price"
                name="Price ¢/kWh"
                stroke="var(--accent-3)"
                dot={false}
                strokeWidth={2}
              />
            )}
            <Area
              yAxisId="right"
              type="monotone"
              dataKey="cumulative"
              name="Cumulative $"
              stroke="var(--accent)"
              fill="var(--accent-soft)"
              strokeWidth={2}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
