import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip,
  XAxis, YAxis,
} from 'recharts'
import type { TooltipProps } from 'recharts'
import { api, type DayResponse } from '../api'
import { COLORS } from '../colors'
import { ChartCard, CutoffSelect, KpiCard, LegendItem, Loadable } from '../components/ui'
import {
  biasSentence, formatGWh, formatHour, formatHours, formatK, formatLongDay, formatMW, formatPublish, formatSignedMW,
  leadRange,
} from '../format'
import { buildGapSeries } from '../gapShading'
import { DELIVERY_END, DELIVERY_START, shiftDate, useFetch, type UrlState } from '../state'

type ChartRow = Record<string, number | [number, number] | boolean | null>

const HOUR_TICKS = [0, 3, 6, 9, 12, 15, 18, 21]

const lowerFirst = (s: string) => s.charAt(0).toLowerCase() + s.slice(1)

const MAIN_SERIES: Record<string, string> = {
  actual: 'Actual wind',
  forecast: 'Forecast used',
  adjusted: 'Bias-adjusted forecast',
}

/** Gap-shading points plus, on whole hours, the adjusted forecast and other publishes. */
function buildChartRows(day: DayResponse): ChartRow[] {
  const gap = buildGapSeries(day.rows.map((r) => ({ hour: r.hour, forecast: r.forecast_mw, actual: r.actual_mw })))
  const rows: ChartRow[] = gap.map((g) => ({ ...g }))
  for (const r of day.rows) {
    const row = rows.find((x) => x.hour === r.hour && !x.crossing)
    if (row) row.adjusted = r.corrected_forecast_mw
  }
  day.other_publishes.forEach((p, i) => {
    for (const pt of p.rows) {
      const row = rows.find((x) => x.hour === pt.hour && !x.crossing)
      if (row) row[`p${i}`] = pt.forecast_mw
    }
  })
  return rows
}

function MainTooltip({ active, payload, label }: TooltipProps<number, string>) {
  // Crossing points sit between whole hours; only whole hours get a tooltip.
  if (!active || !payload?.length || !Number.isInteger(Number(label))) return null
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

function DayView({ day, adjusted, others }: { day: DayResponse; adjusted: boolean; others: boolean }) {
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
        <KpiCard label="Wind shortfall" value={formatGWh(s.shortfall_mwh)}
          note="Energy you planned to get from wind that didn’t arrive"
          extra={adjustedLine(formatGWh(s.corrected_shortfall_mwh))} />
        <KpiCard label="Extra wind" value={formatGWh(s.surplus_mwh)}
          note="Wind that arrived beyond what was forecast"
          extra={adjustedLine(formatGWh(s.corrected_surplus_mwh))} />
      </div>

      <ChartCard title={`Wind generation on ${formatLongDay(day.date)}`}
        caption={others
          ? 'Shading shows the gap between the forecast used and actual wind. Grey lines are the other forecasts published for this day.'
          : 'Shading shows the gap between the forecast used and actual wind.'}>
        <div className="legend">
          <LegendItem color={COLORS.actual} label="Actual wind" />
          <LegendItem color={COLORS.forecast} label="Forecast used (latest before deadline)" thick />
          {adjusted && <LegendItem color={COLORS.adjusted} label="Bias-adjusted forecast (experimental)" />}
          <LegendItem color={COLORS.shortfallFill} label="Gap: wind planned but not delivered" swatch />
          <LegendItem color={COLORS.surplusFill} label="Gap: extra wind" swatch />
          {others && <LegendItem color={COLORS.otherPublish} label="Earlier forecasts" faint />}
          {others && (
            <LegendItem color={COLORS.otherPublish} label="Published after deadline – not available to the buyer" dashed faint />
          )}
        </div>
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={chartRows} margin={{ top: 8, right: 12, bottom: 0, left: 8 }}>
            <CartesianGrid stroke={COLORS.grid} vertical={false} />
            <XAxis dataKey="hour" type="number" domain={[0, 23]} ticks={HOUR_TICKS} tickFormatter={formatHour}
              tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={formatK} width={40} tick={{ fontSize: 12 }}
              label={{ value: 'MW', angle: -90, position: 'insideLeft', fontSize: 12 }} />
            <Tooltip content={<MainTooltip />} />
            <Area dataKey="shortfall" stroke="none" fill={COLORS.shortfallFill} fillOpacity={1}
              activeDot={false} isAnimationActive={false} />
            <Area dataKey="surplus" stroke="none" fill={COLORS.surplusFill} fillOpacity={1}
              activeDot={false} isAnimationActive={false} />
            {others && day.other_publishes.map((p, i) => (
              <Line key={p.publish_time} dataKey={`p${i}`} stroke={COLORS.otherPublish}
                strokeOpacity={p.after_decision ? 0.55 : 0.4} strokeWidth={1}
                strokeDasharray={p.after_decision ? '5 3' : undefined}
                dot={false} activeDot={false} isAnimationActive={false} connectNulls />
            ))}
            <Line dataKey="actual" stroke={COLORS.actual} strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line dataKey="forecast" stroke={COLORS.forecast} strokeWidth={3.5} dot={false} isAnimationActive={false} />
            {adjusted && (
              <Line dataKey="adjusted" stroke={COLORS.adjusted} strokeWidth={2} dot={false} isAnimationActive={false}
                connectNulls />
            )}
          </ComposedChart>
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
  const { date, cutoff, adjusted, others } = state
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
        <label className="control toggle">
          <input type="checkbox" checked={others} onChange={(e) => update({ others: e.target.checked })} />
          <span>Show other forecasts for this day</span>
        </label>
      </div>

      <Loadable state={day} retry={retry} isEmpty={(d) => d.rows.length === 0}>
        {(d) => <DayView day={d} adjusted={adjusted} others={others} />}
      </Loadable>
    </>
  )
}
