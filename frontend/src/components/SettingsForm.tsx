import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ConfigModel } from "../lib/api";

const NUMERIC: (keyof ConfigModel)[] = [
  "billing_cycle_days",
  "delivery_cents_per_kwh",
  "other_cents_per_kwh",
  "fixed_monthly_charge",
  "tax_rate_pct",
];

const LABELS: Record<keyof ConfigModel, string> = {
  billing_cycle_start: "Billing cycle start (last invoice / meter-read date)",
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
