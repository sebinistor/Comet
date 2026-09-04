import type { NowResponse } from "../lib/api";
import { cents, clock, priceBand, usd4, watts } from "../lib/format";

export function PriceTile({ now }: { now: NowResponse | undefined }) {
  const band = priceBand(now?.price_cents_per_kwh);
  return (
    <section className={`tile price-tile band-${band}`}>
      <header>
        <span>ComEd price now</span>
        <span className="muted">as of {clock(now?.price_ts)}</span>
      </header>
      <div className="big">{cents(now?.price_cents_per_kwh)}<span className="unit">/kWh</span></div>
      <div className="tile-row">
        <div>
          <div className="label">Hour average</div>
          <div className="value">{cents(now?.hour_avg_cents_per_kwh)}</div>
        </div>
        <div>
          <div className="label">Drawing now</div>
          <div className="value">{watts(now?.power_watts)}</div>
        </div>
        <div>
          <div className="label">Cost rate</div>
          <div className="value">{usd4(now?.cost_rate_per_hour)}<span className="unit">/hr</span></div>
        </div>
      </div>
    </section>
  );
}
