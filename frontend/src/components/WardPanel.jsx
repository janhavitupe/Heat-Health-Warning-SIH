import { useEffect, useState } from 'react'
import {
  Area, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../api.js'
import { ALERTS, ALERT_COLOR, ALERT_LABEL, DATA_LABELS, SERIES } from '../theme.js'
import { Actions, Advisories, WorkWindows } from './DecisionSections.jsx'

const dark = window.matchMedia?.('(prefers-color-scheme: dark)').matches
const S = dark ? SERIES.dark : SERIES.light
const INK2 = dark ? '#c3c2b7' : '#52514e'
const GRID = dark ? '#2c2c2a' : '#e1e0d9'
const GROUPS = { heat: { label: 'Heat', color: S[0] }, vulnerability: { label: 'Vulnerability', color: S[2] }, factor: { label: 'Local factor', color: S[1] } }
const PVI_NAMES = {
  elderly_share: 'Elderly (60+)', outdoor_worker_share: 'Outdoor workers', healthcare_access_gap: 'Walk to health care',
  informal_housing_share: 'Slum population', under5_share: 'Children under 5', population_density: 'Population density',
  cooling_access_gap: 'Far from cooling places',
}
const shortDate = (d) => new Date(`${d}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
const axis = { stroke: GRID, tick: { fill: INK2, fontSize: 11 }, tickLine: false }

function Tip({ active, payload, label, fmt = (v) => v?.toFixed(1), title = shortDate }) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tip">
      <div className="t">{title(label)}</div>
      {payload.filter((p) => p.value !== null && p.value !== undefined && !Array.isArray(p.value)).map((p) => (
        <div className="r" key={p.dataKey}><span className="k" style={{ background: p.color }} /><b>{fmt(p.value, p)}</b> {p.name}</div>
      ))}
    </div>
  )
}

function Contributions({ ex }) {
  if (!ex) return null
  const rows = ex.contributions.filter((c) => Math.abs(c.points) >= 0.05 || c.note)
  const max = Math.max(1, ...rows.map((c) => Math.abs(c.points)))
  return (
    <>
      <div className="groupkey">{Object.values(GROUPS).map((g) => <span key={g.label} style={{ '--c': g.color }}>{g.label}</span>)}</div>
      {rows.map((c) => {
        const w = (Math.abs(c.points) / max) * 70           // positive bars use 70% of the track, negative 30%
        return (
          <div className="contrib" key={c.key}>
            <div className="name">{c.label}<span className="tag">{DATA_LABELS[c.data_label] ?? c.data_label}</span>
              {c.note && <span className="note">{c.note}</span>}</div>
            <div className="track" aria-hidden="true"><span className="zero" />
              <span className="fill" style={{ background: GROUPS[c.group]?.color, width: `${c.points >= 0 ? w : (w * 30) / 70}%`,
                left: c.points >= 0 ? '30%' : `${30 - (w * 30) / 70}%` }} /></div>
            <div className="pts">{c.points >= 0 ? '+' : '−'}{Math.abs(c.points).toFixed(1)}</div>
          </div>
        )
      })}
    </>
  )
}

export default function WardPanel({ wardId, day, target, replay }) {
  const [ward, setWard] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let live = true
    api.ward(wardId, replay)
      .then((w) => { if (live) { setError(null); setWard(w) } })
      .catch((e) => { if (live) setError(e.message) })
    return () => { live = false }
  }, [wardId, replay])

  if (error) return <p className="empty">Could not load ward: {error}</p>
  if (!ward || ward.ward_id !== wardId) return <p className="empty">Loading…</p>

  const row = ward.daily.find((d) => d.date === day) ?? ward.daily.at(-1)
  const ex = row[`explanation_${target}`]
  const lvl = row[`alert_${target}`]
  const hasProbs = ward.daily.some((d) => d.p_red !== undefined && d.p_red !== null)
  const traj = ward.daily.map((d) => ({ date: d.date, score: d[target], band: d.mri_p10 !== undefined && d.mri_p10 !== null ? [d.mri_p10, d.mri_p90] : null }))
  const probs = ward.daily.filter((d) => d.p_red !== undefined && d.p_red !== null).map((d) => ({
    date: d.date, red: d.p_red, orange: d.p_orange - d.p_red, yellow: d.p_yellow - d.p_orange, green: 1 - d.p_yellow }))
  const hours = ward.hourly.filter((h) => h.time.startsWith(row.date)).map((h) => ({ ...h, hour: h.time.slice(11, 16) }))
  const a = ward.attributes
  const pct = (v) => (v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`)

  return (
    <div>
      <h2>{ward.ward_name}</h2>
      <div className="meta">{ward.zone} zone · {ward.ward_id} · {new Date(`${row.date}T00:00:00`).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</div>

      <div className="kpis">
        <div className="kpi"><div className="v"><span className="badge"><span className="dot" style={{ background: ALERT_COLOR[lvl] }} />{row[target].toFixed(0)}</span></div>
          <div className="l">{target === 'hri' ? 'Hospitalization' : 'Mortality'} risk · {ALERT_LABEL[lvl]}</div></div>
        <div className="kpi"><div className="v">{row.htsi.toFixed(0)}</div><div className="l">Heat stress (HTSI) · {row.htsi_category.replace('_', ' ')}</div></div>
        <div className="kpi"><div className="v">{row.pvi.toFixed(0)}</div><div className="l">Vulnerability (PVI)</div></div>
        <div className="kpi"><div className="v">{row.tmax.toFixed(1)}°</div><div className="l">Max · min {row.tmin.toFixed(1)} °C</div></div>
        <div className="kpi"><div className="v">{pct(row.p_red)}</div><div className="l">Chance of Red{row.confidence ? ` · ${row.confidence} confidence` : ''}</div></div>
        <div className="kpi"><div className="v">{row.peak_hour ? row.peak_hour.split('–')[0] : row.hot_run_days}</div>
          <div className="l">{row.peak_hour ? `Peak hour on ${shortDate(row.peak_day)}` : 'Consecutive heat-alert days'}</div></div>
      </div>
      {ex && <p className="summary">{ex.summary}</p>}

      <h3>Why this score</h3>
      <Contributions ex={ex} />

      <h3>What to do</h3>
      <Actions wardId={wardId} day={row.date} replay={replay} />

      <h3>Safe outdoor work hours</h3>
      <WorkWindows wardId={wardId} day={row.date} replay={replay} />

      <h3>Public advisories</h3>
      <Advisories wardId={wardId} day={row.date} replay={replay} />

      <h3>{replay ? 'Risk over the event' : 'Risk over the forecast'}{hasProbs ? ' (band: 10–90% of forecast runs)' : ''}</h3>
      <div className="chart">
        <ResponsiveContainer>
          <ComposedChart data={traj} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="date" tickFormatter={shortDate} {...axis} minTickGap={24} />
            <YAxis domain={[0, 100]} ticks={[0, 40, 60, 80, 100]} {...axis} />
            {ALERTS.slice(0, 3).map((al, i) => <ReferenceLine key={al.key} y={[40, 60, 80][i]} stroke={GRID} strokeDasharray="0" />)}
            <ReferenceLine x={row.date} stroke={INK2} />
            {hasProbs && <Area dataKey="band" name="10–90% range" stroke="none" fill={S[0]} fillOpacity={0.14} isAnimationActive={false} />}
            <Line dataKey="score" name={target.toUpperCase()} stroke={S[0]} strokeWidth={2} dot={false} isAnimationActive={false} />
            <Tooltip content={<Tip fmt={(v) => v.toFixed(0)} />} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {probs.length > 0 && (<>
        <h3>Chance of each alert level</h3>
        <div className="chart">
          <ResponsiveContainer>
            <BarChart data={probs} margin={{ top: 6, right: 8, bottom: 0, left: -18 }} barCategoryGap={1}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="date" tickFormatter={shortDate} {...axis} minTickGap={24} />
              <YAxis domain={[0, 1]} tickFormatter={(v) => `${v * 100}%`} {...axis} />
              {ALERTS.map((al) => <Bar key={al.key} dataKey={al.key} name={al.label} stackId="p" fill={al.color} isAnimationActive={false} />)}
              <Legend wrapperStyle={{ fontSize: 11, color: INK2 }} iconSize={10} itemSorter={null} />
              <Tooltip content={<Tip fmt={(v) => `${Math.round(v * 100)}%`} />} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="meta">{ward.meta.probability_source}</div>
      </>)}

      {hours.length > 0 && (<>
        <h3>Through the day, {shortDate(row.date)} (°C; hour ending)</h3>
        <div className="chart">
          <ResponsiveContainer>
            <LineChart data={hours} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="hour" {...axis} interval={3} />
              <YAxis {...axis} domain={[(min) => Math.floor(min / 5) * 5, (max) => Math.ceil(max / 5) * 5]} allowDecimals={false} tickCount={5} />
              <Line dataKey="t2m" name="Air temperature" stroke={S[0]} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line dataKey="utci" name="Feels-like (UTCI)" stroke={S[1]} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line dataKey="wbgt" name="Work heat stress (WBGT)" stroke={S[2]} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Legend wrapperStyle={{ fontSize: 11, color: INK2 }} iconSize={10} itemSorter={null} />
              <Tooltip content={<Tip title={(h) => `Hour ending ${h}`} />} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </>)}

      <h3>Vulnerability breakdown (PVI {a.pvi?.toFixed(0)})</h3>
      <table className="list">
        <thead><tr><th>Indicator</th><th>Rank in city</th><th>Status</th></tr></thead>
        <tbody>
          {Object.entries(PVI_NAMES).map(([k, name]) => (
            <tr key={k} style={{ cursor: 'default' }}>
              <td>{name}</td>
              <td className="n">{a[`${k}_n`] === undefined ? '—' : `${Math.round(a[`${k}_n`] * 100)}th pct`}</td>
              <td>{a.pvi_status?.[k] === 'used' ? 'Used' : (a.pvi_status?.[k] ?? '').replace('neutral: ', 'Midpoint: ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="srcnote">Source labels: Live = weather forecast; Census / Satellite = static ward data; Estimate = modelled. {ward.meta.label}</p>
    </div>
  )
}
