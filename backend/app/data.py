"""Turn raw Elexon rows into tidy frames, and load the processed CSV files.

Processed schemas (all times tz-aware UTC):
  actuals:   start_time, actual_mw                         (hourly)
  forecasts: publish_time, start_time, forecast_mw, lead_hours  (lead_hours > 0)
"""

import pandas as pd

from app import config


def hourly_actuals(fuelhh: pd.DataFrame) -> pd.DataFrame:
    """Average the two half-hours of each hour; hours missing a half are dropped."""
    df = pd.DataFrame({
        "start_time": pd.to_datetime(fuelhh["startTime"], utc=True).dt.floor("h"),
        "generation": fuelhh["generation"].astype(float),
    })
    hourly = df.groupby("start_time")["generation"].agg(["mean", "size"])
    hourly = hourly[hourly["size"] == 2]
    return (hourly["mean"].rename("actual_mw")
            .reset_index()
            .sort_values("start_time", ignore_index=True))


def tidy_forecasts(windfor: pd.DataFrame) -> pd.DataFrame:
    """Rename WINDFOR columns, add lead_hours, drop rows with lead_hours <= 0."""
    df = pd.DataFrame({
        "publish_time": pd.to_datetime(windfor["publishTime"], utc=True),
        "start_time": pd.to_datetime(windfor["startTime"], utc=True),
        "forecast_mw": windfor["generation"].astype(float),
    })
    df["lead_hours"] = (df["start_time"] - df["publish_time"]).dt.total_seconds() / 3600
    df = df[df["lead_hours"] > 0].drop_duplicates(["publish_time", "start_time"])
    return df.sort_values(["publish_time", "start_time"], ignore_index=True)


def _read_csv(path, time_cols) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in time_cols:
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


def load_actuals(path=None) -> pd.DataFrame:
    return _read_csv(path or config.ACTUALS_PATH, ["start_time"])


def load_forecasts(path=None) -> pd.DataFrame:
    return _read_csv(path or config.FORECASTS_PATH, ["publish_time", "start_time"])
