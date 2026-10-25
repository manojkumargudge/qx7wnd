from datetime import date, timedelta

import pandas as pd
import pytest

from app.correction import InsufficientHistoryError, corrected_forecasts_for_range, \
    training_window

D = date(2026, 1, 15)
HISTORY_START = date(2026, 1, 5)  # a few days before the D-8 window start


def day_hours(d):
    return pd.date_range(pd.Timestamp(d, tz="UTC"), periods=24, freq="h")


def make_forecasts(value_for_day, first=HISTORY_START, last=D):
    """One publish per delivery day at 07:30 the day before, covering exactly that day."""
    frames = []
    d = first
    while d <= last:
        pt = pd.Timestamp(d - timedelta(days=1), tz="UTC") + pd.Timedelta(hours=7, minutes=30)
        starts = day_hours(d)
        frames.append(pd.DataFrame({
            "publish_time": pt, "start_time": starts, "forecast_mw": float(value_for_day(d)),
            "lead_hours": (starts - pt).total_seconds() / 3600,
        }))
        d += timedelta(days=1)
    return pd.concat(frames, ignore_index=True)


def make_actuals(value_for_day, first=HISTORY_START, last=D):
    days = pd.date_range(first, last, freq="D")
    starts = pd.DatetimeIndex([t for d in days for t in day_hours(d.date())])
    return pd.DataFrame({"start_time": starts,
                         "actual_mw": [float(value_for_day(t.date())) for t in starts]})


def correction_for_d(forecasts, actuals, method):
    out = corrected_forecasts_for_range(forecasts, actuals, D, D, "09:00", method)
    assert len(out) == 24
    return out


@pytest.fixture
def forecasts():
    # 120 MW on every training day, 150 MW on D itself.
    return make_forecasts(lambda d: 150 if d == D else 120)


@pytest.fixture
def actuals():
    return make_actuals(lambda d: 100)


def test_training_window_is_d_minus_8_to_d_minus_2():
    assert training_window(D) == (date(2026, 1, 7), date(2026, 1, 13))


@pytest.mark.parametrize("method", ["additive", "ratio"])
def test_no_leakage_from_d_minus_1_or_d(forecasts, actuals, method):
    base = correction_for_d(forecasts, actuals, method)
    days = actuals["start_time"].dt.date
    tampered = actuals.copy()
    tampered.loc[days >= D - timedelta(days=1), "actual_mw"] = 99999.0
    after = correction_for_d(forecasts, tampered, method)
    assert after["correction"].iloc[0] == base["correction"].iloc[0]
    assert after["corrected_mw"].tolist() == base["corrected_mw"].tolist()


@pytest.mark.parametrize("method", ["additive", "ratio"])
def test_actuals_on_d_minus_2_do_change_correction(forecasts, actuals, method):
    base = correction_for_d(forecasts, actuals, method)
    tampered = actuals.copy()
    tampered.loc[tampered["start_time"].dt.date == D - timedelta(days=2), "actual_mw"] = 50.0
    after = correction_for_d(forecasts, tampered, method)
    assert after["correction"].iloc[0] != base["correction"].iloc[0]


def test_additive_known_example(forecasts, actuals):
    # Window error = 120 - 100 = 20 every hour, so D's 150 becomes 130.
    out = correction_for_d(forecasts, actuals, "additive")
    assert out["correction"].iloc[0] == pytest.approx(20.0)
    assert out["corrected_mw"].tolist() == pytest.approx([130.0] * 24)


def test_ratio_known_example(forecasts, actuals):
    # Window factor = 100 / 120, so D's 150 becomes 125.
    out = correction_for_d(forecasts, actuals, "ratio")
    assert out["correction"].iloc[0] == pytest.approx(100 / 120)
    assert out["corrected_mw"].tolist() == pytest.approx([125.0] * 24)


def test_additive_averages_over_all_window_hours():
    # Errors of +30 on 4 window days and +10 on 3 days -> mean 150/7.
    window_first = training_window(D)[0]
    fc = make_forecasts(lambda d: 130 if (d - window_first).days % 2 == 0 else 110)
    out = correction_for_d(fc, make_actuals(lambda d: 100), "additive")
    assert out["correction"].iloc[0] == pytest.approx(150 / 7)


def test_missing_window_actuals_raise(forecasts, actuals):
    gap = actuals["start_time"] == pd.Timestamp("2026-01-10 05:00", tz="UTC")
    with pytest.raises(InsufficientHistoryError, match="6 of 7 complete days; incomplete: 2026-01-10"):
        correction_for_d(forecasts, actuals[~gap], "additive")


def test_missing_window_forecast_publish_raises(forecasts, actuals):
    # Remove the publish for delivery day 2026-01-07 (made 01-06 07:30); the latest
    # publish before that cutoff is then 01-05 07:30, which does not cover 01-07.
    gone = forecasts["publish_time"] == pd.Timestamp("2026-01-06 07:30", tz="UTC")
    with pytest.raises(InsufficientHistoryError, match="incomplete: 2026-01-07"):
        correction_for_d(forecasts[~gone], actuals, "ratio")


def test_history_starting_too_late_raises():
    fc = make_forecasts(lambda d: 120, first=date(2026, 1, 10))
    act = make_actuals(lambda d: 100, first=date(2026, 1, 10))
    with pytest.raises(InsufficientHistoryError, match="4 of 7"):
        correction_for_d(fc, act, "additive")


def test_unknown_method_raises(forecasts, actuals):
    with pytest.raises(ValueError, match="method must be one of"):
        corrected_forecasts_for_range(forecasts, actuals, D, D, "09:00", "median")
