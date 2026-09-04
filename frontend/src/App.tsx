import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./lib/api";
import { PriceTile } from "./components/PriceTile";
import { RollingCostCard } from "./components/RollingCostCard";
import { UsageChart } from "./components/UsageChart";
import { SettingsForm } from "./components/SettingsForm";

type Mode = "supply" | "total";

export default function App() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [range, setRange] = useState<"day" | "cycle">("day");
  const [mode, setMode] = useState<Mode>(() => (localStorage.getItem("comet.mode") as Mode) || "supply");

  useEffect(() => localStorage.setItem("comet.mode", mode), [mode]);

  const now = useQuery({ queryKey: ["now"], queryFn: api.now, refetchInterval: 30_000 });
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary, refetchInterval: 60_000 });
  const history = useQuery({
    queryKey: ["history", range],
    queryFn: () => api.history(range),
    refetchInterval: 120_000,
  });
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 60_000 });

  const s = summary.data;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">◐</span>
          <h1>Comet</h1>
          <span className="muted">ComEd Hourly Pricing · Emporia</span>
        </div>
        <div className="controls">
          <div className="seg">
            <button className={mode === "supply" ? "on" : ""} onClick={() => setMode("supply")}>
              Supply
            </button>
            <button className={mode === "total" ? "on" : ""} onClick={() => setMode("total")}>
              Est. total
            </button>
          </div>
          <button className="icon" title="Settings" onClick={() => setSettingsOpen(true)}>
            ⚙
          </button>
        </div>
      </header>

      {health.data && (health.data.mock || health.data.status !== "ok") && (
        <div className={`banner ${health.data.status !== "ok" ? "warn" : "info"}`}>
          {health.data.mock && <span>Demo mode — showing simulated data. </span>}
          {health.data.status !== "ok" && <span>Some pollers are failing — check /api/health.</span>}
        </div>
      )}

      <main className="grid">
        <PriceTile now={now.data} />
        <RollingCostCard
          title="Today"
          subtitle="since local midnight"
          block={s?.day}
          mode={mode}
        />
        <RollingCostCard
          title="This billing cycle"
          subtitle={s ? `since ${s.invoice.cycle_start}` : ""}
          block={s?.invoice}
          mode={mode}
          projection={mode === "total" ? s?.invoice.projected_total_cost : s?.invoice.projected_supply_cost}
        />
        <div className="span-all">
          <UsageChart data={history.data} range={range} onRangeChange={setRange} />
        </div>
      </main>

      <footer className="foot muted">
        {now.data ? `Updated ${new Date(now.data.generated_at).toLocaleTimeString()}` : "Loading…"}
        {" · "}
        Prices are ComEd supply-side; totals are estimates.
      </footer>

      {settingsOpen && <SettingsForm onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
