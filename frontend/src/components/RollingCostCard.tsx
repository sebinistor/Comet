import type { InvoiceBlock, RollupBlock } from "../lib/api";
import { kwh, usd } from "../lib/format";

interface Props {
  title: string;
  subtitle: string;
  block: RollupBlock | InvoiceBlock | undefined;
  mode: "supply" | "total";
  projection?: number | null;
}

function isInvoice(b: RollupBlock | InvoiceBlock | undefined): b is InvoiceBlock {
  return !!b && "days_elapsed" in b;
}

export function RollingCostCard({ title, subtitle, block, mode, projection }: Props) {
  const cost = block ? (mode === "total" ? block.total_cost : block.supply_cost) : null;
  return (
    <section className="tile cost-card">
      <header>
        <span>{title}</span>
        <span className="muted">{subtitle}</span>
      </header>
      <div className="big">{usd(cost)}</div>
      <div className="tile-row">
        <div>
          <div className="label">Energy</div>
          <div className="value">{kwh(block?.kwh)}</div>
        </div>
        {mode === "total" && block && (
          <div>
            <div className="label">Supply only</div>
            <div className="value">{usd(block.supply_cost)}</div>
          </div>
        )}
        {projection != null && (
          <div>
            <div className="label">Projected</div>
            <div className="value">{usd(projection)}</div>
          </div>
        )}
        {isInvoice(block) && (
          <div>
            <div className="label">Day {Math.floor(block.days_elapsed)} / {block.days_in_cycle}</div>
            <div className="value">since {block.cycle_start}</div>
          </div>
        )}
      </div>
    </section>
  );
}
