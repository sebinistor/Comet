export const usd = (n: number | null | undefined): string =>
  n == null ? "—" : n.toLocaleString(undefined, { style: "currency", currency: "USD" });

export const usd4 = (n: number | null | undefined): string =>
  n == null
    ? "—"
    : n.toLocaleString(undefined, {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 2,
        maximumFractionDigits: 4,
      });

export const cents = (n: number | null | undefined): string =>
  n == null ? "—" : `${n.toFixed(2)}¢`;

export const kwh = (n: number | null | undefined): string =>
  n == null ? "—" : `${n.toFixed(2)} kWh`;

export const watts = (n: number | null | undefined): string => {
  if (n == null) return "—";
  if (n >= 1000) return `${(n / 1000).toFixed(2)} kW`;
  return `${Math.round(n)} W`;
};

export const clock = (iso: string | null | undefined): string =>
  !iso ? "—" : new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

// Price severity band for coloring the live tile.
export const priceBand = (c: number | null | undefined): "low" | "mid" | "high" => {
  if (c == null) return "mid";
  if (c < 4) return "low";
  if (c < 9) return "mid";
  return "high";
};
