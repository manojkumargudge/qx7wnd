import pandas as pd

from app.data import hourly_actuals, tidy_forecasts


def test_negative_and_zero_lead_rows_are_dropped():
    raw = pd.DataFrame({
        "publishTime": ["2026-01-15T07:30:00Z"] * 4,
        "startTime": ["2026-01-15T06:00:00Z", "2026-01-15T07:00:00Z",
                      "2026-01-15T08:00:00Z", "2026-01-16T07:00:00Z"],
        "generation": [100, 200, 300, 400],
    })
    out = tidy_forecasts(raw)
    assert out["forecast_mw"].tolist() == [300.0, 400.0]
    assert out["lead_hours"].tolist() == [0.5, 23.5]
    assert list(out.columns) == ["publish_time", "start_time", "forecast_mw", "lead_hours"]


def test_lead_of_exactly_zero_is_dropped():
    raw = pd.DataFrame({
        "publishTime": ["2026-01-15T08:00:00Z"],
        "startTime": ["2026-01-15T08:00:00Z"],
        "generation": [1],
    })
    assert tidy_forecasts(raw).empty


def test_half_hours_are_averaged_to_hourly():
    raw = pd.DataFrame({
        "startTime": ["2026-01-15T00:00:00Z", "2026-01-15T00:30:00Z",
                      "2026-01-15T01:00:00Z", "2026-01-15T01:30:00Z"],
        "generation": [100, 201, 50, 70],
    })
    out = hourly_actuals(raw)
    assert out["start_time"].tolist() == [pd.Timestamp("2026-01-15 00:00", tz="UTC"),
                                          pd.Timestamp("2026-01-15 01:00", tz="UTC")]
    assert out["actual_mw"].tolist() == [150.5, 60.0]
    assert list(out.columns) == ["start_time", "actual_mw"]


def test_duplicate_half_hours_keep_latest_publish():
    raw = pd.DataFrame({
        "publishTime": ["2026-01-15T00:30:00Z", "2026-01-15T01:00:00Z",
                        "2026-01-15T02:00:00Z"],
        "startTime": ["2026-01-15T00:00:00Z", "2026-01-15T00:30:00Z", "2026-01-15T00:00:00Z"],
        "generation": [100, 200, 300],
    })
    assert hourly_actuals(raw)["actual_mw"].tolist() == [250.0]


def test_hour_with_one_half_missing_is_dropped():
    raw = pd.DataFrame({
        "startTime": ["2026-01-15T00:00:00Z", "2026-01-15T00:30:00Z", "2026-01-15T01:30:00Z"],
        "generation": [100, 200, 70],
    })
    out = hourly_actuals(raw)
    assert out["actual_mw"].tolist() == [150.0]
