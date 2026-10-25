"""Explore Elexon BMRS wind data (FUELHH actuals and WINDFOR forecasts).

Fetches raw data from the Elexon Insights API (no key needed), saves each
response chunk to data/raw/*.json, and prints a report on schema, time
resolution, duplicates, publish schedule, day-ahead coverage, missing
actuals, and the scale of actuals vs forecasts.

Usage: python scripts/explore_data.py
"""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = "https://data.elexon.co.uk/bmrs/api/v1"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

ACTUALS_FROM, ACTUALS_TO = date(2025, 12, 31), date(2026, 2, 2)
FORECAST_FROM, FORECAST_TO = date(2025, 12, 29), date(2026, 2, 1)
DELIVERY_FROM, DELIVERY_TO = date(2026, 1, 2), date(2026, 2, 1)
CUTOFF_HOUR_UTC = 9

ACTUALS_CHUNK_DAYS = 7
FORECAST_CHUNK_DAYS = 2

# Candidate param names, tried in order until the API accepts one.
ACTUALS_PARAM_CANDIDATES = [
    ("settlementDateFrom", "settlementDateTo"),
    ("from", "to"),
]
FORECAST_PARAM_CANDIDATES = [
    ("publishDateTimeFrom", "publishDateTimeTo"),
    ("publishTimeFrom", "publishTimeTo"),
    ("from", "to"),
]


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def fetch_json(url, params):
    resp = requests.get(url, params=params, timeout=60)
    if resp.status_code != 200:
        raise requests.HTTPError(f"HTTP {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    # Stream endpoints return a bare list; others wrap rows in {"data": [...]}.
    return data["data"] if isinstance(data, dict) and "data" in data else data


def fetch_chunked(dataset, candidates, chunks, extra_params, fmt):
    """Fetch every chunk, discovering the working param names on the first one."""
    url = f"{BASE}/datasets/{dataset}/stream"
    working = None
    rows = []
    for start, end in chunks:
        names = [working] if working else candidates
        for p_from, p_to in names:
            params = {p_from: fmt(start), p_to: fmt(end), **extra_params}
            try:
                chunk = fetch_json(url, params)
            except requests.HTTPError as exc:
                print(f"  [{dataset}] params {p_from}/{p_to} rejected: {exc}")
                continue
            if working is None:
                working = (p_from, p_to)
                print(f"  [{dataset}] working params: {params}")
            break
        else:
            raise RuntimeError(f"No working param names for {dataset}")
        out = RAW_DIR / f"{dataset.lower()}_{fmt(start)}_{fmt(end)}.json".replace(":", "")
        out.write_text(json.dumps(chunk, indent=1))
        print(f"  [{dataset}] {fmt(start)} -> {fmt(end)}: {len(chunk)} rows -> {out.name}")
        rows.extend(chunk)
    return pd.DataFrame(rows)


def date_chunks(start, end, days):
    """Inclusive date ranges [a, b] covering start..end."""
    out = []
    cur = start
    while cur <= end:
        b = min(cur + timedelta(days=days - 1), end)
        out.append((cur, b))
        cur = b + timedelta(days=1)
    return out


def datetime_chunks(start, end, days):
    """Half-open datetime ranges covering start 00:00 .. end 23:59:59 UTC."""
    lo = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    hi = datetime(end.year, end.month, end.day, tzinfo=timezone.utc) + timedelta(days=1)
    out = []
    cur = lo
    while cur < hi:
        b = min(cur + timedelta(days=days), hi)
        # API "to" is inclusive, so stop one minute short of the next chunk.
        out.append((cur, b - timedelta(minutes=1)))
        cur = b
    return out


def parse_times(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], utc=True)
    return df


