import { api } from '../api'
import { Loadable } from '../components/ui'
import { formatDay } from '../format'
import { useFetch } from '../state'

export function Method() {
  const { state: meta, retry } = useFetch((signal) => api.meta(signal), 'meta')

  return (
    <section className="card prose">
      <h3>Method &amp; assumptions</h3>
      <ul>
        <li>
          <strong>Data.</strong> Actual wind generation is Elexon BMRS <em>FUELHH</em> (fuel type WIND).
          Forecasts are Elexon BMRS <em>WINDFOR</em>, National Grid ESO’s national wind forecast.
        </li>
        <li>
          <strong>The decision.</strong> A buyer must commit the day before delivery. For each delivery
          day we use the latest forecast published at or before the deadline (default 09:00) on the
          previous day. Forecasts published after the deadline are shown for context only.
        </li>
        <li>
          <strong>Delivery day.</strong> 00:00 to 23:00 UTC. In January UTC is the same as UK time.
        </li>
        <li>
          <strong>Hourly alignment.</strong> Actuals are reported every half hour and forecasts every hour,
          so each hour’s actual is the average of its two half-hours.
        </li>
        <li>
          <strong>Error</strong> is forecast minus actual, in MW. Positive means the forecast was too high.
          <ul>
            <li><strong>MAE</strong>: the average size of the miss, ignoring direction.</li>
            <li><strong>RMSE</strong>: like MAE, but large misses count more.</li>
            <li><strong>Bias</strong>: the average error, keeping direction. It shows a steady lean one way.</li>
            <li>
              <strong>P10 / P90</strong>: 10% of hours had an error below P10, and 10% above P90.
            </li>
            <li>Percentage errors are not shown, because actual wind can be close to zero.</li>
          </ul>
        </li>
        <li>
          <strong>Bias adjustment (experimental).</strong> Each day’s adjustment is learned from the seven
          days D-8 to D-2 only, so it uses nothing the buyer could not have known at the deadline. It
          assumes last week’s gap will repeat. When the weather pattern changes, it can overshoot. The
          default (ratio) was chosen after looking at these same January results, so its score here
          is probably a little optimistic.
        </li>
        <li>
          <strong>The gap.</strong> Over January the forecast ran about 14% above actual generation.
          That fits wind farms being turned down (curtailment) when the grid can’t take their power, but
          these datasets can’t show it. Curtailment data is outside the scope of this tool.
        </li>
      </ul>

      <Loadable state={meta} retry={retry}>
        {(m) => (
          <>
            <h4>Forecast publishing schedule</h4>
            <p>
              Forecasts are normally published at {m.publish_times_of_day.join(', ')} UTC.
              {m.irregular_publishes.length > 0 && (
                <> Irregular publishes: {m.irregular_publishes
                  .map((p) => `${p.time} on ${p.dates.map(formatDay).join(', ')}`).join('; ')}.</>
              )}
            </p>
            <p className="caption">{m.data_source}</p>
          </>
        )}
      </Loadable>
    </section>
  )
}
