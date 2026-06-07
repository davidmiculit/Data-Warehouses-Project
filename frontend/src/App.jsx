import { useState, useEffect, createContext, useContext, useCallback } from 'react'
import { api } from './api.js'
import { Icon } from './components/icons.jsx'
import Dashboard from './components/Dashboard.jsx'
import Assets from './components/Assets.jsx'
import DataSources from './components/DataSources.jsx'
import TimeSeries from './components/TimeSeries.jsx'
import Analytics from './components/Analytics.jsx'
import Ingest from './components/Ingest.jsx'
import Assistant from './components/Assistant.jsx'

const NAV = [
  {
    label: 'Overview',
    items: [{ id: 'dashboard', label: 'Dashboard', icon: 'dashboard', el: Dashboard }],
  },
  {
    label: 'Warehouse',
    items: [
      { id: 'assets', label: 'Assets', icon: 'assets', el: Assets },
      { id: 'sources', label: 'Data Sources', icon: 'source', el: DataSources },
      { id: 'timeseries', label: 'Time Series', icon: 'series', el: TimeSeries },
    ],
  },
  {
    label: 'Insight',
    items: [
      { id: 'analytics', label: 'Analytics', icon: 'analytics', el: Analytics },
      { id: 'assistant', label: 'Assistant', icon: 'assistant', el: Assistant },
    ],
  },
  {
    label: 'Operations',
    items: [{ id: 'ingest', label: 'Ingest', icon: 'ingest', el: Ingest }],
  },
]

const ALL = NAV.flatMap((g) => g.items)

// ---- shared app context: selected asset/source + cross-view navigation ----
const Ctx = createContext(null)
export const useApp = () => useContext(Ctx)

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [healthy, setHealthy] = useState(null)
  // cross-view selection context (carried when deep-linking between views)
  const [sel, setSel] = useState({ asset: null, source: null })
  const [pending, setPending] = useState(null) // one-shot intent for a target view
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const ping = () =>
      api.health().then(() => setHealthy(true)).catch(() => setHealthy(false))
    ping()
    const h = setInterval(ping, 15000)
    const c = setInterval(() => setNow(new Date()), 1000)
    return () => { clearInterval(h); clearInterval(c) }
  }, [])

  // navigate to a view, optionally seeding selection + an intent payload
  const goto = useCallback((target, ctx = {}) => {
    setSel((s) => ({
      asset: ctx.asset !== undefined ? ctx.asset : s.asset,
      source: ctx.source !== undefined ? ctx.source : s.source,
    }))
    if (ctx.intent) setPending({ view: target, ...ctx.intent })
    setTab(target)
  }, [])

  const consumeIntent = useCallback((view) => {
    if (pending && pending.view === view) {
      const p = pending
      setPending(null)
      return p
    }
    return null
  }, [pending])

  const active = ALL.find((t) => t.id === tab) || ALL[0]
  const Active = active.el

  const ctxValue = {
    asset: sel.asset, source: sel.source,
    setAsset: (asset) => setSel((s) => ({ ...s, asset })),
    setSource: (source) => setSel((s) => ({ ...s, source })),
    goto, consumeIntent,
  }

  return (
    <Ctx.Provider value={ctxValue}>
      <div className="app">
        <aside className="sidebar">
          <div className="brand">
            <span className="brand-mark">A</span>
            <div>
              <div className="brand-title">Acme Terminal</div>
              <div className="brand-sub">Markets Data Warehouse</div>
            </div>
          </div>

          {NAV.map((group) => (
            <div className="nav-group" key={group.label}>
              <div className="nav-label">{group.label}</div>
              <nav>
                {group.items.map((t) => {
                  const I = Icon[t.icon]
                  return (
                    <button
                      key={t.id}
                      className={'nav-item' + (t.id === tab ? ' active' : '')}
                      onClick={() => setTab(t.id)}
                    >
                      <I className="ico" size={17} />
                      <span>{t.label}</span>
                    </button>
                  )
                })}
              </nav>
            </div>
          ))}

          <div className="side-foot">
            <div className="temporal-note">
              Bi-temporal store · records are immutable; history is preserved and replayable.
            </div>
            <div className="health">
              <span className={'dot ' + (healthy ? 'ok' : healthy === false ? 'bad' : '')} />
              <span>
                {healthy == null ? 'connecting…' : healthy ? 'API online' : 'API offline'}
              </span>
            </div>
          </div>
        </aside>

        <div className="main">
          <header className="topbar">
            <div className="crumb">
              {active.label === 'Dashboard' ? (
                <b>Overview</b>
              ) : (
                <>
                  <span>Acme</span><span>/</span><b>{active.label}</b>
                </>
              )}
            </div>
            <div className="topbar-spacer" />
            {sel.asset && (
              <span className="chip click" onClick={() => goto('timeseries')}>
                <Icon.assets size={13} /> {sel.asset}
              </span>
            )}
            <div className="clock">
              <Icon.clock size={14} />
              <span className="lbl">system time</span>
              {now.toLocaleTimeString(undefined, { hour12: false })}
            </div>
          </header>

          <main className="view">
            <div className="view-inner" key={tab}>
              <Active />
            </div>
          </main>
        </div>
      </div>
    </Ctx.Provider>
  )
}
