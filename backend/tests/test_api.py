"""API tests against the real processed CSVs in data/processed/ (no network)."""

from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import config, main, metrics
from app.main import Dataset, app, corrected_errors, decision_errors, get_dataset, in_range


def rounded(summary: dict) -> dict:
    """A metrics.summary() dict as the API returns it: MW values to 0.1."""
    return {k: v if k == "n" else round(v, 1) for k, v in summary.items()}


def mw_values(obj, key=""):
    """Yield every value in a JSON body whose key names an MW quantity."""
    mw_keys = {"mae", "rmse", "bias", "p10", "p50", "p90", "forecast_mw", "actual_mw",
               "error_mw", "corrected_forecast_mw", "corrected_mae", "corrected_bias"}
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from mw_values(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from mw_values(v, key)
    elif key in mw_keys and obj is not None:
        yield obj


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_meta(client):
    body = client.get("/api/meta").json()
    assert body["delivery_start"] == "2026-01-02"
    assert body["delivery_end"] == "2026-02-01"
    assert body["default_cutoff"] == "09:00"
    assert "07:30" in body["publish_times_of_day"]
    assert "12:25" not in body["publish_times_of_day"]
    assert "UTC" in body["timezone"]
    assert body["data_source"]


def test_day_default_cutoff_uses_0730_publish(client):
    r = client.get("/api/day", params={"date": "2026-01-15"})
    assert r.status_code == 200
    body = r.json()
    assert body["publish_time"] == "2026-01-14T07:30:00Z"
    assert body["decision_time"] == "2026-01-14T09:00:00Z"
    assert len(body["rows"]) == 24
    assert [row["hour"] for row in body["rows"]] == list(range(24))
    first = body["rows"][0]
    assert set(first) == {"hour", "start_time", "forecast_mw", "corrected_forecast_mw",
                          "actual_mw", "error_mw"}
    assert first["error_mw"] == pytest.approx(first["forecast_mw"] - first["actual_mw"])
    assert set(body["summary"]) == {"mae", "bias", "corrected_mae", "corrected_bias"}


def test_day_cutoff_0950_uses_0930_publish(client):
    body = client.get("/api/day", params={"date": "2026-01-15", "cutoff": "09:50"}).json()
    assert body["publish_time"] == "2026-01-14T09:30:00Z"


def test_day_other_publishes(client):
    body = client.get("/api/day", params={"date": "2026-01-15"}).json()
    others = body["other_publishes"]
    times = [p["publish_time"] for p in others]
    assert body["publish_time"] not in times
    assert times == sorted(times)
    assert any(p["after_decision"] for p in others)
    assert any(not p["after_decision"] for p in others)
    assert all(pt["lead_hours"] > 0 for p in others for pt in p["rows"])
    # The irregular 12:25 publish on 2026-01-15 forecasts part of that same day.
    assert "2026-01-15T12:25:00Z" in times


def test_accuracy_shape(client):
    r = client.get("/api/accuracy")
    assert r.status_code == 200
    body = r.json()
    assert (body["start"], body["end"], body["cutoff"]) == ("2026-01-02", "2026-02-01", "09:00")
    assert set(body["summary"]) == {"n", "mae", "rmse", "bias", "p10", "p50", "p90"}
    assert len(body["by_hour_of_day"]) == 24
    assert [b["lead_bucket"] for b in body["by_lead_bucket"]] == \
        ["0-6", "6-12", "12-18", "18-24", "24-30", "30-36", "36-42", "42-48"]
    assert len(body["daily"]) == 31


def test_accuracy_summary_matches_metrics(client):
    body = client.get("/api/accuracy", params={"cutoff": "09:50"}).json()
    expected = metrics.summary(decision_errors("09:50"))
    assert body["summary"] == rounded(expected)


def test_accuracy_sub_range(client):
    body = client.get("/api/accuracy",
                      params={"start": "2026-01-10", "end": "2026-01-12"}).json()
    expected = metrics.summary(in_range(decision_errors("09:00"),
                                        date(2026, 1, 10), date(2026, 1, 12)))
    assert body["summary"]["n"] == 72
    assert body["summary"] == rounded(expected)
    assert len(body["daily"]) == 3


def test_meta_lists_irregular_publishes_separately(client):
    body = client.get("/api/meta").json()
    assert body["irregular_publishes"] == [{"time": "12:25", "dates": ["2026-01-15"]}]
    assert body["publish_times_of_day"] == ["02:30", "04:30", "07:30", "09:30", "11:30",
                                            "15:30", "18:30", "22:30"]


@pytest.mark.parametrize("path,params", [
    ("/api/day", {"date": "2026-01-15"}),
    ("/api/day", {"date": "2026-01-15", "method": "additive"}),
    ("/api/accuracy", {}),
    ("/api/timeseries", {"start": "2026-01-02", "end": "2026-01-05"}),
])
def test_mw_values_rounded_to_one_decimal(client, path, params):
    values = list(mw_values(client.get(path, params=params).json()))
    assert len(values) > 20
    assert all(v == round(v, 1) for v in values)


def test_day_summary_includes_corrected_metrics(client):
    body = client.get("/api/day", params={"date": "2026-01-15", "method": "ratio"}).json()
    errors = [r["corrected_forecast_mw"] - r["actual_mw"] for r in body["rows"]]
    s = body["summary"]
    assert s["corrected_mae"] == pytest.approx(sum(abs(e) for e in errors) / 24, abs=0.1)
    assert s["corrected_bias"] == pytest.approx(sum(errors) / 24, abs=0.1)
    # Raw and corrected differ on this day: ratio pulls a +1042 MW bias below zero.
    assert s["bias"] > 0 > s["corrected_bias"]


def test_meta_correction_fields(client):
    body = client.get("/api/meta").json()
    assert body["correction_methods"] == ["additive", "ratio"]
    assert body["default_correction_method"] == "ratio"
    assert "D-8..D-2" in body["correction_note"]


def test_hardcoded_default_still_has_lower_january_mae():
    # Guards the claim in config.py/README: ratio beat additive on the full range.
    mae = {m: metrics.summary(corrected_errors("09:00", m))["mae"] for m in ("additive", "ratio")}
    assert config.DEFAULT_CORRECTION_METHOD == "ratio"
    assert mae["ratio"] < mae["additive"]


def test_day_correction_default_method(client):
    body = client.get("/api/day", params={"date": "2026-01-15"}).json()
    corr = body["correction"]
    assert corr["method"] == "ratio"
    assert (corr["window_start"], corr["window_end"]) == ("2026-01-07", "2026-01-13")
    assert all("corrected_forecast_mw" in row for row in body["rows"])


@pytest.mark.parametrize("method", ["additive", "ratio"])
def test_day_correction_is_applied_per_row(client, method):
    body = client.get("/api/day", params={"date": "2026-01-15", "method": method}).json()
    value = body["correction"]["value"]
    assert body["correction"]["method"] == method
    for row in body["rows"]:
        expected = row["forecast_mw"] - value if method == "additive" else row["forecast_mw"] * value
        # value is rounded to 4 dp in the response, so allow a little slack.
        assert row["corrected_forecast_mw"] == pytest.approx(expected, abs=1.0)


def test_day_correction_matches_range_computation(client):
    body = client.get("/api/day", params={"date": "2026-01-20", "method": "ratio"}).json()
    ranged = corrected_errors("09:00", "ratio")
    ranged = ranged[ranged["delivery_date"] == date(2026, 1, 20)]
    assert [r["corrected_forecast_mw"] for r in body["rows"]] == \
        [round(v, 1) for v in ranged["corrected_mw"]]


def test_accuracy_corrected_summaries(client):
    body = client.get("/api/accuracy", params={"start": "2026-01-10", "end": "2026-01-20"}).json()
    for m in ("additive", "ratio"):
        expected = metrics.summary(in_range(corrected_errors("09:00", m),
                                            date(2026, 1, 10), date(2026, 1, 20)))
        assert body["corrected"][m] == rounded(expected)
        assert body["corrected"][m]["n"] == body["summary"]["n"] == 11 * 24


def test_timeseries(client):
    r = client.get("/api/timeseries", params={"start": "2026-01-02", "end": "2026-01-03"})
    assert r.status_code == 200
    points = r.json()["points"]
    assert len(points) == 48
    assert set(points[0]) == {"start_time", "forecast_mw", "actual_mw"}
    assert points[0]["start_time"] == "2026-01-02T00:00:00Z"


@pytest.mark.parametrize("path,params,needle", [
    ("/api/day", {"date": "2026-13-01"}, "date"),
    ("/api/day", {"date": "not-a-date"}, "date"),
    ("/api/day", {}, "date"),
    ("/api/day", {"date": "2026-01-01"}, "outside the available delivery range"),
    ("/api/day", {"date": "2026-02-02"}, "outside the available delivery range"),
    ("/api/day", {"date": "2026-01-15", "cutoff": "9:00"}, "HH:MM"),
    ("/api/day", {"date": "2026-01-15", "cutoff": "25:00"}, "HH:MM"),
    ("/api/day", {"date": "2026-01-15", "method": "median"}, "method"),
    ("/api/accuracy", {"cutoff": "noon"}, "HH:MM"),
    ("/api/accuracy", {"start": "2025-12-01"}, "outside the available delivery range"),
    ("/api/accuracy", {"start": "2026-01-20", "end": "2026-01-10"}, "must be on or before"),
    ("/api/timeseries", {"end": "2026-03-01"}, "outside the available delivery range"),
])
def test_bad_inputs_return_422_with_message(client, path, params, needle):
    r = client.get(path, params=params)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, str)
    assert needle in detail


