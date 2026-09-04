# Comet on UNRAID — Install & Initialization

A step‑by‑step guide to running Comet as a Docker container on UNRAID and getting
it talking to ComEd and your Emporia Vue.

Comet ships **no prebuilt image on a public registry**, so the first step is
always to *build the image*. Three build paths are covered below — pick one.

---

## 0. Prerequisites

| Need | Notes |
| --- | --- |
| UNRAID 6.12+ with the **Docker** service enabled | Settings → Docker → Enable = Yes |
| An **Emporia** account (email + password) | The Emporia mobile app account. **Two‑factor auth must be OFF** — the `pyemvue` library cannot complete a 2FA login. |
| Your Vue is online and reporting in the Emporia app | Comet reads Emporia's cloud, not the device directly |
| Outbound HTTPS from the server to `hourlypricing.comed.com` and `*.amazonaws.com` | ComEd prices + Emporia (AWS Cognito) auth |
| A recent ComEd bill | Only needed for "estimated total bill" mode (delivery ¢/kWh, taxes, fixed charges) |

Decide a **host port** now (examples below use `8080`) and confirm nothing else on
the server uses it.

---

## 1. Get the code onto the server

Open the UNRAID web terminal (**>_** icon, top right) or SSH in, then:

```bash
mkdir -p /boot/config/plugins/comet-src
cd /mnt/user/appdata
git clone <your-repo-url> comet-build      # or copy the project folder here
cd comet-build
```

> Anywhere on a cache/array share is fine; `/mnt/user/appdata/comet-build` keeps it
> tidy. You only need this folder to **build**; the running container uses
> `/mnt/user/appdata/comet` for data.

---

## 2. Build the image (choose ONE path)

### Path A — Build on the UNRAID box (simplest)

```bash
cd /mnt/user/appdata/comet-build
docker build -t comet:local .
```

When it finishes:

```bash
docker images | grep comet        # you should see  comet   local
```

Use **`comet:local`** as the Repository in step 3.

### Path B — Docker Compose (needs the "Compose Manager" plugin)

1. Install **Compose Manager** from **Apps** (Community Applications).
2. Compose Manager → **Add New Stack** → name it `comet`.
3. Paste the contents of this repo's `docker-compose.yml` into the compose file,
   and paste `.env.example` into the stack's `.env`, editing the values
   (see step 4 for what each one means).
4. Set `build: .` to the full path, e.g. `build: /mnt/user/appdata/comet-build`.
5. Click **Compose Up**. Skip to step 5 (initialization).

### Path C — Build elsewhere, load on UNRAID

On a machine with Docker:

```bash
docker build -t comet:local .
docker save comet:local | gzip > comet.tar.gz
# copy comet.tar.gz to the server, then on the server:
gunzip -c comet.tar.gz | docker load
```

Or push to your own registry / Docker Hub / GHCR and use that path as the
Repository.

---

## 3. Add the container in UNRAID

You can import the bundled template or fill the form by hand.

### Using the template (recommended)

1. Copy `unraid-template/comet.xml` from this repo to
   `/boot/config/plugins/dockerMan/templates-user/comet.xml` on the server:
   ```bash
   cp /mnt/user/appdata/comet-build/unraid-template/comet.xml \
      /boot/config/plugins/dockerMan/templates-user/my-comet.xml
   ```
2. **Docker** tab → **Add Container** → in the **Template** dropdown pick
   **my-comet** (under "User templates").
3. Set **Repository** to the image you built: `comet:local` (Path A/C) — the
   template ships `comet:latest`, change it.
4. Adjust the values (next section), then **Apply**.

### By hand

**Docker** tab → **Add Container**, toggle **Advanced View** (top right), then:

| Field | Value |
| --- | --- |
| **Name** | `Comet` |
| **Repository** | `comet:local` |
| **Network Type** | `Bridge` |
| **Port** | Container `8080` → Host `8080` (TCP) |
| **Path** | Container `/data` → Host `/mnt/user/appdata/comet` (Read/Write) |
| **WebUI** | `http://[IP]:[PORT:8080]/` |

Then add the **Variables** in step 4.

---

## 4. Configure environment variables

Add these as container **Variables** (Key = the name in the table). Only the two
Emporia values are required for live data.

| Key | Example | Required | Purpose |
| --- | --- | --- | --- |
| `EMPORIA_USERNAME` | `you@example.com` | ✅ | Emporia account email |
| `EMPORIA_PASSWORD` | `••••••••` | ✅ (first run only) | Emporia password. Read **only** to create `/data/emporia_tokens.json`; after that Comet refreshes tokens itself and this can be blanked. |
| `EMPORIA_DEVICE_GIDS` | *(empty)* | — | Comma‑separated device GIDs to record. **Leave empty** to auto‑track every device on the account. |
| `COMET_TZ` | `America/Chicago` | — | Timezone for "today" and billing‑cycle boundaries. Default is already correct for ComEd/Illinois. |
| `COMET_MOCK` | `0` | — | `1` = run on simulated data with no credentials (try before committing). |
| `PRICE_POLL_SECONDS` | `300` | — | How often to pull ComEd prices. |
| `METER_POLL_SECONDS` | `60` | — | How often to pull Emporia usage. |

