"""Forecast error metrics. Error = forecast - actual, in MW.

MAPE is deliberately left out: actual wind output can be close to zero, which
makes percentage errors blow up.
"""

import numpy as np
import pandas as pd

LEAD_BUCKET_HOURS = 6
MAX_LEAD_HOURS = 72


def join_actuals(forecasts: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    """Inner-join forecasts to actuals on start_time and add an error column."""
    df = forecasts.merge(actuals, on="start_time", how="inner")
    df["error"] = df["forecast_mw"] - df["actual_mw"]
    return df


def summary(df: pd.DataFrame) -> dict:
    """MAE, RMSE, bias and error percentiles for rows with an error column."""
    e = df["error"]
    return {
        "n": int(len(e)),
        "mae": float(e.abs().mean()),
        "rmse": float(np.sqrt((e ** 2).mean())),
        "bias": float(e.mean()),
        "p10": float(e.quantile(0.10)),
        "p50": float(e.quantile(0.50)),
        "p90": float(e.quantile(0.90)),
    }


def energy_gaps(df: pd.DataFrame) -> dict:
    """Energy in MWh from hourly errors (each row is one hour, so MW x 1 h = MWh).

    shortfall_mwh: forecast above actual, i.e. wind planned but not delivered.
    surplus_mwh:   forecast below actual, i.e. extra wind; reported as a positive number.
    """
    e = df["error"]
    return {
        "shortfall_mwh": float(e.clip(lower=0).sum()),
        "surplus_mwh": float(-e.clip(upper=0).sum()) + 0.0,  # + 0.0 turns -0.0 into 0.0
    }


def by_lead_bucket(df: pd.DataFrame) -> pd.DataFrame:
    """Bias and MAE per 6-hour lead bucket [0,6), [6,12), ... Pass all publishes."""
    edges = list(range(0, MAX_LEAD_HOURS + 1, LEAD_BUCKET_HOURS))
    labels = [f"{a}-{b}" for a, b in zip(edges[:-1], edges[1:])]
    bucket = pd.cut(df["lead_hours"], bins=edges, labels=labels, right=False)
    out = (df.assign(abs_error=df["error"].abs())
           .groupby(bucket, observed=True)
           .agg(n=("error", "size"), bias=("error", "mean"), mae=("abs_error", "mean")))
    out.index.name = "lead_bucket"
    return out.reset_index()


def by_hour_of_day(df: pd.DataFrame) -> pd.DataFrame:
    """MAE and bias per delivery hour (UTC)."""
    out = (df.assign(abs_error=df["error"].abs(), hour=df["start_time"].dt.hour)
           .groupby("hour")
           .agg(n=("error", "size"), mae=("abs_error", "mean"), bias=("error", "mean")))
    return out.reset_index()
