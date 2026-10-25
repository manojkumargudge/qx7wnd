// Typed client for the FastAPI backend. Types mirror the Pydantic models in backend/app/main.py.
// The base is relative so the same build works behind the Vite proxy and on Vercel.
const API_BASE = '/api'

export type CorrectionMethod = 'additive' | 'ratio'

export interface Health {
  status: string
}

export interface IrregularPublish {
  time: string
  dates: string[]
}

export interface Meta {
  delivery_start: string
  delivery_end: string
  default_cutoff: string
  publish_times_of_day: string[]
  irregular_publishes: IrregularPublish[]
  correction_methods: CorrectionMethod[]
  default_correction_method: CorrectionMethod
  correction_note: string
  data_source: string
  timezone: string
}

export interface Summary {
  n: number
  mae: number
  rmse: number
  bias: number
  p10: number
  p50: number
  p90: number
}

export interface DayRow {
  hour: number
  start_time: string
  forecast_mw: number
  corrected_forecast_mw: number
  actual_mw: number | null
  error_mw: number | null
}

export interface CorrectionUsed {
  method: CorrectionMethod
  value: number
  unit: string
  window_start: string
  window_end: string
}

export interface PublishPoint {
  hour: number
  forecast_mw: number
  lead_hours: number
}

export interface OtherPublish {
  publish_time: string
  after_decision: boolean
  rows: PublishPoint[]
}

export interface DaySummary {
  mae: number | null
  bias: number | null
  corrected_mae: number | null
  corrected_bias: number | null
}

export interface DayResponse {
  date: string
  cutoff: string
  decision_time: string
  publish_time: string
  rows: DayRow[]
  summary: DaySummary
  correction: CorrectionUsed
  other_publishes: OtherPublish[]
}

export interface HourStat {
  hour: number
  n: number
  mae: number
  bias: number
}

export interface LeadStat {
  lead_bucket: string
  n: number
  mae: number
  bias: number
}

export interface DailyStat {
  date: string
  mae: number
  bias: number
  additive_mae: number
  ratio_mae: number
}

export interface AccuracyResponse {
  cutoff: string
  start: string
  end: string
  summary: Summary
  corrected: Record<CorrectionMethod, Summary>
  by_hour_of_day: HourStat[]
  by_lead_bucket: LeadStat[]
  daily: DailyStat[]
}

export interface TimeseriesPoint {
  start_time: string
  forecast_mw: number
  actual_mw: number
}

export interface TimeseriesResponse {
  cutoff: string
  start: string
  end: string
  points: TimeseriesPoint[]
}

/** An HTTP error from the API (status > 0) or a network failure (status 0). */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type Params = Record<string, string | undefined>

export async function getJson<T>(path: string, params: Params = {}, signal?: AbortSignal): Promise<T> {
  const query = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) query.set(k, v)
  }
  const qs = query.toString()
  const url = `${API_BASE}${path}${qs ? `?${qs}` : ''}`

  let res: Response
  try {
    res = await fetch(url, { signal })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError(0, 'Could not reach the server. Check your connection and try again.')
  }

  if (!res.ok) {
    let detail = res.statusText || 'Request failed'
    try {
      const body: unknown = await res.json()
      if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
        detail = body.detail
      }
    } catch {
      // Body was not JSON; keep the status text.
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

export const api = {
  health: (signal?: AbortSignal) => getJson<Health>('/health', {}, signal),
  meta: (signal?: AbortSignal) => getJson<Meta>('/meta', {}, signal),
  day: (date: string, cutoff: string, signal?: AbortSignal) =>
    getJson<DayResponse>('/day', { date, cutoff }, signal),
  accuracy: (cutoff: string, signal?: AbortSignal) =>
    getJson<AccuracyResponse>('/accuracy', { cutoff }, signal),
  timeseries: (cutoff: string, signal?: AbortSignal) =>
    getJson<TimeseriesResponse>('/timeseries', { cutoff }, signal),
}
