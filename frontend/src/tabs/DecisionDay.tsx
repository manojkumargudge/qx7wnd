import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip,
  XAxis, YAxis,
} from 'recharts'
import type { TooltipProps } from 'recharts'
import { api, type DayResponse } from '../api'
import { COLORS } from '../colors'
import { ChartCard, CutoffSelect, KpiCard, LegendItem, Loadable } from '../components/ui'
import {
  biasSentence, formatHour, formatHours, formatK, formatLongDay, formatMW, formatPublish, formatSignedMW, leadRange,
} from '../format'
import { DELIVERY_END, DELIVERY_START, shiftDate, useFetch, type UrlState } from '../state'

type ChartRow = Record<string, number | null>

const lowerFirst = (s: string) => s.charAt(0).toLowerCase() + s.slice(1)

const MAIN_SERIES: Record<string, string> = {
  actual: 'Actual wind',
  forecast: 'Forecast used',
  adjusted: 'Bias-adjusted forecast',
}

function buildChartRows(day: DayResponse): ChartRow[] {
  const rows: ChartRow[] = day.rows.map((r) => ({
    hour: r.hour,
    actual: r.actual_mw,
    forecast: r.forecast_mw,
    adjusted: r.corrected_forecast_mw,
  }))
  day.other_publishes.forEach((p, i) => {
    for (const pt of p.rows) {
      const row = rows.find((r) => r.hour === pt.hour)
      if (row) row[`p${i}`] = pt.forecast_mw
    }
  })
  return rows
}

function MainTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const shown = payload.filter((p) => typeof p.dataKey === 'string' && p.dataKey in MAIN_SERIES)
  return (
    <div className="tooltip">
      <strong>{formatHour(Number(label))}</strong>
      {shown.map((p) => (
        <div key={String(p.dataKey)} style={{ color: p.color }}>
          {MAIN_SERIES[String(p.dataKey)]}: {formatMW(p.value as number)}
        </div>
      ))}
    </div>
  )
}

function ErrorTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const v = payload[0].value as number
  return (
    <div className="tooltip">
      <strong>{formatHour(Number(label))}</strong>
      <div>{v >= 0 ? 'Forecast too high by ' : 'Forecast too low by '}{formatMW(Math.abs(v))}</div>
    </div>
  )
}