def test_no_decision_forecast_maps_to_422(client, monkeypatch):
    # Drop the last delivery hour from the publish that would be chosen.
    ds = get_dataset()
    fc = ds.forecasts
    gap = (fc["publish_time"] == pd.Timestamp("2026-01-14 07:30", tz="UTC")) & \
          (fc["start_time"] == pd.Timestamp("2026-01-15 23:00", tz="UTC"))
    monkeypatch.setattr(main, "get_dataset", lambda: Dataset(ds.actuals, fc[~gap]))
    r = client.get("/api/day", params={"date": "2026-01-15"})
    assert r.status_code == 422
    assert "does not cover 1 hour(s)" in r.json()["detail"]


def test_cors_allows_vite_dev_origin(client):
    r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_accuracy_daily_includes_corrected_mae(client):
    daily = client.get("/api/accuracy").json()["daily"]
    assert len(daily) == 31
    assert set(daily[0]) == {"date", "mae", "bias", "additive_mae", "ratio_mae"}
    for m in ("additive", "ratio"):
        ce = corrected_errors("09:00", m)
        expected = ce["error"].abs().groupby(ce["delivery_date"]).mean()
        assert [d[f"{m}_mae"] for d in daily] == [round(v, 1) for v in expected]
        # The documented January result: each method beats raw on 21 of 31 days.
        assert sum(d[f"{m}_mae"] < d["mae"] for d in daily) == 21


def test_accuracy_daily_corrected_mae_changes_with_cutoff(client):
    at_9 = client.get("/api/accuracy", params={"cutoff": "09:00"}).json()["daily"]
    at_11 = client.get("/api/accuracy", params={"cutoff": "11:00"}).json()["daily"]
    assert [d["ratio_mae"] for d in at_9] != [d["ratio_mae"] for d in at_11]
