"""Bias-correct decision-time forecasts using only information available at decision time.

For delivery day D the decision is made on D-1 at the cutoff. At that moment the
latest fully observed day is D-2, so the training window is delivery days
D-8..D-2 (7 days): their decision-time forecasts and their actuals. D-1 and later
are never used.

Methods:
  additive: corrected = forecast - mean(forecast - actual) over the window
  ratio:    corrected = forecast * sum(actual) / sum(forecast) over the window
"""

from datetime import date, timedelta

import pandas as pd

from app import config, metrics
from app.forecast import HOURS_PER_DAY, NoDecisionForecastError, decision_forecast

WINDOW_DAYS = 7
WINDOW_END_LAG_DAYS = 2  # last training day is D-2
METHODS = ("additive", "ratio")


class InsufficientHistoryError(ValueError):
    """The training window lacks complete forecast/actual data."""


def training_window(delivery_date) -> tuple[date, date]:
    """First and last delivery day of the training window for D: (D-8, D-2)."""
    d = pd.Timestamp(delivery_date).date()
    last = d - timedelta(days=WINDOW_END_LAG_DAYS)
    return last - timedelta(days=WINDOW_DAYS - 1), last


def decision_history(forecasts: pd.DataFrame, actuals: pd.DataFrame, start, end,
                     cutoff: str = config.CUTOFF) -> pd.DataFrame:
    """Decision-time forecasts joined to actuals for delivery days start..end.

    Days without a usable decision forecast are skipped rather than raising, so a
    gap shows up later as an incomplete training window.
    """
    frames = []
    for d in pd.date_range(pd.Timestamp(start).date(), pd.Timestamp(end).date(), freq="D"):
        try:
            frames.append(decision_forecast(forecasts, d, cutoff).assign(delivery_date=d.date()))
        except NoDecisionForecastError:
            continue
    if not frames:
        return pd.DataFrame(columns=["publish_time", "start_time", "forecast_mw", "lead_hours",
                                     "delivery_date", "actual_mw", "error"])
    return metrics.join_actuals(pd.concat(frames, ignore_index=True), actuals)


def correction_value(history: pd.DataFrame, delivery_date, method: str) -> float:
    """The additive offset (MW) or ratio factor for D, from history rows in D-8..D-2 only."""
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}, got {method!r}")
    first, last = training_window(delivery_date)
    window = history[(history["delivery_date"] >= first) & (history["delivery_date"] <= last)]
    window = window.dropna(subset=["forecast_mw", "actual_mw"])

    hours = window.groupby("delivery_date").size()
    full_days = hours[hours == HOURS_PER_DAY].index
    if len(full_days) < WINDOW_DAYS:
        missing = sorted(set(pd.date_range(first, last).date) - set(full_days))
        raise InsufficientHistoryError(
            f"Training window {first}..{last} for {pd.Timestamp(delivery_date).date()} has "
            f"{len(full_days)} of {WINDOW_DAYS} complete days; incomplete: "
            + ", ".join(str(d) for d in missing))

    if method == "additive":
        return float(window["error"].mean())
    total_forecast = window["forecast_mw"].sum()
    if total_forecast <= 0:
        raise InsufficientHistoryError(f"Training window {first}..{last} has zero total forecast")
    return float(window["actual_mw"].sum() / total_forecast)


def apply_correction(forecast_mw: pd.Series, value: float, method: str) -> pd.Series:
    if method == "additive":
        return forecast_mw - value
    return forecast_mw * value


def corrected_forecasts_for_range(forecasts: pd.DataFrame, actuals: pd.DataFrame, start, end,
                                  cutoff: str = config.CUTOFF,
                                  method: str = "additive") -> pd.DataFrame:
    """Decision-time forecasts for start..end with correction and corrected_mw columns.

    Raises InsufficientHistoryError if any day's training window is incomplete,
    and NoDecisionForecastError if a delivery day itself has no decision forecast.
    """
    start, end = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    history = decision_history(forecasts, actuals, training_window(start)[0], end, cutoff)
    frames = []
    for d in pd.date_range(start, end, freq="D"):
        d = d.date()
        value = correction_value(history, d, method)
        rows = decision_forecast(forecasts, d, cutoff).assign(delivery_date=d)
        rows["correction"] = value
        rows["corrected_mw"] = apply_correction(rows["forecast_mw"], value, method)
        frames.append(rows)
    return pd.concat(frames, ignore_index=True)
