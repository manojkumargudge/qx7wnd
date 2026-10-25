// Plain-language number and time formatting. All times are UTC.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const MINUS = '−'
const intFormat = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 })

function roundedAbs(v: number): number {
  return Math.abs(Math.round(v))
}

/** 1041.8 -> "1,042 MW" */
export function formatMW(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '–'
  const r = Math.round(v)
  return `${r < 0 ? MINUS : ''}${intFormat.format(Math.abs(r))} MW`
}

/** Axis ticks in thousands of MW: 18000 -> "18k", 4500 -> "4.5k", -2000 -> "−2k" */
export function formatK(v: number): string {
  const k = Math.round(v / 100) / 10
  return `${k < 0 ? MINUS : ''}${Math.abs(k)}k`
}

/** 1041.8 -> "+1,042 MW", -549.3 -> "−549 MW", 0.2 -> "0 MW" */
export function formatSignedMW(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '–'
  const r = Math.round(v)
  const sign = r > 0 ? '+' : r < 0 ? MINUS : ''
  return `${sign}${intFormat.format(Math.abs(r))} MW`
}

/** Bias is forecast − actual: positive means the forecast was too high. */
export function biasSentence(bias: number | null | undefined): string {
  if (bias === null || bias === undefined || Number.isNaN(bias)) return 'No data'
  if (Math.round(bias) === 0) return 'Forecast was right on average'
  const size = formatMW(roundedAbs(bias))
  return bias > 0
    ? `Forecast was too high by ${size} on average`
    : `Forecast was too low by ${size} on average`
}

/** P90 of forecast − actual: the "wind came in below forecast" tail. */
export function p90Sentence(p90: number): string {
  if (Math.round(p90) > 0) {
    return `In 1 of 10 hours, wind came in at least ${formatMW(roundedAbs(p90))} below forecast.`
  }
  return `Even in the worst 10% of hours, wind did not come in below forecast.`
}

/** P10 of forecast − actual: the "wind came in above forecast" tail. */
export function p10Sentence(p10: number): string {
  if (Math.round(p10) < 0) {
    return `In 1 of 10 hours, wind came in at least ${formatMW(roundedAbs(p10))} above forecast.`
  }
  return `In 9 of 10 hours the forecast was too high by at least ${formatMW(roundedAbs(p10))}.`
}

/** "2026-01-14T07:30:00Z" -> "07:30 on 14 Jan" */
export function formatPublish(iso: string): string {
  const d = new Date(iso)
  const hh = String(d.getUTCHours()).padStart(2, '0')
  const mm = String(d.getUTCMinutes()).padStart(2, '0')
  return `${hh}:${mm} on ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`
}

/** "2026-01-15" (or an ISO timestamp) -> "15 Jan" */
export function formatDay(isoDate: string): string {
  const d = new Date(isoDate.length === 10 ? `${isoDate}T00:00:00Z` : isoDate)
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`
}

/** "2026-01-15" -> "Thursday 15 January 2026" */
export function formatLongDay(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
  })
}

/** 7 -> "07:00" */
export function formatHour(hour: number): string {
  return `${String(hour).padStart(2, '0')}:00`
}

/** Hours between publish and the first/last delivery hour of the day. */
export function leadRange(publishIso: string, deliveryDate: string): [number, number] {
  const first = (Date.parse(`${deliveryDate}T00:00:00Z`) - Date.parse(publishIso)) / 3_600_000
  return [first, first + 23]
}

/** 16.5 -> "16.5", 17 -> "17" */
export function formatHours(h: number): string {
  return Number.isInteger(h) ? String(h) : h.toFixed(1)
}
