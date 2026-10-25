import math

import pandas as pd
import pytest

from app.metrics import by_hour_of_day, by_lead_bucket, energy_gaps, join_actuals, summary

# Errors (forecast - actual) are +10, -10, 0, +20.
STARTS = pd.to_datetime(["2026-01-16 00:00", "2026-01-16 01:00",
                         "2026-01-16 00:00", "2026-01-16 01:00"], utc=True)


@pytest.fixture
def joined():
    forecasts = pd.DataFrame({
        "publish_time": pd.Timestamp("2026-01-15 07:30", tz="UTC"),
        "start_time": STARTS,
        "forecast_mw": [110.0, 90.0, 100.0, 120.0],
        "lead_hours": [1.0, 5.5, 6.0, 13.0],
    })
    actuals = pd.DataFrame({
        "start_time": pd.to_datetime(["2026-01-16 00:00", "2026-01-16 01:00"], utc=True),
        "actual_mw": [100.0, 100.0],
    })
    return join_actuals(forecasts, actuals)


def test_join_computes_forecast_minus_actual(joined):
    assert sorted(joined["error"].tolist()) == [-10.0, 0.0, 10.0, 20.0]


def test_join_drops_hours_without_actuals():
    fc = pd.DataFrame({"start_time": pd.to_datetime(["2026-01-16 05:00"], utc=True),
                       "forecast_mw": [1.0]})
    act = pd.DataFrame({"start_time": pd.to_datetime(["2026-01-16 06:00"], utc=True),
                        "actual_mw": [1.0]})
    assert join_actuals(fc, act).empty


def test_summary_known_values(joined):
    s = summary(joined)
    assert s["n"] == 4
    assert s["mae"] == pytest.approx(10.0)
    assert s["rmse"] == pytest.approx(math.sqrt(150.0))
    assert s["bias"] == pytest.approx(5.0)
    # Linear-interpolated percentiles of [-10, 0, 10, 20].
    assert s["p10"] == pytest.approx(-7.0)
    assert s["p50"] == pytest.approx(5.0)
    assert s["p90"] == pytest.approx(17.0)
    assert "mape" not in s


def test_by_lead_bucket(joined):
    out = by_lead_bucket(joined).set_index("lead_bucket")
    assert out.index.tolist() == ["0-6", "6-12", "12-18"]
    assert out.loc["0-6", "n"] == 2
    assert out.loc["0-6", "bias"] == pytest.approx(0.0)
    assert out.loc["0-6", "mae"] == pytest.approx(10.0)
    assert out.loc["6-12", "mae"] == pytest.approx(0.0)
    assert out.loc["12-18", "bias"] == pytest.approx(20.0)


def test_by_hour_of_day(joined):
    out = by_hour_of_day(joined).set_index("hour")
    assert out.loc[0, "mae"] == pytest.approx(5.0)    # errors +10, 0
    assert out.loc[0, "bias"] == pytest.approx(5.0)
    assert out.loc[1, "mae"] == pytest.approx(15.0)   # errors -10, +20
    assert out.loc[1, "bias"] == pytest.approx(5.0)


def test_energy_gaps_split_positive_and_negative_errors(joined):
    # Errors +10, -10, 0, +20 over four hours.
    assert energy_gaps(joined) == {"shortfall_mwh": 30.0, "surplus_mwh": 10.0}


def test_energy_gaps_empty():
    assert energy_gaps(pd.DataFrame({"error": []})) == {"shortfall_mwh": 0.0, "surplus_mwh": 0.0}


def test_energy_gaps_no_negative_zero():
    out = energy_gaps(pd.DataFrame({"error": [5.0, 3.0]}))
    assert math.copysign(1, out["surplus_mwh"]) == 1
