"""Fetch raw FUELHH (wind) actuals and WINDFOR forecasts from Elexon into data/raw/.

For delivery days START..END the bias correction needs a 7-day training window
ending two days before each delivery day, so this fetches:
  actuals:   settlement dates START-11 .. END+1
  forecasts: published START-12 00:00 .. END 23:59 UTC

Existing fuelhh_*.json / windfor_*.json files in data/raw/ are replaced so that
overlapping chunks from earlier runs cannot create duplicate rows.

Usage (from backend/):
  python scripts/fetch_raw.py                       # delivery 2026-01-02..2026-02-01
  python scripts/fetch_raw.py --start 2026-01-10 --end 2026-01-20
"""

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402

BASE = "https://data.elexon.co.uk/bmrs/api/v1"
DEFAULT_START, DEFAULT_END = date(2026, 1, 2), date(2026, 2, 1)
ACTUALS_DAYS_BEFORE, ACTUALS_DAYS_AFTER = 11, 1
FORECASTS_DAYS_BEFORE = 12

ACTUALS_CHUNK_DAYS = 7
FORECAST_CHUNK_DAYS = 2
TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 5
BACKOFF_SECONDS = 2  # doubles after each failed attempt
RETRY_STATUS = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    pass


def get_with_retries(url, params):
    """GET JSON rows, retrying network errors and 429/5xx with exponential backoff."""
    delay = BACKOFF_SECONDS
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
        except (requests.ConnectionError, requests.Timeout) as exc:
            problem = f"{type(exc).__name__}: {exc}"
        else:
            if resp.status_code == 200:
                data = resp.json()
                # Stream endpoints return a bare list; others wrap rows in {"data": [...]}.
                return data["data"] if isinstance(data, dict) and "data" in data else data
            problem = f"HTTP {resp.status_code}: {resp.text[:300]}"
            if resp.status_code not in RETRY_STATUS:
                raise FetchError(f"{url} {params} failed, not retrying. {problem}")
        if attempt == MAX_ATTEMPTS:
            raise FetchError(f"{url} {params} failed after {MAX_ATTEMPTS} attempts. {problem}")
        print(f"    attempt {attempt} failed ({problem}); retrying in {delay}s")
        time.sleep(delay)
        delay *= 2


def date_chunks(start, end, days):
    """Inclusive date ranges [a, b] covering start..end."""
    out, cur = [], start
    while cur <= end:
        b = min(cur + timedelta(days=days - 1), end)
        out.append((cur, b))
        cur = b + timedelta(days=1)
    return out


def datetime_chunks(start, end, days):
    """Inclusive minute-resolution ranges covering start 00:00 .. end 23:59 UTC."""
    lo = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    hi = datetime(end.year, end.month, end.day, tzinfo=timezone.utc) + timedelta(days=1)
    out, cur = [], lo
    while cur < hi:
        b = min(cur + timedelta(days=days), hi)
        out.append((cur, b - timedelta(minutes=1)))
        cur = b
    return out


def clear_raw(prefix):
    for f in config.RAW_DIR.glob(f"{prefix}_*.json"):
        f.unlink()


def save(prefix, label, rows):
    path = config.RAW_DIR / f"{prefix}_{label}.json"
    path.write_text(json.dumps(rows, indent=1))
    return path


def fetch_actuals(start, end):
    url = f"{BASE}/datasets/FUELHH/stream"
    clear_raw("fuelhh")
    total = 0
    for a, b in date_chunks(start, end, ACTUALS_CHUNK_DAYS):
        rows = get_with_retries(url, {"settlementDateFrom": a.isoformat(),
                                      "settlementDateTo": b.isoformat(), "fuelType": "WIND"})
        path = save("fuelhh", f"{a}_{b}", rows)
        print(f"  FUELHH  {a} .. {b}: {len(rows):5d} rows -> {path.name}")
        total += len(rows)
    return total


def fetch_forecasts(start, end):
    url = f"{BASE}/datasets/WINDFOR/stream"
    clear_raw("windfor")
    total = 0
    for a, b in datetime_chunks(start, end, FORECAST_CHUNK_DAYS):
        fa, fb = a.strftime("%Y-%m-%dT%H:%MZ"), b.strftime("%Y-%m-%dT%H:%MZ")
        rows = get_with_retries(url, {"publishDateTimeFrom": fa, "publishDateTimeTo": fb})
        path = save("windfor", f"{a:%Y-%m-%dT%H%M}_{b:%Y-%m-%dT%H%M}", rows)
        print(f"  WINDFOR {fa} .. {fb}: {len(rows):5d} rows -> {path.name}")
        total += len(rows)
    return total


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START,
                   help=f"first delivery date (default {DEFAULT_START})")
    p.add_argument("--end", type=date.fromisoformat, default=DEFAULT_END,
                   help=f"last delivery date (default {DEFAULT_END})")
    args = p.parse_args(argv)
    if args.start > args.end:
        p.error(f"--start {args.start} is after --end {args.end}")
    return args


def main(argv=None):
    args = parse_args(argv)
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    act_from = args.start - timedelta(days=ACTUALS_DAYS_BEFORE)
    act_to = args.end + timedelta(days=ACTUALS_DAYS_AFTER)
    fc_from = args.start - timedelta(days=FORECASTS_DAYS_BEFORE)
    print(f"Delivery {args.start} .. {args.end}")
    print(f"Actuals settlement dates {act_from} .. {act_to}")
    n_act = fetch_actuals(act_from, act_to)
    print(f"Forecasts published {fc_from} 00:00 .. {args.end} 23:59 UTC")
    n_fc = fetch_forecasts(fc_from, args.end)
    print(f"Done: {n_act} actual rows, {n_fc} forecast rows in {config.RAW_DIR}")


if __name__ == "__main__":
    try:
        main()
    except FetchError as exc:
        sys.exit(f"ERROR: {exc}")
