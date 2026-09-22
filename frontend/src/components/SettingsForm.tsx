import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ConfigModel } from "../lib/api";
import { usd, kwh } from "../lib/format";

const NUMERIC: (keyof ConfigModel)[] = [
  "billing_cycle_days",
  "delivery_cents_per_kwh",
  "other_cents_per_kwh",
  "fixed_monthly_charge",
  "tax_rate_pct",
];

const LABELS: Record<keyof ConfigModel, string> = {
  billing_cycle_start: "Current cycle start (auto-advances when the cycle ends)",
  billing_cycle_days: "Billing cycle length (days)",
  delivery_cents_per_kwh: "Delivery charge (¢/kWh)",
  other_cents_per_kwh: "Other riders (¢/kWh)",
  fixed_monthly_charge: "Fixed monthly charge ($)",
  tax_rate_pct: "Tax rate (%)",
  cost_mode: "Cost mode",
};

export function SettingsForm({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["config"], queryFn: api.config });
  const { data: cycles } = useQuery({ queryKey: ["cycles"], queryFn: api.cycles });
  const [form, setForm] = useState<ConfigModel | null>(null);

  useEffect(() => {
    if (data && !form) setForm(data);
  }, [data, form]);

  const save = useMutation({
    mutationFn: (patch: Partial<ConfigModel>) => api.updateConfig(patch),
    onSuccess: (fresh) => {
      setForm(fresh);
      qc.invalidateQueries();
    },
  });

  if (!form) return null;

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <header>
          <h2>Settings</h2>
          <button className="icon" onClick={onClose}>×</button>
        </header>

        <label className="field">
          <span>{LABELS.cost_mode}</span>
          <select
            value={form.cost_mode}
            onChange={(e) => setForm({ ...form, cost_mode: e.target.value as ConfigModel["cost_mode"] })}
          >
            <option value="supply">Supply only (ComEd hourly price)</option>
            <option value="total">Estimated total bill</option>
          </select>
        </label>

        <label className="field">
          <span>{LABELS.billing_cycle_start}</span>
          <input
            type="date"
            value={form.billing_cycle_start}
            onChange={(e) => setForm({ ...form, billing_cycle_start: e.target.value })}
          />
        </label>

        {NUMERIC.map((k) => (
          <label className="field" key={k}>
            <span>{LABELS[k]}</span>
            <input
              type="number"
              step="0.001"
              value={form[k] as number}
              onChange={(e) => setForm({ ...form, [k]: Number(e.target.value) })}
            />
          </label>
        ))}

        <p className="muted small">
          Total-bill mode adds delivery, riders, fixed charges and tax on top of the ComEd
          supply price. It is an estimate, not a guaranteed match to your printed bill.
        </p>
        <p className="muted small">
          When the cycle reaches its configured length above, it closes on its own: the final
          estimate is saved below and the start date rolls forward — no manual reset needed.
        </p>

        {cycles && cycles.length > 0 && (
          <div className="cycle-history">
            <h3>Previous cycles</h3>
            <ul className="cycle-list">
              {cycles.map((c) => (
                <li key={c.cycle_start}>
                  <div>
                    <div className="value">{c.cycle_start} – {c.cycle_end}</div>
                    <div className="muted small">{kwh(c.kwh)} · {c.days}-day cycle</div>
                  </div>
                  <div className="value">{usd(c.cost_mode === "total" ? c.total_cost : c.supply_cost)}</div>
                </li>
              ))}
            </ul>
          </div>
        )}

        <footer>
          <button className="primary" disabled={save.isPending} onClick={() => save.mutate(form)}>
            {save.isPending ? "Saving…" : "Save"}
          </button>
          {save.isError && <span className="err">Save failed</span>}
          {save.isSuccess && <span className="ok">Saved</span>}
        </footer>
      </div>
    </div>
  );
}
