# Deploying to Vercel

One Vercel project serves both the frontend and the API:

- `frontend/` is built with Vite and served as static files from `frontend/dist`.
- `api/index.py` is a Python Vercel Function that loads the FastAPI app from `backend/app`.
- `vercel.json` sends every `/api/*` request to that function. Everything else is the static site.
- `data/processed/*.csv` are bundled with the function. The app finds them through paths relative
  to its own source files, so the working directory does not matter.

Almost all settings come from `vercel.json`, which overrides the dashboard. The steps below mostly
confirm that the dashboard is not set up to fight it.

## Before you start

- Everything is pushed to `main` on GitHub (`manojkumargudge/qx7wnd`), including `vercel.json`,
  `api/`, `requirements.txt`, `.python-version`, `frontend/package-lock.json` and
  `data/processed/*.csv`.
- You have a Vercel account linked to your GitHub account.

## Import the project

1. Go to <https://vercel.com/new>.
2. Under **Import Git Repository**, find `qx7wnd` and click **Import**. If it is not listed, click
   **Adjust GitHub App Permissions** and give Vercel access to the repo.
3. On the **Configure Project** screen:

   | Setting | Value |
   |---|---|
   | Project Name | anything, e.g. `wind-forecast-accuracy` |
   | Framework Preset | **Vite** (also forced by `vercel.json`) |
   | Root Directory | **`./`**, the repository root. Do **not** pick `frontend`, or the `api/` function and the data will not be deployed. |
   | Build Command | leave the default. `vercel.json` sets `npm run build --prefix frontend` |
   | Output Directory | leave the default. `vercel.json` sets `frontend/dist` |
   | Install Command | leave the default. `vercel.json` sets `npm ci --prefix frontend` |
   | Environment Variables | none needed |

   If you do turn on any **Override** toggles, use exactly the values in `vercel.json`.

4. Click **Deploy**.

## What should happen in the build log

- `npm ci --prefix frontend` and then `npm run build --prefix frontend` finish, ending with
  `dist/index.html` and `dist/assets/...`.
- A Python function is built for `api/index.py`. Vercel installs `fastapi`, `numpy` and `pandas`
  from the root `requirements.txt`, using Python 3.12 from `.python-version`.

## Check the deployment

Open the deployment URL, then:

1. `https://<your-domain>/api/health` returns `{"status":"ok"}`.
2. `https://<your-domain>/api/meta` returns JSON with `"delivery_start":"2026-01-02"`.
3. `https://<your-domain>/` shows the page, with API health "ok" and the metadata list filled in.
4. `https://<your-domain>/api/day?date=2026-01-15` returns 24 rows with
   `"publish_time":"2026-01-14T07:30:00Z"`.

## If something goes wrong

| Symptom | Likely cause and fix |
|---|---|
| Page loads but shows `404` for health/meta | The rewrite did not apply, or Root Directory is not `./`. Check **Settings → General → Root Directory**. |
| `/api/*` returns `500` and the function log says `FileNotFoundError ... data/processed` | The CSVs were not bundled. Check they are committed, and that `includeFiles` in `vercel.json` is unchanged. |
| `/api/*` returns `500` with `ModuleNotFoundError: app` | `backend/app` was not bundled. Same check as above. |
| `/api/*` returns `500` with `ModuleNotFoundError: fastapi` or `pandas` | The root `requirements.txt` is missing or was renamed. |
| Every route, including `/`, goes to FastAPI | The FastAPI preset was detected instead of Vite. Set **Framework Preset** to **Vite**, or check that `"framework": "vite"` is still in `vercel.json`. |
| Build fails at `npm ci` | `frontend/package-lock.json` is missing or out of date. Run `npm install` in `frontend/` and commit the lockfile. |

Function logs are in the project dashboard under **Logs** (filter by `/api`).

## After the first deploy

Every push to `main` creates a production deployment. Pushes to other branches and pull requests get
preview URLs. The data is static, read from the committed CSVs. To refresh it, run the fetch and build
scripts locally (see `README.md`), commit `data/processed/`, and push.
