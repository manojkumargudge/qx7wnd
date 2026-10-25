# UK wind forecast accuracy

How good was National Grid's day-ahead wind forecast in January 2026, and can a
simple bias correction improve it?

- **Actuals:** Elexon BMRS `FUELHH` (fuel type WIND), half-hourly, averaged to hourly.
- **Forecasts:** Elexon BMRS `WINDFOR`, hourly, published about 8 times a day.
- **Decision-time forecast:** for delivery day D (00:00–23:00 UTC), the latest
  `WINDFOR` publish at or before the cutoff (default 09:00 UTC) on D-1.
- **Error:** forecast − actual, in MW. MAPE is not reported because actuals can be near zero.

## Bias correction

Each delivery day D is corrected using only delivery days D-8..D-2, which are
fully observed before the D-1 cutoff. D-1 and D are never used. Two methods:

- **additive:** forecast − mean error over the window
- **ratio:** forecast × sum(actual) / sum(forecast) over the window

**Disclosure:** the default method shown in the app (`ratio`) was picked after
comparing both methods on the same January 2026 data the app reports on. On
2 Jan – 1 Feb at a 09:00 cutoff, MAE was 2,039 MW raw, 1,615 MW additive and
1,437 MW ratio. The window length (7 days) was fixed in advance and not tuned.
Both methods beat the raw forecast on 21 of 31 days.

## Layout

```
api/index.py          Vercel function entry; imports the FastAPI app
backend/app/          FastAPI app, forecast selection, correction, metrics
backend/scripts/      fetch_raw.py (Elexon -> data/raw), build_dataset.py (-> data/processed)
backend/tests/        pytest suite
data/processed/       hourly actuals and forecasts as CSV (committed)
frontend/             Vite + React + TypeScript
scripts/              explore_data.py, the original data exploration
```

## Run locally

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # macOS/Linux: .venv/bin/python

# API on http://localhost:8000
.venv/Scripts/python -m uvicorn api.index:app --reload --port 8000

# Frontend on http://localhost:5173 (proxies /api to :8000)
cd frontend && npm ci && npm run dev

# Tests (from backend/)
cd backend && ../.venv/Scripts/python -m pytest
```

Refresh the data with `python backend/scripts/fetch_raw.py` and then
`python backend/scripts/build_dataset.py` (run both from `backend/`).

`requirements.txt` holds only the runtime dependencies Vercel installs.
`requirements-dev.txt` adds pytest, httpx, requests and uvicorn.

Deployment: see [DEPLOY.md](DEPLOY.md).
