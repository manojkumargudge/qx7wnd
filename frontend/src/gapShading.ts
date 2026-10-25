export interface GapInput {
  hour: number
  forecast: number
  actual: number | null
}

export interface GapPoint {
  hour: number
  forecast: number | null
  actual: number | null
  /** [low, high] band where forecast > actual (wind planned but not delivered); zero-width otherwise. */
  shortfall: [number, number] | null
  /** [low, high] band where forecast < actual (extra wind); zero-width otherwise. */
  surplus: [number, number] | null
  /** True for points inserted where the two lines cross. */
  crossing: boolean
}

function point(hour: number, forecast: number, actual: number, crossing = false): GapPoint {
  const lo = Math.min(forecast, actual)
  const hi = Math.max(forecast, actual)
  return {
    hour,
    forecast,
    actual,
    shortfall: forecast > actual ? [lo, hi] : [actual, actual],
    surplus: forecast < actual ? [lo, hi] : [actual, actual],
    crossing,
  }
}

/**
 * Range-area series for shading the gap between forecast and actual.
 *
 * Where the lines cross between two hours, a point is inserted at the interpolated
 * crossing so the red and blue bands meet exactly there instead of overlapping.
 * Hours without an actual get no band.
 */
export function buildGapSeries(rows: GapInput[]): GapPoint[] {
  const out: GapPoint[] = []
  rows.forEach((r, i) => {
    if (r.actual === null) {
      out.push({ hour: r.hour, forecast: r.forecast, actual: null, shortfall: null, surplus: null, crossing: false })
      return
    }
    const prev = rows[i - 1]
    if (prev && prev.actual !== null) {
      const d0 = prev.forecast - prev.actual
      const d1 = r.forecast - r.actual
      if ((d0 > 0 && d1 < 0) || (d0 < 0 && d1 > 0)) {
        const t = d0 / (d0 - d1)
        const value = prev.actual + t * (r.actual - prev.actual)
        out.push(point(prev.hour + t * (r.hour - prev.hour), value, value, true))
      }
    }
    out.push(point(r.hour, r.forecast, r.actual))
  })
  return out
}