Click **Apply**. UNRAID pulls/starts the container.

---

## 5. Initialize

### 5a. First start — confirm it's alive

Wait ~60–90 seconds after the container starts, then from the server terminal:

```bash
curl -s http://localhost:8080/api/health
```

Expected — `status: "ok"`, `mock: false`, and every job `"ok": true`:

```json
{"status":"ok","mock":false,"scheduler_running":true,
 "jobs":{"prices":{"ok":true,...},
         "meter":{"ok":true,...},
         "backfill":{"ok":true,...}}}
```

Then open the dashboard: **`http://<TOWER-IP>:8080/`** (or click **WebUI** on the
container). Within a couple of minutes the price tile and "Drawing now" should
show real numbers.

### 5b. Verify Emporia is being read

Check the container log (**Docker** tab → click **Comet** → **Logs**). You want a
line like:

```
comet.emporia: authenticated with username/password
comet.emporia: tracking device gids [123456]
```

- The **`tracking device gids [...]`** line lists the GIDs Comet found. If you want
  to record only some of them, put those numbers in `EMPORIA_DEVICE_GIDS` and
  restart.
- If instead you see `meter ingest failed` / an auth error, see
  **Troubleshooting** below.

### 5c. Set your billing cycle and rates (in the UI)

Click the **⚙ (gear)** in the top‑right of the dashboard and fill in:

| Setting | What to enter |
| --- | --- |
| **Cost mode** | `Supply only` to start (just the ComEd hourly price). Switch to `Estimated total bill` once you've entered the rates below. |
| **Billing cycle start** | The date your **current** ComEd bill period began — the "meter read date" / service‑period start printed on your latest invoice. Comet counts "this billing cycle" from here. |
| **Billing cycle length (days)** | Usually `30` (used only for the end‑of‑cycle projection). |
| **Delivery charge (¢/kWh)** | From your bill: total *delivery* charges ÷ kWh used. Only used in total mode. |
| **Other riders (¢/kWh)** | Any per‑kWh line items not covered above (e.g. environmental/efficiency riders). |
| **Fixed monthly charge ($)** | The flat customer/metering charge for the month. |
| **Tax rate (%)** | State/municipal tax applied to the bill, if any. |

Click **Save**. `/api/summary` recomputes immediately and the cards update.

> **Backfill note:** on startup Comet backfills price + hourly usage history from
> the billing‑cycle start (capped at 45 days). If you set the start date to
> something well in the past *after* first launch, **restart the container** once
> so it backfills the fuller range.

### 5d. (Optional) tighten security

After 5b succeeds, edit the container and **blank `EMPORIA_PASSWORD`** (leave
`EMPORIA_USERNAME`). Comet will keep working from the saved token file at
`/mnt/user/appdata/comet/emporia_tokens.json`.

---

## 6. Updating

```bash
cd /mnt/user/appdata/comet-build
git pull
docker build -t comet:local .
```

Then **Docker** tab → **Comet** → **Force update** (or **Compose Up --build** for
Path B). Your data in `/mnt/user/appdata/comet` is untouched.

---

## 7. Backups

Everything persistent lives in **`/mnt/user/appdata/comet/`**:

- `comet.db` — all price/consumption history and your UI settings
- `emporia_tokens.json` — cached Emporia login

The **CA Appdata Backup** plugin (Community Applications) will include this folder
automatically. To reset all history: stop the container, delete `comet.db`,
start it again.

---

## 8. Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| Dashboard loads but **"Drawing now" is blank** and `/api/health` shows `meter.ok:false` | Emporia login failing. Most common: **2FA enabled** on the Emporia account (turn it off), wrong password, or the server can't reach AWS. Check the container log for the exact error. |
| **Price tile blank**, `prices.ok:false` | Server can't reach `https://hourlypricing.comed.com`. Check UNRAID's DNS / outbound firewall / VPN routing. |
| Costs look **~3× too high or too low** | Comet assumes the whole‑home total is Emporia channel `"1,2,3"`. If your device reports the mains differently, the log will show which channels were found — this is a known limitation that may need a one‑line code change in `backend/app/providers/emporia.py`. |
| `/api/health` shows `"mock": true` | `COMET_MOCK` is set to `1` — change it to `0` and restart. |
| "This billing cycle" total seems to **start mid‑cycle** | You changed the cycle‑start date after first launch. Restart the container once to backfill. |
| Container won't start, log mentions **port in use** | Another container/service holds your host port. Pick a different host port in the container's Port mapping. |
| Wrong day boundaries | Set `COMET_TZ` to your IANA timezone (e.g. `America/Chicago`) and restart. |

---

## Quick reference

- **Dashboard:** `http://<TOWER-IP>:8080/`
- **Health JSON:** `http://<TOWER-IP>:8080/api/health`
- **Data dir:** `/mnt/user/appdata/comet/`
- **Rebuild:** `docker build -t comet:local .` then Force update
- **Demo without a device:** set `COMET_MOCK=1`
