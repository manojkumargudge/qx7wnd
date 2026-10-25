"""Pick the forecast that was available at decision time for each delivery day.

For delivery day D (UTC hours 00:00..23:00) the decision is made on D-1 at the
cutoff time. The forecast used is the latest publish at or before that moment.
"""

from datetime import date, datetime, time, timedelta

import pandas as pd

from app import config

HOURS_PER_DAY = 24


class NoDecisionForecastError(ValueError):
    """No usable publish exists for a delivery day at the given cutoff."""


def _parse_cutoff(cutoff: str) -> time:
    try:
        return datetime.strptime(cutoff, "%H:%M").time()
    except ValueError:
        raise ValueError(f"cutoff must be 'HH:MM' (UTC), got {cutoff!r}") from None


def _as_date(d) -> date:
    return pd.Timestamp(d).date()


def cutoff_timestamp(delivery_date, cutoff: str = config.CUTOFF) -> pd.Timestamp:
    """The decision moment for a delivery day: D-1 at cutoff, UTC."""
    d = _as_date(delivery_date) - timedelta(days=1)
    return pd.Timestamp(datetime.combine(d, _parse_cutoff(cutoff)), tz="UTC")


def decision_forecast(forecasts: pd.DataFrame, delivery_date,
                      cutoff: str = config.CUTOFF) -> pd.DataFrame:
    """Return the 24 hourly rows of the latest publish <= D-1 at cutoff.

    Raises NoDecisionForecastError if there is no publish before the cutoff, or
    if the latest one does not cover every hour of the delivery day. It does not
    fall back to an older publish, since that would hide a data problem.
    """
    decided_at = cutoff_timestamp(delivery_date, cutoff)
    day_start = pd.Timestamp(_as_date(delivery_date), tz="UTC")
    hours = pd.date_range(day_start, periods=HOURS_PER_DAY, freq="h")

    eligible = forecasts.loc[forecasts["publish_time"] <= decided_at, "publish_time"]
    if eligible.empty:
        raise NoDecisionForecastError(
            f"No forecast published at or before {decided_at} for delivery day {day_start.date()}")
    publish = eligible.max()

    rows = forecasts[(forecasts["publish_time"] == publish) & forecasts["start_time"].isin(hours)]
    missing = hours.difference(rows["start_time"])
    if len(missing):
        raise NoDecisionForecastError(
            f"Publish {publish} (latest before cutoff {decided_at}) does not cover "
            f"{len(missing)} hour(s) of {day_start.date()}: "
            + ", ".join(t.strftime("%H:%M") for t in missing))
    return rows.sort_values("start_time", ignore_index=True)


def decision_forecasts_for_range(forecasts: pd.DataFrame, start, end,
                                 cutoff: str = config.CUTOFF) -> pd.DataFrame:
    """Decision-time forecasts for each delivery day from start to end inclusive."""
    days = pd.date_range(_as_date(start), _as_date(end), freq="D")
    frames = [decision_forecast(forecasts, d, cutoff).assign(delivery_date=d.date()) for d in days]
    return pd.concat(frames, ignore_index=True)
