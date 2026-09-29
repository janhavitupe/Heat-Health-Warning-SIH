import { useEffect, useState } from 'react'
import { api } from './api.js'
import DaySlider from './components/DaySlider.jsx'
import Legend from './components/Legend.jsx'
import MapView from './components/MapView.jsx'
import WardList from './components/WardList.jsx'
import AlertsTab from './components/AlertsTab.jsx'
import PlanTab from './components/PlanTab.jsx'
import ReportsTab from './components/ReportsTab.jsx'
import WhatIfTab from './components/WhatIfTab.jsx'
import MethodTab from './components/MethodTab.jsx'
import StatusStrip from './components/StatusStrip.jsx'
import WardPanel from './components/WardPanel.jsx'
import { LAYERS, ROLES } from './theme.js'

const localDay = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' })

export default function App() {
  const [replay, setReplay] = useState(() => new URLSearchParams(location.search).get('replay'))
  const [role, setRole] = useState('municipal')
  const [layer, setLayer] = useState(() => {       // ?layer=cooling etc. opens a specific map layer
    const l = new URLSearchParams(location.search).get('layer')
    return l && LAYERS[l] ? l : ROLES.municipal.layer
  })
  const [days, setDays] = useState(null)
  const [day, setDay] = useState(null)
  const [wards, setWards] = useState(null)
  const [selected, setSelected] = useState(null)
  const [tab, setTab] = useState(() => (['ward', 'list', 'plan', 'alerts', 'whatif', 'reports', 'method'].includes(new URLSearchParams(location.search).get('tab')) ? new URLSearchParams(location.search).get('tab') : 'ward'))
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)            // e.g. live forecast unavailable, replay shown instead
  const [cooling, setCooling] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)      // bumped after alert actions to refresh the status strip
  const [armed, setArmed] = useState(false)             // what-if: next map click places a cooling centre
  const [point, setPoint] = useState(null)

  useEffect(() => {                       // keep the URL shareable: ?replay=may2024
    const q = new URLSearchParams(location.search)
    if (replay) q.set('replay', replay)
    else q.delete('replay')
    history.replaceState(null, '', `${location.pathname}${q.size ? `?${q}` : ''}`)
    let current = true                    // ignore answers that arrive after the mode changed
    api.days(replay).then((d) => { if (current) { setError(null); setDays(d); setDay(d.default_day) } })
      .catch((e) => {
        if (!current) return
        if (!replay && e.message.startsWith('503')) {   // no live forecast yet: show the replay instead
          setNotice('The live forecast is not available right now (the free weather service is limiting this server; it retries every hour). Showing the May 2024 heatwave replay instead.')
          setReplay('may2024')
        } else setError(e.message)
      })
    return () => { current = false }
  }, [replay])

  const chooseMode = (r) => {
    if (r === replay) return
    setDays(null); setWards(null); setDay(null); setError(null); setNotice(null); setReplay(r)
  }

  useEffect(() => {
    if (!day) return
    let current = true
    api.wards(day, replay).then((w) => {
      if (!current) return
      setWards(w)
      setSelected((s) => s ?? [...w.features].sort((a, b) => b.properties.mri - a.properties.mri)[0].properties.ward_id)
    }).catch((e) => current && setError(e.message))
    return () => { current = false }
  }, [day, replay])

  useEffect(() => {                       // cooling places and recommended sites, fetched once when first needed
    if ((layer === 'cooling' || tab === 'whatif') && !cooling) api.cooling().then(setCooling).catch((e) => setError(e.message))
  }, [layer, tab, cooling])

  const chooseRole = (r) => { setRole(r); setLayer(ROLES[r].layer) }
  const target = layer === 'hri' || (role === 'healthcare' && LAYERS[layer].kind !== 'alert') ? 'hri' : 'mri'
  const meta = days?.meta
  const hasConfidence = wards?.features.some((f) => f.properties.confidence)
  const updated = meta?.scores_updated ? new Date(meta.scores_updated).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : null

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Ahmedabad Heat-Health Risk</h1>
          <div className="sub">{meta ? (replay ? `${meta.title} (replay)` : `Live forecast · updated ${updated}`) : 'Loading…'}</div>
        </div>
        <div className="seg" role="group" aria-label="Data">
          <button aria-pressed={!replay} onClick={() => chooseMode(null)}>Live</button>
          <button aria-pressed={replay === 'may2024'} onClick={() => chooseMode('may2024')}>May 2024 replay</button>
        </div>
        <div className="seg" role="group" aria-label="Role">
          {Object.entries(ROLES).map(([k, r]) => <button key={k} aria-pressed={role === k} onClick={() => chooseRole(k)}>{r.label}</button>)}
        </div>
        <div className="spacer" />
        <span className="estimate">Model estimates, not clinical predictions</span>
      </header>

      <StatusStrip day={day} replay={replay} role={role} refreshKey={refreshKey} onOpenAlerts={() => setTab('alerts')} />
      {error && <div className="banner" role="alert">Data unavailable: {error}</div>}
      {notice && <div className="banner notice" role="status">{notice}</div>}

      <div className="main">
        <div className="mapcol">
          <div className="toolbar">
            <label htmlFor="layer">Map layer</label>
            <select id="layer" value={layer} onChange={(e) => setLayer(e.target.value)}>
              {Object.entries(LAYERS).map(([k, l]) => <option key={k} value={k}>{l.label}</option>)}
            </select>
            <span className="layer-help">{LAYERS[layer].help}</span>
          </div>
          <div style={{ position: 'relative', minHeight: 0, display: 'grid' }}>
            <MapView data={wards} layer={layer} selected={selected} cooling={layer === 'cooling' ? cooling : null}
              armed={armed} point={tab === 'whatif' ? point : null}
              onMapClick={(p) => { setPoint(p); setArmed(false) }}
              onSelect={(id) => { setSelected(id); if (tab !== 'whatif' && tab !== 'reports') setTab('ward') }} />
            <Legend layer={layer} hasConfidence={hasConfidence} />
          </div>
          {days && <DaySlider days={days.days} day={day} today={replay ? null : localDay()} onChange={setDay} />}
        </div>

        <aside className="panel" aria-label="Details">
          <div className="tabs" role="group" aria-label="Panel view">
            <button aria-pressed={tab === 'ward'} onClick={() => setTab('ward')}>Ward</button>
            <button aria-pressed={tab === 'list'} onClick={() => setTab('list')}>All wards</button>
            <button aria-pressed={tab === 'plan'} onClick={() => setTab('plan')}>Plan</button>
            <button aria-pressed={tab === 'alerts'} onClick={() => setTab('alerts')}>Alerts</button>
            <button aria-pressed={tab === 'whatif'} onClick={() => setTab('whatif')}>What-if</button>
            <button aria-pressed={tab === 'reports'} onClick={() => setTab('reports')}>Reports</button>
            <button aria-pressed={tab === 'method'} onClick={() => setTab('method')}>Method</button>
          </div>
          {tab === 'method' && <MethodTab replay={replay} />}
          {tab === 'whatif' && <WhatIfTab wards={wards} selected={selected} point={point} armed={armed} onArm={setArmed} cooling={cooling} />}
          {tab === 'reports' && day && <ReportsTab wards={wards} day={day} replay={replay} selected={selected} onChanged={() => setRefreshKey((k) => k + 1)} />}
          {tab === 'alerts' && <AlertsTab replay={replay} onChanged={() => setRefreshKey((k) => k + 1)} />}
          {tab === 'plan' && day && <PlanTab day={day} replay={replay} role={role} onSelect={(id) => { setSelected(id); setTab('ward') }} />}
          {tab === 'list' && <WardList data={wards} layer={layer} onSelect={(id) => { setSelected(id); setTab('ward') }} />}
          {tab === 'ward' && selected && day && <WardPanel wardId={selected} day={day} target={target} replay={replay} />}
        </aside>
      </div>
    </div>
  )
}
