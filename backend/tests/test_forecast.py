import pandas as pd
import pytest

from app.forecast import NoDecisionForecastError, decision_forecast, decision_forecasts_for_range

DELIVERY = "2026-01-16"


def publish(publish_time, value, start="2026-01-15 13:00", hours=60):
    """One publish: hourly rows from start, every forecast_mw equal to value."""
    pt = pd.Timestamp(publish_time, tz="UTC")
    starts = pd.date_range(pd.Timestamp(start, tz="UTC"), periods=hours, freq="h")
    return pd.DataFrame({
        "publish_time": pt,
        "start_time": starts,
        "forecast_mw": float(value),
        "lead_hours": (starts - pt).total_seconds() / 3600,
    })


@pytest.fixture
def forecasts():
    # 11:30 replaced by an irregular 12:25 publish, as seen on 2026-01-15.
    return pd.concat([
        publish("2026-01-15 04:30", 430),
        publish("2026-01-15 07:30", 730),
        publish("2026-01-15 09:30", 930),
        publish("2026-01-15 12:25", 1225),
        publish("2026-01-15 15:30", 1530),
    ], ignore_index=True)


def test_picks_latest_publish_before_cutoff_and_ignores_later(forecasts):
    rows = decision_forecast(forecasts, DELIVERY, cutoff="09:00")
    assert rows["publish_time"].unique().tolist() == [pd.Timestamp("2026-01-15 07:30", tz="UTC")]
    assert (rows["forecast_mw"] == 730).all()


def test_returns_exactly_the_24_delivery_hours(forecasts):
    rows = decision_forecast(forecasts, DELIVERY, cutoff="09:00")
    expected = pd.date_range(pd.Timestamp(DELIVERY, tz="UTC"), periods=24, freq="h")
    assert rows["start_time"].tolist() == expected.tolist()


def test_cutoff_0950_picks_0930_publish(forecasts):
    rows = decision_forecast(forecasts, DELIVERY, cutoff="09:50")
    assert (rows["forecast_mw"] == 930).all()


def test_irregular_publish_is_picked_when_it_is_latest(forecasts):
    rows = decision_forecast(forecasts, DELIVERY, cutoff="13:00")
    assert (rows["forecast_mw"] == 1225).all()


def test_publish_exactly_at_cutoff_is_eligible(forecasts):
    rows = decision_forecast(forecasts, DELIVERY, cutoff="09:30")
    assert (rows["forecast_mw"] == 930).all()


def test_no_publish_before_cutoff_raises(forecasts):
    with pytest.raises(NoDecisionForecastError, match="No forecast published"):
        decision_forecast(forecasts, DELIVERY, cutoff="03:00")


def test_incomplete_latest_publish_raises():
    short = publish("2026-01-15 07:30", 730, hours=20)  # ends 2026-01-16 08:00
    with pytest.raises(NoDecisionForecastError, match="does not cover 15 hour"):
        decision_forecast(short, DELIVERY, cutoff="09:00")


def test_bad_cutoff_format_raises(forecasts):
    with pytest.raises(ValueError, match="HH:MM"):
        decision_forecast(forecasts, DELIVERY, cutoff="9am")


def test_range_returns_24_rows_per_day():
    fc = pd.concat([
        publish("2026-01-14 07:30", 1, start="2026-01-14 08:00", hours=72),
        publish("2026-01-15 07:30", 2, start="2026-01-15 08:00", hours=72),
    ], ignore_index=True)
    out = decision_forecasts_for_range(fc, "2026-01-15", "2026-01-16", cutoff="09:00")
    assert len(out) == 48
    assert out.groupby("delivery_date")["forecast_mw"].first().tolist() == [1.0, 2.0]
