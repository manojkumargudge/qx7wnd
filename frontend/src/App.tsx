import { useEffect, useState } from 'react'
import { getHealth, getMeta, type Health, type Meta } from './api'

type Load<T> = { state: 'loading' } | { state: 'ok'; data: T } | { state: 'error'; message: string }

function useLoad<T>(fn: () => Promise<T>): Load<T> {
  const [result, setResult] = useState<Load<T>>({ state: 'loading' })
  useEffect(() => {
    fn()
      .then((data) => setResult({ state: 'ok', data }))
      .catch((err: Error) => setResult({ state: 'error', message: err.message }))
  }, [fn])
  return result
}

function App() {
  const health = useLoad<Health>(getHealth)
  const meta = useLoad<Meta>(getMeta)

  return (
    <main>
      <h1>UK wind forecast accuracy</h1>

      <section>
        <h2>API health</h2>
        {health.state === 'loading' && <p>Loading…</p>}
        {health.state === 'error' && <p className="error">{health.message}</p>}
        {health.state === 'ok' && <p>Status: <strong>{health.data.status}</strong></p>}
      </section>

      <section>
        <h2>Metadata</h2>
        {meta.state === 'loading' && <p>Loading…</p>}
        {meta.state === 'error' && <p className="error">{meta.message}</p>}
        {meta.state === 'ok' && (
          <dl>
            <dt>Delivery days</dt>
            <dd>{meta.data.delivery_start} to {meta.data.delivery_end}</dd>
            <dt>Default cutoff</dt>
            <dd>{meta.data.default_cutoff} UTC on the day before delivery</dd>
            <dt>Publish times seen</dt>
            <dd>{meta.data.publish_times_of_day.join(', ')}</dd>
            <dt>Correction</dt>
            <dd>
              {meta.data.correction_methods.join(' / ')} (default:{' '}
              {meta.data.default_correction_method}). {meta.data.correction_note}
            </dd>
            <dt>Data source</dt>
            <dd>{meta.data.data_source}</dd>
            <dt>Time zone</dt>
            <dd>{meta.data.timezone}</dd>
          </dl>
        )}
      </section>
    </main>
  )
}

export default App
