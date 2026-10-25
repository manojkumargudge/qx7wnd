"""FastAPI app serving decision-time wind forecast accuracy for January 2026.

Run (from backend/): uvicorn app.main:app --reload
All times are UTC. Errors are forecast - actual, in MW.
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from typing import Annotated, Literal, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import config, metrics
from app.correction import METHODS, InsufficientHistoryError, corrected_forecasts_for_range, \
    training_window
from app.data import load_actuals, load_forecasts
from app.forecast import NoDecisionForecastError, cutoff_timestamp, decision_forecast, \
    decision_forecasts_for_range

DELIVERY_START = date(2026, 1, 2)
DELIVERY_END = date(2026, 2, 1)
MAX_ACCURACY_LEAD_HOURS = 48
CORS_ORIGINS = ["http://localhost:5173"]
DATA_SOURCE = ("Elexon BMRS Insights API: FUELHH (fuelType=WIND) half-hourly outturn, "
               "averaged to hourly; WINDFOR hourly national wind forecasts.")
TIMEZONE_NOTE = ("All times are UTC. A delivery day is 00:00-23:00 UTC; its forecast is the "
                 "latest WINDFOR publish at or before the cutoff time on the previous day.")

CORRECTION_NOTE = ("Corrections are trained on delivery days D-8..D-2 only (decision-time "
                   "forecasts vs actuals), so they use nothing unknown at the D-1 cutoff.")

CutoffParam = Annotated[str, Query(pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
                                   description="Decision cutoff on D-1, HH:MM UTC")]
Method = Literal["additive", "ratio"]


# ---------------------------------------------------------------- data

@dataclass(frozen=True)
class Dataset:
    actuals: pd.DataFrame
    forecasts: pd.DataFrame


@lru_cache(maxsize=1)
def get_dataset() -> Dataset:
    return Dataset(actuals=load_actuals(), forecasts=load_forecasts())


@lru_cache(maxsize=32)
def decision_errors(cutoff: str) -> pd.DataFrame:
    """Decision-time forecasts for the full range, joined to actuals."""
    ds = get_dataset()
    fc = decision_forecasts_for_range(ds.forecasts, DELIVERY_START, DELIVERY_END, cutoff)
    return metrics.join_actuals(fc, ds.actuals)


@lru_cache(maxsize=32)
def corrected_errors(cutoff: str, method: str) -> pd.DataFrame:
    """Corrected decision-time forecasts for the full range; error uses corrected_mw."""
    ds = get_dataset()
    fc = corrected_forecasts_for_range(ds.forecasts, ds.actuals, DELIVERY_START, DELIVERY_END,
                                       cutoff, method)
    joined = metrics.join_actuals(fc, ds.actuals)
    joined["error"] = joined["corrected_mw"] - joined["actual_mw"]
    return joined


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_dataset()
    yield


# ---------------------------------------------------------------- models

class Health(BaseModel):
    status: str


class Meta(BaseModel):
    delivery_start: date
    delivery_end: date
    default_cutoff: str
    publish_times_of_day: list[str]
    correction_methods: list[str]
    default_correction_method: str
    correction_note: str
    data_source: str
    timezone: str


class Summary(BaseModel):
    n: int
    mae: float
    rmse: float
    bias: float
    p10: float
    p50: float
    p90: float


class DayRow(BaseModel):
    hour: int
    start_time: datetime
    forecast_mw: float
    corrected_forecast_mw: float
    actual_mw: Optional[float]
    error_mw: Optional[float]


class CorrectionUsed(BaseModel):
    method: str
    value: float
    unit: str
    window_start: date
    window_end: date


class PublishPoint(BaseModel):
    hour: int
    forecast_mw: float
    lead_hours: float


class OtherPublish(BaseModel):
    publish_time: datetime
    after_decision: bool
    rows: list[PublishPoint]


class DaySummary(BaseModel):
    mae: Optional[float]
    bias: Optional[float]


class DayResponse(BaseModel):
    date: date
    cutoff: str
    decision_time: datetime
    publish_time: datetime
    rows: list[DayRow]
    summary: DaySummary
    correction: CorrectionUsed
    other_publishes: list[OtherPublish]


class HourStat(BaseModel):
    hour: int
    n: int
    mae: float
    bias: float


class LeadStat(BaseModel):
    lead_bucket: str
    n: int
    mae: float
    bias: float


class DailyStat(BaseModel):
    date: date
    mae: float
    bias: float


class CorrectedSummaries(BaseModel):
    additive: Summary
    ratio: Summary


class AccuracyResponse(BaseModel):
    cutoff: str
    start: date
    end: date
    summary: Summary
    corrected: CorrectedSummaries
    by_hour_of_day: list[HourStat]
    by_lead_bucket: list[LeadStat]
    daily: list[DailyStat]


class TimeseriesPoint(BaseModel):
    start_time: datetime
    forecast_mw: float
    actual_mw: float


class TimeseriesResponse(BaseModel):
    cutoff: str
    start: date
    end: date
    points: list[TimeseriesPoint]


# ---------------------------------------------------------------- app

app = FastAPI(title="Wind forecast accuracy", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET"],
                   allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    """Flatten pydantic errors into one readable message."""
    parts = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"] if p not in ("query", "path", "body"))
        msg = err["msg"]
        if err["type"] == "string_pattern_mismatch":
            msg = "must be HH:MM in 24-hour UTC, e.g. 09:00"
        parts.append(f"{field}: {msg} (got {err.get('input')!r})")
    return JSONResponse(status_code=422, content={"detail": "; ".join(parts)})


@app.exception_handler(NoDecisionForecastError)
@app.exception_handler(InsufficientHistoryError)
async def data_gap(_request: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def check_in_range(name: str, d: date):
    if not DELIVERY_START <= d <= DELIVERY_END:
        raise HTTPException(422, f"{name}: {d} is outside the available delivery range "
                                 f"{DELIVERY_START}..{DELIVERY_END}")


def resolve_range(start: Optional[date], end: Optional[date]) -> tuple[date, date]:
    start, end = start or DELIVERY_START, end or DELIVERY_END
    check_in_range("start", start)
    check_in_range("end", end)
    if start > end:
        raise HTTPException(422, f"start ({start}) must be on or before end ({end})")
    return start, end


def in_range(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    days = df["start_time"].dt.date
    return df[(days >= start) & (days <= end)]


def optional_float(x) -> Optional[float]:
    return None if pd.isna(x) else float(x)


@app.get("/api/health", response_model=Health)
def health():
    return Health(status="ok")


@app.get("/api/meta", response_model=Meta)
def meta():
    times = get_dataset().forecasts["publish_time"].dt.strftime("%H:%M").unique()
    return Meta(delivery_start=DELIVERY_START, delivery_end=DELIVERY_END,
                default_cutoff=config.CUTOFF, publish_times_of_day=sorted(times),
                correction_methods=list(METHODS),
                default_correction_method=config.DEFAULT_CORRECTION_METHOD,
                correction_note=CORRECTION_NOTE, data_source=DATA_SOURCE,
                timezone=TIMEZONE_NOTE)


@app.get("/api/day", response_model=DayResponse)
def day(date: date, cutoff: CutoffParam = config.CUTOFF, method: Optional[Method] = None):
    check_in_range("date", date)
    method = method or config.DEFAULT_CORRECTION_METHOD
    ds = get_dataset()
    chosen = decision_forecast(ds.forecasts, date, cutoff)
    corrected = corrected_forecasts_for_range(ds.forecasts, ds.actuals, date, date, cutoff, method)
    joined = corrected.merge(ds.actuals, on="start_time", how="left")
    joined["error"] = joined["forecast_mw"] - joined["actual_mw"]
    publish = chosen["publish_time"].iloc[0]
    decided_at = cutoff_timestamp(date, cutoff)
    window_start, window_end = training_window(date)

    rows = [DayRow(hour=r.start_time.hour, start_time=r.start_time.to_pydatetime(),
                   forecast_mw=r.forecast_mw, corrected_forecast_mw=r.corrected_mw,
                   actual_mw=optional_float(r.actual_mw), error_mw=optional_float(r.error))
            for r in joined.itertuples()]

    others = in_range(ds.forecasts, date, date)
    others = others[others["publish_time"] != publish]
    other_publishes = [
        OtherPublish(publish_time=pt.to_pydatetime(), after_decision=bool(pt > decided_at),
                     rows=[PublishPoint(hour=r.start_time.hour, forecast_mw=r.forecast_mw,
                                        lead_hours=r.lead_hours)
                           for r in g.sort_values("start_time").itertuples()])
        for pt, g in others.groupby("publish_time")
    ]

    errors = joined["error"].dropna()
    return DayResponse(
        date=date, cutoff=cutoff, decision_time=decided_at.to_pydatetime(),
        publish_time=publish.to_pydatetime(), rows=rows,
        summary=DaySummary(mae=optional_float(errors.abs().mean()),
                           bias=optional_float(errors.mean())),
        correction=CorrectionUsed(method=method, value=float(corrected["correction"].iloc[0]),
                                  unit="MW subtracted" if method == "additive" else "multiplier",
                                  window_start=window_start, window_end=window_end),
        other_publishes=other_publishes)


@app.get("/api/accuracy", response_model=AccuracyResponse)
def accuracy(cutoff: CutoffParam = config.CUTOFF, start: Optional[date] = None,
             end: Optional[date] = None):
    start, end = resolve_range(start, end)
    dec = in_range(decision_errors(cutoff), start, end)

    ds = get_dataset()
    all_pubs = metrics.join_actuals(in_range(ds.forecasts, start, end), ds.actuals)
    all_pubs = all_pubs[all_pubs["lead_hours"] < MAX_ACCURACY_LEAD_HOURS]

    daily = (dec.assign(abs_error=dec["error"].abs())
             .groupby("delivery_date")
             .agg(mae=("abs_error", "mean"), bias=("error", "mean"))
             .reset_index())
    return AccuracyResponse(
        cutoff=cutoff, start=start, end=end,
        summary=Summary(**metrics.summary(dec)),
        corrected=CorrectedSummaries(**{
            m: Summary(**metrics.summary(in_range(corrected_errors(cutoff, m), start, end)))
            for m in METHODS}),
        by_hour_of_day=metrics.by_hour_of_day(dec).to_dict("records"),
        by_lead_bucket=metrics.by_lead_bucket(all_pubs).astype({"lead_bucket": str})
        .to_dict("records"),
        daily=[DailyStat(date=r.delivery_date, mae=r.mae, bias=r.bias)
               for r in daily.itertuples()])


@app.get("/api/timeseries", response_model=TimeseriesResponse)
def timeseries(cutoff: CutoffParam = config.CUTOFF, start: Optional[date] = None,
               end: Optional[date] = None):
    start, end = resolve_range(start, end)
    dec = in_range(decision_errors(cutoff), start, end).sort_values("start_time")
    return TimeseriesResponse(
        cutoff=cutoff, start=start, end=end,
        points=[TimeseriesPoint(start_time=r.start_time.to_pydatetime(),
                                forecast_mw=r.forecast_mw, actual_mw=r.actual_mw)
                for r in dec.itertuples()])
