import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip,
  XAxis, YAxis,
} from 'recharts'
import { api, type AccuracyResponse, type Summary, type TimeseriesResponse } from '../api'
import { COLORS } from '../colors'
import { ChartCard, CutoffSelect, KpiCard, LegendItem, Loadable } from '../components/ui'
import {
  biasSentence, formatDay, formatHour, formatK, formatMW, formatSignedMW, p10Sentence, p90Sentence,
} from '../format'
import { binValues } from '../histogram'
import { compareDays, comparisonPhrase } from '../stats'
import { useFetch, type UrlState } from '../state'

const HISTOGRAM_BIN_MW = 500
const HISTOGRAM_TICK_MW = 2000
const DAY_MS = 86_400_000

const mwTooltip = (v: number, name: string) => [formatMW(v), name]

function Kpis({ s }: { s: Summary }) {
  return (
    <div className="kpis kpis-5">
      <KpiCard label="Average miss (MAE)" value={formatMW(s.mae)} note="Typical size of the hourly gap" />
      <KpiCard label="RMSE" value={formatMW(s.rmse)} note="Like MAE, but big misses count more" />
      <KpiCard label="Bias" value={formatSignedMW(s.bias)} note={biasSentence(s.bias)} />
      <KpiCard label="P90 error" value={formatSignedMW(s.p90)} note={p90Sentence(s.p90)} />
      <KpiCard label="P10 error" value={formatSignedMW(s.p10)} note={p10Sentence(s.p10)} />
    </div>
  )
}

function TimeseriesChart({ ts }: { ts: TimeseriesResponse }) {
  const data = ts.points.map((p) => ({ t: Date.parse(p.start_time), actual: p.actual_mw, forecast: p.forecast_mw }))
  const ticks: number[] = []
  for (let t = data[0].t; t <= data[data.length - 1].t; t += 7 * DAY_MS) ticks.push(t)
  return (
    <ChartCard title="Hourly forecast vs actual, whole period"
      caption="Each delivery day uses the forecast that was available at the decision deadline the day before.">
      <div className="legend">
        <LegendItem color={COLORS.actual} label="Actual wind" />
        <LegendItem color={COLORS.forecast} label="Forecast used" />
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 8 }}>
          <CartesianGrid stroke={COLORS.grid} vertical={false} />
          <XAxis dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']} ticks={ticks}
            tickFormatter={(t: number) => formatDay(new Date(t).toISOString())} tick={{ fontSize: 12 }} />
          <YAxis tickFormatter={formatK} width={40} tick={{ fontSize: 12 }} />
          <Tooltip labelFormatter={(t: number) => {
            const d = new Date(t).toISOString()
            return `${formatDay(d)} ${d.slice(11, 16)}`
          }} formatter={mwTooltip} />
          <Line dataKey="actual" name="Actual" stroke={COLORS.actual} strokeWidth={1.25} dot={false} isAnimationActive={false} />
          <Line dataKey="forecast" name="Forecast" stroke={COLORS.forecast} strokeWidth={1.25} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