def resolution_report(name, df):
    starts = pd.Series(sorted(df["startTime"].unique()))
    diffs = starts.diff().dropna().value_counts()
    print(f"{name}: distinct startTimes={len(starts)}")
    for delta, n in diffs.items():
        print(f"  step {delta}: {n} times")


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    section("FETCH")
    actuals = fetch_chunked(
        "FUELHH",
        ACTUALS_PARAM_CANDIDATES,
        date_chunks(ACTUALS_FROM, ACTUALS_TO, ACTUALS_CHUNK_DAYS),
        {"fuelType": "WIND"},
        lambda d: d.isoformat(),
    )
    forecasts = fetch_chunked(
        "WINDFOR",
        FORECAST_PARAM_CANDIDATES,
        datetime_chunks(FORECAST_FROM, FORECAST_TO, FORECAST_CHUNK_DAYS),
        {},
        lambda d: d.strftime("%Y-%m-%dT%H:%MZ"),
    )

    actuals = parse_times(actuals, ["publishTime", "startTime"])
    forecasts = parse_times(forecasts, ["publishTime", "startTime"])
    # Chunk boundaries can overlap; drop exact duplicate rows before analysis.
    n_fc_raw = len(forecasts)
    forecasts = forecasts.drop_duplicates().reset_index(drop=True)

    # ------------------------------------------------------------------ 1
    section("1. FIELDS, DTYPES, ROW COUNTS")
    for name, df in [("FUELHH (actuals)", actuals), ("WINDFOR (forecasts)", forecasts)]:
        print(f"{name}: {len(df)} rows")
        for col, dt in df.dtypes.items():
            sample = df[col].iloc[0] if len(df) else None
            print(f"  {col:<18} {str(dt):<22} e.g. {sample}")
        print()
    if n_fc_raw != len(forecasts):
        print(f"(WINDFOR: dropped {n_fc_raw - len(forecasts)} exact duplicate rows from chunk overlap)")
    print(f"FUELHH fuelType values: {sorted(actuals['fuelType'].unique())}")
    print(f"FUELHH startTime range: {actuals['startTime'].min()} .. {actuals['startTime'].max()}")
    print(f"WINDFOR publishTime range: {forecasts['publishTime'].min()} .. {forecasts['publishTime'].max()}")
    print(f"WINDFOR startTime range:   {forecasts['startTime'].min()} .. {forecasts['startTime'].max()}")

    # ------------------------------------------------------------------ 2
    section("2. TIME RESOLUTION OF startTime")
    resolution_report("FUELHH", actuals)
    resolution_report("WINDFOR", forecasts)
    fc_minutes = forecasts["startTime"].dt.minute.value_counts().sort_index()
    print(f"WINDFOR startTime minute-of-hour counts: {fc_minutes.to_dict()}")

    # ------------------------------------------------------------------ 3
    section("3. DUPLICATE startTime ROWS IN FUELHH")
    dup_mask = actuals.duplicated("startTime", keep=False)
    dups = actuals[dup_mask].sort_values(["startTime", "publishTime"])
    print(f"Rows sharing a startTime: {len(dups)} "
          f"({dups['startTime'].nunique()} distinct startTimes)")
    if len(dups):
        varying = [c for c in actuals.columns
                   if c != "startTime" and dups.groupby("startTime")[c].nunique().max() > 1]
        print(f"Columns that differ within duplicate groups: {varying}")
        print("First few duplicate groups:")
        print(dups.head(12).to_string(index=False))
    else:
        print("None: each startTime appears exactly once.")
    actuals_dedup = (actuals.sort_values("publishTime")
                     .drop_duplicates("startTime", keep="last")
                     .sort_values("startTime").reset_index(drop=True))

    # ------------------------------------------------------------------ 4
    section("4. WINDFOR PUBLISH SCHEDULE AND LEAD TIMES")
    forecasts["leadHours"] = (forecasts["startTime"] - forecasts["publishTime"]).dt.total_seconds() / 3600
    pubs = (forecasts.groupby("publishTime")
            .agg(rows=("startTime", "size"),
                 minLead=("leadHours", "min"),
                 maxLead=("leadHours", "max"))
            .reset_index())
    pubs["day"] = pubs["publishTime"].dt.date
    pubs["tod"] = pubs["publishTime"].dt.strftime("%H:%M")

    print(f"Distinct publishTimes: {len(pubs)}")
    print("\nPublishes per day (times of day, UTC):")
    for day, g in pubs.groupby("day"):
        print(f"  {day}  n={len(g):<2}  {' '.join(g['tod'])}")

    print("\nBy time of day (all days):")
    tod = (pubs.groupby("tod")
           .agg(days=("day", "nunique"), rows=("rows", "median"),
                minLead=("minLead", "min"), maxLead=("maxLead", "max"))
           .reset_index())
    print(tod.to_string(index=False))

    print("\nPer publish: min/max lead time (hours), row count:")
    for _, r in pubs.iterrows():
        print(f"  {r['publishTime']:%Y-%m-%d %H:%M}  rows={r['rows']:<3} "
              f"lead {r['minLead']:6.1f} .. {r['maxLead']:6.1f} h")

    # ------------------------------------------------------------------ 5
    section(f"5. DAY-AHEAD PUBLISH (latest <= {CUTOFF_HOUR_UTC:02d}:00 UTC previous day) AND COVERAGE")
    fc_starts = forecasts.groupby("publishTime")["startTime"].apply(set)
    pub_times = pubs["publishTime"].sort_values()
    gaps = []
    day = DELIVERY_FROM
    while day <= DELIVERY_TO:
        day_start = pd.Timestamp(day, tz="UTC")
        cutoff = day_start - pd.Timedelta(days=1) + pd.Timedelta(hours=CUTOFF_HOUR_UTC)
        eligible = pub_times[pub_times <= cutoff]
        expected = set(pd.date_range(day_start, periods=24, freq="h"))
        if eligible.empty:
            print(f"  {day}  cutoff {cutoff:%m-%d %H:%M}  NO PUBLISH  <-- GAP")
            gaps.append(day)
        else:
            pub = eligible.iloc[-1]
            missing = sorted(expected - fc_starts[pub])
            age = (cutoff - pub).total_seconds() / 3600
            status = "full 24h" if not missing else f"MISSING {len(missing)}h: " + \
                ", ".join(f"{m:%H:%M}" for m in missing) + "  <-- GAP"
            print(f"  {day}  cutoff {cutoff:%m-%d %H:%M}  publish {pub:%m-%d %H:%M} "
                  f"({age:.1f}h before cutoff)  {status}")
            if missing:
                gaps.append(day)
        day += timedelta(days=1)
    print(f"\nDelivery days with gaps: {len(gaps)}" + (f" -> {gaps}" if gaps else ""))

    # ------------------------------------------------------------------ 6
    section("6. MISSING ACTUALS PERIODS")
    lo = pd.Timestamp(ACTUALS_FROM, tz="UTC")
    hi = pd.Timestamp(ACTUALS_TO, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(minutes=30)
    expected = pd.date_range(lo, hi, freq="30min")
    have = set(actuals_dedup["startTime"])
    missing = [t for t in expected if t not in have]
    print(f"Expected half-hours {lo} .. {hi}: {len(expected)}")
    print(f"Present (deduplicated): {len(have & set(expected))}")
    extra = sorted(have - set(expected))
    if extra:
        print(f"Rows outside expected range: {len(extra)} ({extra[0]} .. {extra[-1]})")
    print(f"Missing: {len(missing)}")
    if missing:
        # Collapse consecutive missing slots into ranges.
        runs, run = [], [missing[0]]
        for t in missing[1:]:
            if t - run[-1] == pd.Timedelta(minutes=30):
                run.append(t)
            else:
                runs.append(run)
                run = [t]
        runs.append(run)
        for r in runs:
            print(f"  {r[0]} .. {r[-1]}  ({len(r)} half-hours)")
    nulls = actuals_dedup["generation"].isna().sum()
    print(f"Null generation values: {nulls}")
    counts = actuals_dedup.groupby("settlementDate").size()
    odd = counts[counts != 48]
    print("Settlement dates without 48 periods: " +
          (", ".join(f"{d}={n}" for d, n in odd.items()) if len(odd) else "none"))

    # ------------------------------------------------------------------ 7
    section("7. SCALE CHECK: JANUARY 2026 MEAN (MW)")
    jan_lo = pd.Timestamp("2026-01-01", tz="UTC")
    jan_hi = pd.Timestamp("2026-02-01", tz="UTC")
    act_jan = actuals_dedup[(actuals_dedup["startTime"] >= jan_lo) & (actuals_dedup["startTime"] < jan_hi)]
    fc_jan = forecasts[(forecasts["startTime"] >= jan_lo) & (forecasts["startTime"] < jan_hi)]
    latest_fc = (fc_jan.sort_values("publishTime")
                 .drop_duplicates("startTime", keep="last"))
    # Actuals on the hourly grid the forecasts use (xx:00 starts only).
    act_on_hour = act_jan[act_jan["startTime"].dt.minute == 0]
    act_hourly_mean = (act_jan.set_index("startTime")["generation"]
                       .resample("h").mean())

    mean_act = act_jan["generation"].mean()
    print(f"Actual  (all half-hours, n={len(act_jan)}):            {mean_act:9.1f}")
    print(f"Actual  (xx:00 half-hours only, n={len(act_on_hour)}):       {act_on_hour['generation'].mean():9.1f}")
    print(f"Actual  (hourly mean of half-hours, n={len(act_hourly_mean)}):   {act_hourly_mean.mean():9.1f}")
    print(f"Forecast (all rows, all publishes, n={len(fc_jan)}):   {fc_jan['generation'].mean():9.1f}")
    print(f"Forecast (latest publish per hour, n={len(latest_fc)}):    {latest_fc['generation'].mean():9.1f}")
    print(f"Ratio forecast(latest)/actual(all): {latest_fc['generation'].mean() / mean_act:.3f}")
    print(f"Actual  min/max: {act_jan['generation'].min()} / {act_jan['generation'].max()}")
    print(f"Forecast min/max: {fc_jan['generation'].min()} / {fc_jan['generation'].max()}")


if __name__ == "__main__":
    main()
