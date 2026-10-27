# WindGap: UK wind forecast accuracy for day-ahead buying

Live app: <https://qx7wnd.vercel.app/>

A buyer has to fix tomorrow's power purchases on the day before, using the national wind forecast
available at that moment. If the forecast promises more wind than arrives, the gap must be bought
later at a worse price. The app answers two questions:

1. How accurate was the forecast the buyer could actually see at decision time (09:00 UTC on D-1)?
2. Can a simple bias correction, trained only on data known at that time, make it better?

## Results (09:00 cutoff, January 2026)

31 delivery days, 2 Jan to 1 Feb 2026, 744 hours.
Purchase decisions are made in January on D-1, so delivery days run from 2 Jan (decided 1 Jan)
to 1 Feb (decided 31 Jan).

| Metric | Value |
|---|---|
| MAE | 2,039 MW |
| RMSE | 2,505 MW |
| Bias (mean of forecast − actual) | +1,748 MW (forecast about 15% above actual on average) |
| P10 / P90 of error | −549 MW / +4,098 MW |
| Shortfall (wind forecast but not delivered) | 1,408.7 GWh |
| Extra wind (delivered but not forecast) | 108.3 GWh |

- The over-forecast is structural. Bias is still about 1,400–1,500 MW at 0–6 h and 6–12 h lead
  time, so it is not just a long-range problem. Curtailment (wind farms told to turn down) could
  explain part of it, but that is a hypothesis and the app does not test it.
- Waiting until 09:50 to pick up the 09:30 publish improves MAE by only about 26 MW (2,013 MW).
- The ratio correction lowers MAE to 1,437 MW and beats the raw forecast on 21 of 31 days. The app
  shows it as an experimental toggle, not as the main result (see the disclosure below).

## Method

- **Actuals:** Elexon BMRS `FUELHH`, fuel type `WIND`, half-hourly. The two half-hours of each hour
  are averaged; hours missing a half are dropped.
- **Forecasts:** Elexon BMRS `WINDFOR`, hourly national wind forecasts. Publishes arrive at 8
  regular times a day (02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30 UTC), plus one
  irregular publish at 12:25 on 15 Jan. Forecast rows for hours at or before the publish time
  (lead ≤ 0) are dropped.
- **Decision-time forecast:** for delivery day D (00:00–23:00 UTC), the latest publish at or before
  the cutoff (default 09:00 UTC) on D-1. With the regular schedule that is the 07:30 publish. If that
  publish does not cover all 24 hours, the app reports an error instead of falling back to an older
  publish.
- **Why 09:00:** an assumed decision time, configurable in the app and via `WIND_CUTOFF`. The
  result is not sensitive to it: MAE is 2,016 MW at 07:00 (04:30 publish), 2,039 MW at 09:00
  (07:30 publish) and 2,013 MW at 09:50 (09:30 publish). Cutoffs between 22:30 and 02:30 are not
  supported, because the 22:30 publish only reaches about 46 hours ahead and does not cover the
  whole next delivery day.
- **Time zone:** everything is UTC. UK local time equals UTC in January, so there is no daylight
  saving issue in this data.
- **Error sign:** error = forecast − actual, in MW. Positive means over-forecast (a shortfall for the
  buyer). Each row is one hour, so summing positive errors gives shortfall in MWh.
- **No MAPE:** actual wind output can be close to zero, which makes percentage errors explode. MAE,
  RMSE, bias and percentiles are reported instead.

## Bias correction

Each delivery day D is corrected using only delivery days D-8..D-2 (decision-time forecasts against
actuals). Those days are fully observed before the D-1 cutoff. D-1 and D are never used. Two methods:

- **additive:** forecast − mean error over the window
- **ratio:** forecast × sum(actual) / sum(forecast) over the window

**Disclosure:** the default method shown in the app (`ratio`) was picked after comparing both
methods on the same January 2026 data the app reports on. On 2 Jan – 1 Feb at a 09:00 cutoff, MAE
was 2,039 MW raw, 1,615 MW additive and 1,437 MW ratio. The window length (7 days) was fixed in
advance and not tuned. Both methods beat the raw forecast on 21 of 31 days.

## Limitations

- One month of data only. January is windy; other seasons may behave differently.
- The correction method was chosen on the same data it is evaluated on, so its gain is likely
  optimistic.
- National level only. No regional or per-farm view.
- Static data snapshot. The app reads committed CSV files and does not fetch new data.

## Repository layout

