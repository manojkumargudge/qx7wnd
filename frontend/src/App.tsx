import { Accuracy } from './tabs/Accuracy'
import { DecisionDay } from './tabs/DecisionDay'
import { Method } from './tabs/Method'
import { useUrlState, type Tab } from './state'

const TAB_LABELS: Record<Tab, string> = {
  day: 'Decision day',
  accuracy: 'Forecast accuracy (January)',
  method: 'Method & assumptions',
}

function App() {
  const { state, update, notices, dismissNotices } = useUrlState()

  return (
    <div className="app">
      <header className="header">
        <h1>WindGap</h1>
        <p className="tagline">How far off was the day-ahead UK wind forecast when you had to commit?</p>
        <p className="tz">All times UTC (same as UK time in January).</p>
      </header>

      {notices.length > 0 && (
        <div className="notice" role="status">
          <span>{notices.join('. ')}.</span>
          <button type="button" className="notice-close" aria-label="Dismiss" onClick={dismissNotices}>×</button>
        </div>
      )}

      <nav className="tabs" role="tablist">
        {(Object.keys(TAB_LABELS) as Tab[]).map((t) => (
          <button key={t} type="button" role="tab" aria-selected={state.tab === t}
            className={state.tab === t ? 'tab active' : 'tab'} onClick={() => update({ tab: t })}>
            {TAB_LABELS[t]}
          </button>
        ))}
      </nav>

      <main>
        {state.tab === 'day' && <DecisionDay state={state} update={update} />}
        {state.tab === 'accuracy' && <Accuracy state={state} update={update} />}
        {state.tab === 'method' && <Method />}
      </main>
    </div>
  )
}

export default App
