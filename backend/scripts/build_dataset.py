"""Build processed CSV files from the raw Elexon JSON in data/raw/.

Writes data/processed/actuals.csv (hourly) and
data/processed/forecasts.csv (positive lead only).

Usage (from backend/): python scripts/build_dataset.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.data import hourly_actuals, tidy_forecasts  # noqa: E402


def read_raw(prefix: str) -> pd.DataFrame:
    files = sorted(config.RAW_DIR.glob(f"{prefix}_*.json"))
    if not files:
        raise FileNotFoundError(f"No {prefix}_*.json files in {config.RAW_DIR}")
    rows = [row for f in files for row in json.loads(f.read_text())]
    return pd.DataFrame(rows)


def main():
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    actuals = hourly_actuals(read_raw("fuelhh"))
    actuals.to_csv(config.ACTUALS_PATH, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    print(f"actuals:   {len(actuals)} hourly rows "
          f"{actuals['start_time'].min()} .. {actuals['start_time'].max()} -> {config.ACTUALS_PATH}")

    raw_fc = read_raw("windfor")
    forecasts = tidy_forecasts(raw_fc)
    forecasts.to_csv(config.FORECASTS_PATH, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    print(f"forecasts: {len(forecasts)} rows from {len(raw_fc)} raw "
          f"({forecasts['publish_time'].nunique()} publishes) -> {config.FORECASTS_PATH}")


if __name__ == "__main__":
    main()