```
api/index.py                Vercel function entry; imports the FastAPI app
backend/app/                FastAPI app: forecast selection, correction, metrics
backend/scripts/            fetch_raw.py (Elexon -> data/raw), build_dataset.py (-> data/processed)
backend/tests/              pytest suite
backend/Dockerfile          API image (Python 3.12, uvicorn)
data/processed/             hourly actuals and forecasts as CSV (committed)
frontend/                   Vite + React + TypeScript
frontend/Dockerfile         builds the frontend and serves it with nginx
frontend/nginx.conf         static files, SPA fallback, /api/ proxy to the API container
docker-compose.yml          runs both containers locally
.github/workflows/ci.yml    tests, lint, build and a Docker smoke test on every push and PR
scripts/                    explore_data.py, the original data exploration
vercel.json                 Vercel build and routing
```

## API

All routes are `GET`. Dates are `YYYY-MM-DD` within 2026-01-02..2026-02-01. `cutoff` is `HH:MM` UTC
(default `09:00`).

| Route | Query parameters | Returns |
|---|---|---|
| `/api/health` | none | `{"status":"ok"}` |
| `/api/meta` | none | delivery range, publish times, irregular publishes, correction methods, notes |
| `/api/day` | `date` (required), `cutoff`, `method` (`additive` or `ratio`, default `ratio`) | 24 hourly rows with forecast, corrected forecast, actual and error; day summary; correction used; other publishes for that day |
| `/api/accuracy` | `cutoff`, `start`, `end` (default: full range) | summary stats, corrected summaries, energy gaps, by hour of day, by lead time, daily stats |
| `/api/timeseries` | `cutoff`, `start`, `end` | hourly decision-time forecast and actual |

Interactive docs are at `/docs` on the API server itself, e.g. <http://localhost:8000/docs> when
running without Docker. They are not routed through Vercel or the Docker nginx, which only forward
`/api/`.

## Run it

### Option 1: Docker

Needs Docker with Compose (Docker Desktop on Windows).

```bash
docker compose up --build
```

Open <http://localhost:8080>. nginx serves the frontend and forwards `/api/` to the API container.
Stop with `docker compose down`.

### Option 2: without Docker (Windows)

Needs Python 3.12 and Node 22. In PowerShell, from the repo root:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt

# API on http://localhost:8000
.venv\Scripts\python -m uvicorn api.index:app --reload --port 8000
```

In a second terminal:

```powershell
# Frontend on http://localhost:5173 (proxies /api to :8000)
cd frontend
npm ci
npm run dev
```

On macOS/Linux use `.venv/bin/python` instead of `.venv\Scripts\python`.

### Tests

```powershell
cd backend
..\.venv\Scripts\python -m pytest       # 74 tests

cd ..\frontend
npm run lint
npm test                                # 34 tests
npm run build
```

CI runs the same checks plus a Docker smoke test.

### Refreshing the data

From `backend/`:

```powershell
..\.venv\Scripts\python scripts\fetch_raw.py      # Elexon -> data/raw (default: delivery 2026-01-02..2026-02-01)
..\.venv\Scripts\python scripts\build_dataset.py  # data/raw -> data/processed
```

`fetch_raw.py` takes `--start` and `--end` (delivery dates) and also fetches the extra days the
correction window needs. Commit `data/processed/` after refreshing. The delivery range in
`backend/app/main.py` is fixed to January 2026.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `WIND_CUTOFF` | `09:00` | default decision cutoff on D-1, `HH:MM` UTC |
| `WIND_DATA_DIR` | `<repo>/data` | folder holding `processed/` (and `raw/` for the scripts) |

`requirements.txt` holds only the runtime dependencies (FastAPI, NumPy, pandas) that Vercel and the
API image install. `requirements-dev.txt` adds pytest, httpx, requests and uvicorn. The pinned
`numpy==2.0.2` and `pandas==2.2.2` do not install on Python 3.13+, so use Python 3.12
(`.python-version`).

## Deployment

One Vercel project serves both parts: the Vite build from `frontend/dist` as static files, and
`api/index.py` as a Python function that loads the FastAPI app with `data/processed/*.csv` bundled.
`vercel.json` routes `/api/*` to the function. Every push to `main` deploys to production. Full
steps and troubleshooting: [DEPLOY.md](DEPLOY.md).

## Use of AI tools

- **Claude Code:** wrote most of the code from my step-by-step instructions (data pipeline, API,
  React UI, tests, Docker, CI) and checked the numbers in this README against the app.
- **Claude (chat):** used to plan each step, write the instructions I gave Claude Code, and review
  its output.

What I did myself: chose the analysis rules (decision-time forecast at the 09:00 D-1 cutoff, UTC
delivery day, D-8..D-2 leakage-safe training window, metrics, and disclosing the correction
choice), checked results against the raw data, and reviewed every change before committing.
