"""Settings, overridable through environment variables."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Forecast decision cutoff on the day before delivery, "HH:MM" in UTC.
CUTOFF = os.environ.get("WIND_CUTOFF", "09:00")

# Chosen after comparing additive vs ratio on January 2026 (ratio had lower MAE).
# Fixed here rather than re-selected at runtime; the choice is disclosed in README.md.
DEFAULT_CORRECTION_METHOD = "ratio"

DATA_DIR = Path(os.environ.get("WIND_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
ACTUALS_PATH = PROCESSED_DIR / "actuals.csv"
FORECASTS_PATH = PROCESSED_DIR / "forecasts.csv"
