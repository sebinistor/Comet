# Comet

Self-hosted dashboard for **ComEd Hourly Pricing** customers with an **Emporia Vue**
energy monitor. It shows:

- **Current electricity price** — the live ComEd hourly (5-minute) rate in ¢/kWh, plus
  your instantaneous draw and the resulting cost rate in $/hr.
- **Rolling cost today** — estimated spend since local midnight.
- **Rolling cost this billing cycle** — estimated spend since your last invoice date,
  with a linear projection to the end of the cycle.

Cost = Emporia consumption (kWh) × ComEd price (¢/kWh). A **supply-only** view (the
ComEd hourly supply charge) is shown by default; an **estimated total bill** view
layers in configurable delivery, rider, fixed and tax components.

Runs as a **single Docker container**, designed for **UNRAID**.

---

## Architecture

```
┌── FastAPI (Uvicorn) ─────────────────────────────┐
│  /api/*        JSON API                           │
│  /             built React SPA (static)          │
│  APScheduler   price poll (5 min)                 │
│                meter poll (60 s)                  │
│                startup backfill                   │
└──────────────────────────┬───────────────────────┘
        ComEd Hourly API ──┤   SQLite  /data/comet.db
        Emporia cloud ─────┘   tokens  /data/emporia_tokens.json
        (pyemvue)
```

- **Backend** — Python 3.12, FastAPI, SQLAlchemy, APScheduler, `pyemvue`, `httpx`.
- **Frontend** — React + TypeScript + Vite, TanStack Query, Recharts.
- **Storage** — one SQLite file on the mounted `/data` volume.
- Data sources sit behind small provider interfaces (`app/providers/`), so demo mode
  swaps in deterministic fakes and a future local-Emporia source can be added without
  touching the ingest or costing code.

### Data sources

- **ComEd** — `https://hourlypricing.comed.com/api` (`5minutefeed`, `currenthouraverage`).
  No auth. Prices are ¢/kWh. The hourly average is used as the billed basis for
  rollups; the 5-minute feed drives the live tile and chart.
- **Emporia** — the community [`pyemvue`](https://github.com/magico13/PyEmVue) library
  against the Emporia cloud (no local device API exists). Your password is only used on
  first login; refreshed tokens are cached in `/data/emporia_tokens.json`.

---

## Quick start (Docker Compose)

```bash
cp .env.example .env        # fill in EMPORIA_USERNAME / EMPORIA_PASSWORD
docker compose up -d --build
# open http://localhost:8080
```

Try it with **no device / no credentials**:

```bash
COMET_MOCK=1 docker compose up --build
```

---

## UNRAID

1. Build and publish the image where your server can pull it:
   ```bash
   docker build -t <your-registry>/comet:latest .
   docker push <your-registry>/comet:latest
   ```
   (or `docker build` directly on the UNRAID box).
2. In **Docker → Add Container → Template**, load `unraid-template/comet.xml`
   (edit `<Repository>` to match your image).
3. Set `EMPORIA_USERNAME` / `EMPORIA_PASSWORD`, map `/data` to
   `/mnt/user/appdata/comet`, publish the WebUI port, and start it.
4. Open the WebUI, click ⚙, and set your **billing cycle start** date plus (optional)
   delivery/tax values for total-bill mode.

---

## Configuration

Environment (immutable, set at container start) — see `.env.example`:

| Var | Default | Purpose |
| --- | --- | --- |
| `EMPORIA_USERNAME` / `EMPORIA_PASSWORD` | — | Emporia cloud login |
| `EMPORIA_DEVICE_GIDS` | all | comma-separated device GIDs to record |
| `COMET_TZ` | `America/Chicago` | day / billing-cycle boundaries |
| `COMET_PORT` | `8080` | published port |
| `COMET_MOCK` | `0` | `1` = simulated data |
| `PRICE_POLL_SECONDS` | `300` | ComEd poll interval |
| `METER_POLL_SECONDS` | `60` | Emporia poll interval |

UI settings (stored in the DB, editable from ⚙):
`billing_cycle_start`, `billing_cycle_days`, `delivery_cents_per_kwh`,
`other_cents_per_kwh`, `fixed_monthly_charge`, `tax_rate_pct`, `cost_mode`.

---

## API

| Endpoint | Description |
| --- | --- |
| `GET /api/now` | current price, draw, $/hr |
| `GET /api/summary` | today + billing-cycle rollups and projection |
| `GET /api/history?range=day\|cycle` | hourly price / kWh / cumulative cost series |
| `GET /api/config` · `PUT /api/config` | read / update UI settings |
| `GET /api/health` | scheduler + last-poll status |

---

## Development

```bash
# backend
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
COMET_MOCK=1 COMET_DATA_DIR=./data python -m app.main   # http://localhost:8080

# frontend (separate terminal, proxies /api to :8080)
cd frontend
npm install
npm run dev                                             # http://localhost:5173

# tests
cd backend && pytest
```

---

## Notes & limitations

- ComEd prices are **supply-side market prices**. Total-bill mode is an approximation,
  not a guaranteed match to your printed invoice.
- The billing cycle is tracked by a single `billing_cycle_start` date — update it each
  invoice (or set it to your monthly meter-read day).
- `pyemvue` uses Emporia's **unofficial** cloud API; poll failures are surfaced in
  `/api/health` and the UI banner.