function MaeBiasBars({ data, xKey, xFormat, height = 240 }: {
  data: object[]
  xKey: string
  xFormat?: (v: string | number) => string
  height?: number
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 8 }}>
        <CartesianGrid stroke={COLORS.grid} vertical={false} />
        <XAxis dataKey={xKey} tickFormatter={xFormat} tick={{ fontSize: 12 }} />
        <YAxis tickFormatter={formatK} width={40} tick={{ fontSize: 12 }} />
        <Tooltip formatter={mwTooltip} labelFormatter={xFormat} />
        <Legend wrapperStyle={{ fontSize: 13 }} />
        <ReferenceLine y={0} stroke="#6b7280" />
        <Bar dataKey="mae" name="Average miss (MAE)" fill={COLORS.mae} isAnimationActive={false} />
        <Bar dataKey="bias" name="Bias (+ = forecast too high)" fill={COLORS.tooHigh} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function Histogram({ ts }: { ts: TimeseriesResponse }) {
  const errors = ts.points.map((p) => p.forecast_mw - p.actual_mw)
  const bins = binValues(errors, HISTOGRAM_BIN_MW).map((b) => ({ ...b, mid: b.start + HISTOGRAM_BIN_MW / 2 }))
  const label = (b: { start: number; end: number }) =>
    `${formatSignedMW(b.start)} to ${formatSignedMW(b.end)}`
  const tooHighShare = Math.round((100 * errors.filter((e) => e > 0).length) / errors.length)
  const ticks: number[] = []
  if (bins.length) {
    const step = HISTOGRAM_TICK_MW
    for (let t = Math.ceil(bins[0].start / step) * step; t <= bins[bins.length - 1].end; t += step) ticks.push(t)
  }
  return (
    <ChartCard title="How big were the hourly misses?"
      caption={`Number of hours by error (forecast − actual), in ${HISTOGRAM_BIN_MW} MW steps. ` +
        `The forecast was too high in ${tooHighShare}% of hours (red).`}>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={bins} margin={{ top: 8, right: 12, bottom: 0, left: 8 }} barCategoryGap={1}>
          <CartesianGrid stroke={COLORS.grid} vertical={false} />
          <XAxis dataKey="mid" type="number" domain={[bins[0].start, bins[bins.length - 1].end]}
            ticks={ticks} tickFormatter={formatK} tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} width={40} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(v: number) => [`${v} hours`, 'Count']}
            labelFormatter={(_, p) => (p?.[0] ? label(p[0].payload as { start: number; end: number }) : '')} />
          <ReferenceLine x={0} stroke="#6b7280" />
          <Bar dataKey="count" isAnimationActive={false}>
            {bins.map((b) => <Cell key={b.start} fill={b.start >= 0 ? COLORS.tooHigh : COLORS.tooLow} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

function tailNote(raw: Summary, adj: Summary, name: string): string {
  const below = adj.p90 < raw.p90 ? 'shrinks' : 'does not shrink'
  const above = adj.p10 < raw.p10 ? 'widens' : 'does not widen'
  return `${name} ${below} the “wind below forecast” tail (P90 ${formatSignedMW(raw.p90)} → ${formatSignedMW(adj.p90)}) ` +
    `and ${above} the “wind above forecast” tail (P10 ${formatSignedMW(raw.p10)} → ${formatSignedMW(adj.p10)}).`
}

function Corrected({ acc }: { acc: AccuracyResponse }) {
  const rows: [string, Summary][] = [
    ['Forecast as published', acc.summary],
    ['Additive adjustment', acc.corrected.additive],
    ['Ratio adjustment (default)', acc.corrected.ratio],
  ]
  return (
    <section className="card">
      <h3>Bias-adjusted forecast (experimental)</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Forecast</th><th>MAE</th><th>RMSE</th><th>Bias</th><th>P10</th><th>P90</th></tr>
          </thead>
          <tbody>
            {rows.map(([name, s]) => (
              <tr key={name}>
                <th scope="row">{name}</th>
                <td>{formatMW(s.mae)}</td>
                <td>{formatMW(s.rmse)}</td>
                <td>{formatSignedMW(s.bias)}</td>
                <td>{formatSignedMW(s.p10)}</td>
                <td>{formatSignedMW(s.p90)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="notes">
        <li>
          Each day’s adjustment is learned only from days D-8 to D-2, which are fully known before the
          deadline on D-1. Nothing from the delivery day or the day before is used.
        </li>
        <li>
          Additive subtracts last week’s average error. Ratio scales the forecast by last week’s
          actual ÷ forecast.
        </li>
        <li>
          At the {acc.cutoff} deadline, the additive adjustment {comparisonPhrase(compareDays(acc.daily, 'additive'))};
          the ratio adjustment {comparisonPhrase(compareDays(acc.daily, 'ratio'))}.
        </li>
        <li>{tailNote(acc.summary, acc.corrected.ratio, 'The ratio adjustment')}</li>
        <li>
          In other words, it cuts the risk of planning for wind that doesn’t arrive, but adds risk of
          under-planning when last week’s gap doesn’t repeat.
        </li>
        <li>The ratio method was chosen as default after seeing these January results.</li>
      </ul>
    </section>
  )
}

export function Accuracy({ state, update }: { state: UrlState; update: (p: Partial<UrlState>) => void }) {
  const { cutoff } = state
  const acc = useFetch((signal) => api.accuracy(cutoff, signal), cutoff)
  const ts = useFetch((signal) => api.timeseries(cutoff, signal), cutoff)

  return (
    <>
      <div className="controls">
        <CutoffSelect value={cutoff} onChange={(v) => update({ cutoff: v })} />
      </div>

      <Loadable state={acc.state} retry={acc.retry} isEmpty={(a) => a.summary.n === 0}>
        {(a) => <Kpis s={a.summary} />}
      </Loadable>

      <Loadable state={ts.state} retry={ts.retry} isEmpty={(t) => t.points.length === 0}>
        {(t) => (
          <>
            <TimeseriesChart ts={t} />
            <Histogram ts={t} />
          </>
        )}
      </Loadable>

      <Loadable state={acc.state} retry={acc.retry} isEmpty={(a) => a.daily.length === 0}>
        {(a) => (
          <>
            <ChartCard title="Daily average miss and bias">
              <MaeBiasBars data={a.daily} xKey="date" xFormat={(v) => formatDay(String(v))} />
            </ChartCard>
            <ChartCard title="By hour of day"
              caption="Average miss and bias for each delivery hour, across all days.">
              <MaeBiasBars data={a.by_hour_of_day} xKey="hour" xFormat={(v) => formatHour(Number(v))} />
            </ChartCard>
            <ChartCard title="By how far ahead the forecast was made (0–48 h)"
              caption="Bias stays high even for very short lead times, so most error is a steady offset, not weather uncertainty. Uses every published forecast, not just the one at the deadline.">
              <MaeBiasBars data={a.by_lead_bucket} xKey="lead_bucket" xFormat={(v) => `${v} h`} />
            </ChartCard>
            <Corrected acc={a} />
          </>
        )}
      </Loadable>
    </>
  )
}
