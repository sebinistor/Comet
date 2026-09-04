export interface NowResponse {
  generated_at: string;
  price_cents_per_kwh: number | null;
  price_ts: string | null;
  hour_avg_cents_per_kwh: number | null;
  power_watts: number | null;
  cost_rate_per_hour: number | null;
}

export interface RollupBlock {
  kwh: number;
  supply_cost: number;
  total_cost: number;
  start?: string;
}

export interface InvoiceBlock extends RollupBlock {
  cycle_start: string;
  days_elapsed: number;
  days_in_cycle: number;
  projected_supply_cost: number;
  projected_total_cost: number;
}

export interface SummaryResponse {
  cost_mode: "supply" | "total";
  generated_at: string;
  day: RollupBlock;
  invoice: InvoiceBlock;
}

export interface HistoryPoint {
  ts: string;
  price_cents: number | null;
  kwh: number | null;
  cost: number | null;
  cumulative_cost: number | null;
}

export interface HistoryResponse {
  range: "day" | "cycle";
  start: string;
  end: string;
  points: HistoryPoint[];
}

export interface ConfigModel {
  billing_cycle_start: string;
  billing_cycle_days: number;
  delivery_cents_per_kwh: number;
  other_cents_per_kwh: number;
  fixed_monthly_charge: number;
  tax_rate_pct: number;
  cost_mode: "supply" | "total";
}

export interface HealthResponse {
  status: string;
  mock: boolean;
  scheduler_running: boolean;
  jobs: Record<string, { ok: boolean | null; at: string | null; detail: string | null }>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  now: () => get<NowResponse>("/api/now"),
  summary: () => get<SummaryResponse>("/api/summary"),
  history: (range: "day" | "cycle") => get<HistoryResponse>(`/api/history?range=${range}`),
  config: () => get<ConfigModel>("/api/config"),
  health: () => get<HealthResponse>("/api/health"),
  updateConfig: async (patch: Partial<ConfigModel>): Promise<ConfigModel> => {
    const res = await fetch("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!res.ok) throw new Error(`PUT /api/config -> ${res.status}`);
    return res.json() as Promise<ConfigModel>;
  },
};
