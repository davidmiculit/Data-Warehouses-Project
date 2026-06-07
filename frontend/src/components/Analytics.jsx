import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useApp } from '../App.jsx'
import { Header, Panel, Spinner, ErrorBox, Field, Empty, Badge, fmt, fmtCompact, pct } from './ui.jsx'
import { Icon } from './icons.jsx'
import LineChart from './Chart.jsx'

export default function Analytics() {
  const app = useApp()
  const [assets, setAssets] = useState([])
  const [sources, setSources] = useState([])
  const [sel, setSel] = useState({ assetId: app.asset || '', dataSourceId: app.source || '' })
  const [totals, setTotals] = useState(null)
  const [preds, setPreds] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [running, setRunning] = useState(null) // 'aggregation' | 'regression' | null
  const [jobResult, setJobResult] = useState(null)

  useEffect(() => {
    api.listAssets(0, 1000).then((a) => {
      setAssets(a)
      setSel((s) => ({ ...s, assetId: s.assetId || a[0] || '' }))
    }).catch(() => {})
    api.listDataSources(0, 1000).then((s) => {
      setSources(s)
      setSel((x) => ({ ...x, dataSourceId: x.dataSourceId || (s.includes('BITFINEX') ? 'BITFINEX' : s[0]) || '' }))
    }).catch(() => {})
  }, [])

  const load = () => {
    if (!sel.assetId || !sel.dataSourceId) return
    setLoading(true)
    setError(null)
    setTotals(null)
    setPreds(null)
    Promise.all([
      api.totals(sel.assetId, sel.dataSourceId),
      api.predictions(sel.assetId, sel.dataSourceId, 500),
    ])
      .then(([t, p]) => { setTotals(t); setPreds(p) })
      .catch(setError)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (sel.assetId && sel.dataSourceId && totals == null && !loading) load()
  }, [sel.assetId, sel.dataSourceId]) // eslint-disable-line

  const runJob = (job) => {
    if (running) return
    setRunning(job)
    setError(null)
    setJobResult(null)
    api
      .runJob(job, sel.assetId, sel.dataSourceId)
      .then((r) => { setJobResult(r); load() }) // reload tables after the job writes
      .catch(setError)
      .finally(() => setRunning(null))
  }

  // regression accuracy: mean abs % error
  const mape = preds && preds.length
    ? (preds.filter((p) => p.open && p.prediction).reduce((a, p) => a + Math.abs((p.prediction - p.open) / p.open), 0) /
        preds.filter((p) => p.open && p.prediction).length) * 100
    : null

  const predSeries = preds
    ? [
        { color: 'var(--muted)', points: preds.map((p) => ({ y: p.open })) },
        { color: 'var(--accent)', points: preds.map((p) => ({ y: p.prediction })) },
      ]
    : []

  return (
    <>
      <Header title="Analytics & Forecasting" subtitle="Spark aggregation (per-year totals) and an ML regression that predicts the daily open — computed in Spark, persisted back into the warehouse." />

      <form className="toolbar" onSubmit={(e) => { e.preventDefault(); load() }}>
        <Field label="Asset">
          <select value={sel.assetId} onChange={(e) => setSel({ ...sel, assetId: e.target.value })}>
            {assets.map((a) => <option key={a}>{a}</option>)}
          </select>
        </Field>
        <Field label="Data source">
          <select value={sel.dataSourceId} onChange={(e) => setSel({ ...sel, dataSourceId: e.target.value })}>
            {sources.map((s) => <option key={s}>{s}</option>)}
          </select>
        </Field>
        <button className="btn primary" type="submit"><Icon.refresh size={14} /> Load</button>
      </form>

      <Panel eyebrow="Apache Spark pipeline" title="Run workloads on demand">
        <p className="muted small" style={{ margin: '0 0 14px' }}>
          These launch the real Spark jobs inside the <span className="mono">acme-spark</span> container and write results
          back into the warehouse. A run takes ~20–60s; results upsert, so it's safe to re-run.
        </p>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <button className="btn" disabled={!!running} onClick={() => runJob('aggregation')}>
            <Icon.analytics size={14} />
            {running === 'aggregation' ? 'Running aggregation…' : 'Run aggregation (all pairs)'}
          </button>
          <button className="btn" disabled={!!running} onClick={() => runJob('regression')}>
            <Icon.series size={14} />
            {running === 'regression' ? 'Running regression…' : `Run regression (${sel.assetId || '—'})`}
          </button>
          {running && <span className="spinner" style={{ padding: 0 }}><span className="ring" /> Spark job in progress — this can take up to a minute.</span>}
        </div>
        {jobResult && (
          <div className="notice" style={{ marginTop: 14, marginBottom: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Badge kind="up">done in {jobResult.durationSec}s</Badge>
              <span className="mono small">{jobResult.summary || 'job finished'}</span>
            </div>
          </div>
        )}
      </Panel>

      {loading && <Spinner label="Reading Spark outputs…" />}
      <ErrorBox error={error} />

      {totals && (
        <Panel eyebrow="Spark aggregation · totals table" title="Per-year close statistics">
          {totals.length === 0 ? (
            <Empty icon="analytics">No aggregates for this pair yet — run the Spark aggregation job (see README).</Empty>
          ) : (
            <>
              <div className="grid cols-4" style={{ marginBottom: 16 }}>
                <Mini label="Years covered" value={totals.length} />
                <Mini label="Data points" value={fmtCompact(totals.reduce((a, t) => a + t.count, 0))} />
                <Mini label="All-time low" value={fmtCompact(Math.min(...totals.map((t) => t.minClose)))} accent="down" />
                <Mini label="All-time high" value={fmtCompact(Math.max(...totals.map((t) => t.maxClose)))} accent="up" />
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>year</th><th className="num">count</th><th className="num">min close</th><th className="num">max close</th><th className="num">avg close</th><th className="num">range</th></tr>
                  </thead>
                  <tbody>
                    {totals.map((t) => {
                      const span = t.maxClose && t.minClose ? ((t.maxClose - t.minClose) / t.minClose) * 100 : null
                      return (
                        <tr key={t.year}>
                          <td className="mono">{t.year}</td>
                          <td className="num">{t.count}</td>
                          <td className="num">{fmt(t.minClose)}</td>
                          <td className="num">{fmt(t.maxClose)}</td>
                          <td className="num">{fmt(t.avgClose)}</td>
                          <td className="num up">{span == null ? '—' : pct(span)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Panel>
      )}

      {preds && preds.length > 0 && (
        <Panel
          eyebrow="Spark ML · regression_results table"
          title="Predicted vs. actual daily open"
          actions={mape != null && <span className="chip">MAPE {mape.toFixed(2)}%</span>}
        >
          <LineChart series={predSeries} format={fmtCompact} />
          <div className="x-axis">
            <span>{preds[0].businessDate}</span>
            <span>{preds[preds.length - 1].businessDate}</span>
          </div>
          <div className="legend">
            <span className="lg"><i style={{ background: 'var(--muted)' }} /> actual open</span>
            <span className="lg"><i style={{ background: 'var(--accent)' }} /> predicted open</span>
            <span className="lg muted">{preds.length} test points</span>
          </div>
        </Panel>
      )}
      {preds && preds.length === 0 && totals && totals.length > 0 && (
        <Panel><Empty icon="analytics">No predictions for this pair yet — run the Spark regression job (see README).</Empty></Panel>
      )}
    </>
  )
}

function Mini({ label, value, accent }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className={'kpi-val ' + (accent || '')} style={{ fontSize: 22 }}>{value}</div>
    </div>
  )
}
