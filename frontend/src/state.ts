import { useCallback, useEffect, useRef, useState } from 'react'
import { formatDay } from './format'

export const DELIVERY_START = '2026-01-02'
export const DELIVERY_END = '2026-02-01'
export const DEFAULT_DATE = '2026-01-15'
export const DEFAULT_CUTOFF = '09:00'
export const CUTOFF_OPTIONS = ['07:00', '07:30', '08:00', '08:30', '09:00', '09:30', '10:00', '10:30', '11:00']

export const TABS = ['day', 'accuracy', 'method'] as const
export type Tab = (typeof TABS)[number]

export interface UrlState {
  tab: Tab
  date: string
  cutoff: string
  adjusted: boolean
  others: boolean
}

function isValidDate(s: string | null): s is string {
  return !!s && /^\d{4}-\d{2}-\d{2}$/.test(s) && s >= DELIVERY_START && s <= DELIVERY_END &&
    !Number.isNaN(Date.parse(`${s}T00:00:00Z`))
}

/** Read state from a query string, falling back to defaults for anything invalid. */
export function parseUrlState(search: string): UrlState {
  const q = new URLSearchParams(search)
  const tab = q.get('tab')
  const date = q.get('date')
  const cutoff = q.get('cutoff')
  return {
    tab: TABS.includes(tab as Tab) ? (tab as Tab) : 'day',
    date: isValidDate(date) ? date : DEFAULT_DATE,
    cutoff: cutoff && CUTOFF_OPTIONS.includes(cutoff) ? cutoff : DEFAULT_CUTOFF,
    adjusted: q.get('adjusted') === '1',
    others: q.get('others') === '1',
  }
}

/** Plain-language notes about URL values that were replaced by defaults. */
export function urlNotices(search: string): string[] {
  const q = new URLSearchParams(search)
  const shown = parseUrlState(search)
  const notices: string[] = []
  const date = q.get('date')
  if (date !== null && date !== shown.date) {
    const reason = /^\d{4}-\d{2}-\d{2}$/.test(date) && !Number.isNaN(Date.parse(`${date}T00:00:00Z`))
      ? 'is outside the data range'
      : 'is not a valid date'
    notices.push(`${date} ${reason}; showing ${formatDay(shown.date)}`)
  }
  const cutoff = q.get('cutoff')
  if (cutoff !== null && cutoff !== shown.cutoff) {
    notices.push(`${cutoff} is not an available deadline; showing ${shown.cutoff}`)
  }
  return notices
}

export function toSearch(s: UrlState): string {
  const q = new URLSearchParams({ tab: s.tab, date: s.date, cutoff: s.cutoff })
  if (s.adjusted) q.set('adjusted', '1')
  if (s.others) q.set('others', '1')
  return `?${q}`
}

/**
 * Tab, date, cutoff and the adjusted toggle, kept in the URL so links are shareable.
 * Invalid URL values fall back to defaults; `notices` explains what was replaced, and the
 * URL is rewritten to match what is shown.
 */
export function useUrlState() {
  const [state, setState] = useState(() => parseUrlState(window.location.search))
  const [notices, setNotices] = useState(() => urlNotices(window.location.search))

  useEffect(() => {
    if (urlNotices(window.location.search).length) {
      window.history.replaceState(null, '', toSearch(parseUrlState(window.location.search)))
    }
    const onPop = () => {
      setState(parseUrlState(window.location.search))
      setNotices(urlNotices(window.location.search))
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const dismissNotices = useCallback(() => setNotices([]), [])

  const update = useCallback((patch: Partial<UrlState>) => {
    setState((prev) => {
      const next = { ...prev, ...patch }
      window.history.replaceState(null, '', toSearch(next))
      return next
    })
  }, [])

  return { state, update, notices, dismissNotices }
}

export function shiftDate(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

export type FetchState<T> =
  | { status: 'loading' }
  | { status: 'ok'; data: T }
  | { status: 'error'; error: string }

/** Run `load` whenever `key` changes; aborts the previous request. */
export function useFetch<T>(load: (signal: AbortSignal) => Promise<T>, key: string) {
  const [state, setState] = useState<FetchState<T>>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const loadRef = useRef(load)
  loadRef.current = load

  useEffect(() => {
    const controller = new AbortController()
    setState({ status: 'loading' })
    loadRef.current(controller.signal)
      .then((data) => setState({ status: 'ok', data }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setState({ status: 'error', error: err instanceof Error ? err.message : String(err) })
      })
    return () => controller.abort()
  }, [key, attempt])

  const retry = useCallback(() => setAttempt((a) => a + 1), [])
  return { state, retry }
}