function DayView({ day, adjusted }: { day: DayResponse; adjusted: boolean }) {
  const [leadFrom, leadTo] = leadRange(day.publish_time, day.date)
  const observed = day.rows.filter((r) => r.actual_mw !== null)
  const overRaw = observed.filter((r) => (r.error_mw ?? 0) > 0).length
  const overAdj = observed.filter((r) => r.corrected_forecast_mw - (r.actual_mw as number) > 0).length
  const chartRows = buildChartRows(day)
  const { summary: s, correction } = day
  const adjustedLine = (text: string) => adjusted && <>Bias-adjusted: {text}</>

  return (
    <>
      <p className="info">
        Forecast used: published {formatPublish(day.publish_time)}, {formatHours(leadFrom)}–{formatHours(leadTo)} h
        ahead of delivery.
        {adjusted && (
          <> Bias adjustment: {correction.method === 'ratio'
            ? `forecast × ${correction.value.toFixed(3)}`
            : `forecast − ${formatMW(correction.value)}`}, learned from {correction.window_start} to {correction.window_end}.</>
        )}
      </p>

      <div className="kpis">
        <KpiCard label="Average miss (MAE)" value={formatMW(s.mae)}
          note="Typical size of the hourly gap between forecast and actual"
          extra={adjustedLine(formatMW(s.corrected_mae))} />
        <KpiCard label="Bias" value={formatSignedMW(s.bias)} note={biasSentence(s.bias)}
          extra={adjustedLine(`${formatSignedMW(s.corrected_bias)} (${lowerFirst(biasSentence(s.corrected_bias))})`)} />
        <KpiCard label="Hours over-forecast" value={`${overRaw} / ${observed.length}`}
          note="Hours where the forecast was higher than actual wind"
          extra={adjustedLine(`${overAdj} / ${observed.length}`)} />
      </div>

      <ChartCard title={`Wind generation on ${formatLongDay(day.date)}`}
        caption="Grey lines are the other forecasts published for this day.">
        <div className="legend">
          <LegendItem color={COLORS.actual} label="Actual wind" />
          <LegendItem color={COLORS.forecast} label="Forecast used (latest before deadline)" thick />
          {adjusted && <LegendItem color={COLORS.adjusted} label="Bias-adjusted forecast (experimental)" />}
          <LegendItem color={COLORS.otherPublish} label="Earlier forecasts" faint />
          <LegendItem color={COLORS.otherPublish} label="Published after deadline – not available to the buyer" dashed faint />
        </div>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={chartRows} margin={{ top: 8, right: 12, bottom: 0, left: 8 }}>
            <CartesianGrid stroke={COLORS.grid} vertical={false} />
            <XAxis dataKey="hour" tickFormatter={formatHour} interval={2} tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={formatK} width={40} tick={{ fontSize: 12 }}
              label={{ value: 'MW', angle: -90, position: 'insideLeft', fontSize: 12 }} />
            <Tooltip content={<MainTooltip />} />
            {day.other_publishes.map((p, i) => (
              <Line key={p.publish_time} dataKey={`p${i}`} stroke={COLORS.otherPublish}
                strokeOpacity={p.after_decision ? 0.55 : 0.4} strokeWidth={1}
                strokeDasharray={p.after_decision ? '5 3' : undefined}
                dot={false} activeDot={false} isAnimationActive={false} connectNulls={false} />
            ))}
            <Line dataKey="actual" stroke={COLORS.actual} strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line dataKey="forecast" stroke={COLORS.forecast} strokeWidth={3.5} dot={false} isAnimationActive={false} />
            {adjusted && (
              <Line dataKey="adjusted" stroke={COLORS.adjusted} strokeWidth={2} dot={false} isAnimationActive={false} />
            )}
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Hourly error (forecast − actual)"
        caption="Red bars: forecast too high (less wind than planned). Blue bars: forecast too low.">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={day.rows} margin={{ top: 8, right: 12, bottom: 0, left: 8 }}>
            <CartesianGrid stroke={COLORS.grid} vertical={false} />
            <XAxis dataKey="hour" tickFormatter={formatHour} interval={2} tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={formatK} width={40} tick={{ fontSize: 12 }} />
            <Tooltip content={<ErrorTooltip />} />
            <ReferenceLine y={0} stroke="#6b7280" />
            <Bar dataKey="error_mw" isAnimationActive={false}>
              {day.rows.map((r) => (
                <Cell key={r.hour} fill={(r.error_mw ?? 0) >= 0 ? COLORS.tooHigh : COLORS.tooLow} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </>
  )
}

export function DecisionDay({ state, update }: { state: UrlState; update: (p: Partial<UrlState>) => void }) {
  const { date, cutoff, adjusted } = state
  const { state: day, retry } = useFetch((signal) => api.day(date, cutoff, signal), `${date}|${cutoff}`)

  return (
    <>
      <div className="controls">
        <label className="control">
          <span>Delivery day</span>
          <div className="date-row">
            <button type="button" aria-label="Previous day" disabled={date <= DELIVERY_START}
              onClick={() => update({ date: shiftDate(date, -1) })}>‹</button>
            <input type="date" value={date} min={DELIVERY_START} max={DELIVERY_END}
              onChange={(e) => {
                const v = e.target.value
                if (v >= DELIVERY_START && v <= DELIVERY_END) update({ date: v })
              }} />
            <button type="button" aria-label="Next day" disabled={date >= DELIVERY_END}
              onClick={() => update({ date: shiftDate(date, 1) })}>›</button>
          </div>
        </label>
        <CutoffSelect value={cutoff} onChange={(v) => update({ cutoff: v })} />
        <label className="control toggle">
          <input type="checkbox" checked={adjusted} onChange={(e) => update({ adjusted: e.target.checked })} />
          <span>Show bias-adjusted forecast (experimental)</span>
        </label>
      </div>

      <Loadable state={day} retry={retry} isEmpty={(d) => d.rows.length === 0}>
        {(d) => <DayView day={d} adjusted={adjusted} />}
      </Loadable>
    </>
  )
}
