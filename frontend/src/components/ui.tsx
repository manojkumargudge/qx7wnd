import type { ReactNode } from 'react'
import type { FetchState } from '../state'
import { CUTOFF_OPTIONS } from '../state'

export function KpiCard({ label, value, note, extra }: {
  label: string
  value: string
  note?: string
  extra?: ReactNode
}) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {note && <div className="kpi-note">{note}</div>}
      {extra && <div className="kpi-extra">{extra}</div>}
    </div>
  )
}

/** Renders loading, error (with retry) or empty states; otherwise calls children with the data. */
export function Loadable<T>({ state, retry, isEmpty, emptyText = 'No data for this selection.', children }: {
  state: FetchState<T>
  retry?: () => void
  isEmpty?: (data: T) => boolean
  emptyText?: string
  children: (data: T) => ReactNode
}) {
  if (state.status === 'loading') {
    return <div className="state state-loading" role="status">Loading…</div>
  }
  if (state.status === 'error') {
    return (
      <div className="state state-error" role="alert">
        <p>Couldn’t load this data: {state.error}</p>
        {retry && <button type="button" onClick={retry}>Try again</button>}
      </div>
    )
  }
  if (isEmpty?.(state.data)) {
    return <div className="state state-empty">{emptyText}</div>
  }
  return <>{children(state.data)}</>
}

export function CutoffSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <label className="control">
      <span>Decision deadline (day before)</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {CUTOFF_OPTIONS.map((t) => <option key={t} value={t}>{t} UTC</option>)}
      </select>
    </label>
  )
}

export function ChartCard({ title, caption, children }: {
  title: string
  caption?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="card">
      <h3>{title}</h3>
      {caption && <p className="caption">{caption}</p>}
      <div className="chart">{children}</div>
    </section>
  )
}

export function LegendItem({ color, label, dashed, thick, faint, swatch }: {
  color: string
  label: string
  dashed?: boolean
  thick?: boolean
  faint?: boolean
  /** Draw a filled block (for shaded areas) instead of a line. */
  swatch?: boolean
}) {
  return (
    <span className="legend-item">
      <svg width="28" height="12" aria-hidden="true">
        {swatch
          ? <rect x="0" y="1" width="28" height="10" rx="2" fill={color} />
          : <line x1="0" y1="6" x2="28" y2="6" stroke={color} strokeWidth={thick ? 3.5 : 2}
            strokeDasharray={dashed ? '5 3' : undefined} strokeOpacity={faint ? 0.6 : 1} />}
      </svg>
      {label}
    </span>
  )
}
