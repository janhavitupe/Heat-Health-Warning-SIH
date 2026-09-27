import { useEffect, useState } from 'react'
import { api, reportCardUrl } from '../api.js'

const LABELS = {
  utci: 'Whole-body heat stress (UTCI)', wbgt: 'Outdoor work heat stress (WBGT)', heat_index: 'Heat + humidity (Heat Index)',
  elderly_share: 'Elderly (60+)', outdoor_worker_share: 'Outdoor workers', healthcare_access_gap: 'Walking distance to health care',
  cooling_access_gap: 'Far from cooling places', informal_housing_share: 'Informal housing (slums)', under5_share: 'Children under 5',
  population_density: 'Population density',
}
const DATA_LABEL = { live: 'Live', census: 'Census', model_estimate: 'Estimate' }
const pct = (x) => `${Math.round(x * 100)}%`

const LIMITS = [
  'Scores are model estimates, not clinical predictions. They rank wards and time actions; they do not predict individual illness.',
  'Validated on one heatwave (May 2024). Health outcomes for it are known only city-wide (69 heatstroke cases), so ward rankings cannot yet be checked against illness.',
  'Elderly, children and outdoor-worker shares are held at the city midpoint: WorldPop age shares are flat across wards and census 2011 wards cannot yet be matched to 2015 wards.',
  'Sheet-roof shares are estimates from census 2011 city and slum rates, mixed by each ward’s slum share. Real ward differences are larger.',
  'Hospital capacity is not used: only public beds are in the data, and private hospitals treat most patients in urban Gujarat.',
  'Ward temperature adjustment is applied at night only; the daytime satellite signal made errors worse at the airport station.',
  'Hindi and Gujarati messages are drafts that need review by native speakers before public use.',
  'Health-worker reports and alert deliveries shown in the demo are synthetic / simulated.',
]

// Methodology (§6.8): formulas and weights read live from /config, data sources, validation, limitations.
export default function MethodTab({ replay }) {
  const [cfg, setCfg] = useState(null)
  const [sources, setSources] = useState([])
  const [card, setCard] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => {
    api.config().then((c) => { setCfg(c.config); setSources(c.ward_columns) }).catch((e) => setErr(e.message))
    fetch(`${reportCardUrl('may2024', 0)}&format=json`).then((r) => (r.ok ? r.json() : null)).then(setCard).catch(() => setCard(null))
  }, [])
  if (err) return <p className="error">{err}</p>
  if (!cfg) return <p className="meta">Loading…</p>
  const ts = cfg.thermal_stress, h = cfg.htsi, risk = cfg.risk, bands = cfg.alerts.levels
  const v = card?.verification, s = card?.summary
  const shown = sources.filter((r) => !['ward_id', 'ward_no', 'ward_name', 'zone', 'centroid_lat', 'centroid_lon', 'area_km2'].includes(r.column))

  return (
    <div className="method">
      <p className="meta">How every number on this screen is made. Weights below are read live from the system’s settings.</p>

      <h4>1. From weather to a ward risk score</h4>
      <ol className="steps">
        <li><b>Weather</b> for the city (Open-Meteo: ECMWF, GFS, ICON forecasts), adjusted to each ward at night using satellite surface temperature.</li>
        <li><b>Heat stress (HTSI, 0–100)</b> from three body-heat indices, plus points for hot nights, consecutive hot days and sheet roofs.</li>
        <li><b>Vulnerability (PVI, 0–100)</b> from who lives in the ward and how far they are from care and cooling. 50 = city average.</li>
        <li><b>Mortality risk (MRI)</b> = HTSI × (1 + {risk.vulnerability_spread} × (PVI − 50) / 50) × local factor. Hospitalization risk (HRI) also includes hospital capacity (currently off).</li>
        <li><b>Alert colour</b> from MRI: Green ≤ {bands.green}, Yellow ≤ {bands.yellow}, Orange ≤ {bands.orange}, Red above (IMD colour scheme).</li>
      </ol>

      <h4>2. Heat stress (HTSI)</h4>
      <table className="mt"><thead><tr><th>Index</th><th className="n">Weight</th><th className="n">Scores 0 at</th><th className="n">Scores 100 at</th></tr></thead>
        <tbody>{Object.entries(ts.weights).map(([k, w]) => (
          <tr key={k}><td>{LABELS[k]}</td><td className="n">{pct(w)}</td><td className="n">{ts.normalization[k].zero} °C</td><td className="n">{ts.normalization[k].full} °C</td></tr>))}
        </tbody></table>
      <p className="meta">Scales are anchored to the Ahmedabad Heat Action Plan: a day as rare as Tmax 41 °C scores 40, as rare as 45 °C scores 80. Each index uses the mean of the 3 hottest hours.</p>
      <ul className="meta">
        <li>Hot night: up to {h.night.max_points} points as ward minimum rises from {h.night.tmin_threshold_c} to {h.night.tmin_full_c} °C.</li>
        <li>Consecutive hot days: {h.persistence.points_per_day} points per day in a row at base score ≥ {h.persistence.min_base_score} (max {h.persistence.max_points}).</li>
        <li>Sheet roofs: {h.indoor.max_points} × share of sheet-roofed homes on days with base ≥ {h.indoor.min_base_score}, × {h.indoor.night_multiplier} on hot nights.</li>
      </ul>

      <h4>3. Vulnerability (PVI)</h4>
      <table className="mt"><thead><tr><th>Indicator</th><th className="n">Weight</th></tr></thead>
        <tbody>{Object.entries(cfg.pvi.weights).map(([k, w]) => <tr key={k}><td>{LABELS[k] ?? k}</td><td className="n">{pct(w)}</td></tr>)}</tbody></table>
      <p className="meta">Each indicator is ranked across wards (percentile), so no single skewed indicator dominates. Indicators without ward-level variation are held at the midpoint and say so in each ward’s explanation.</p>

      <h4>4. Forecast probabilities</h4>
      <p className="meta">{cfg.ensemble.models.length} forecast models, each model’s runs given an equal share (122 runs in total). Confidence: high ≥ {pct(cfg.ensemble.confidence.high)}, medium ≥ {pct(cfg.ensemble.confidence.medium)}.
        {cfg.ensemble.triggers.map((t) => ` Preparedness trigger: chance of Red ≥ ${pct(t.at_least)} within ${t.lead_days_max} days.`)}</p>

      <h4>5. How well it worked: May 2024 heatwave</h4>
      {v ? (
        <ul className="meta">
          <li>IMD red-alert days with a ward at Red: <b>{v.imd_days_any_red} of {v.imd_days}</b>; Orange-or-worse warning {v.imd_lead_days} days before IMD’s red alert.</li>
          <li>Days the Heat Action Plan (observed temperature) called Orange/Red that the model also rated Orange+: <b>{v.hits} of {v.plan_warn_days}</b>; over-warning on {v.false} of {v.plan_quiet_days} quieter days.</li>
          <li>Red ward-days flagged by forecasts 3–5 days ahead (chance of Red ≥ {pct(s.threshold)}): <b>{s.red_warned} of {s.red_with_prob}</b>.</li>
          <li><a href={reportCardUrl('may2024', 0)} target="_blank" rel="noreferrer">Open the full report card</a> · details in docs/evaluation.md.</li>
        </ul>
      ) : <p className="meta">Backtest replay not loaded on this server.</p>}

      <h4>6. Data sources</h4>
      <table className="mt"><thead><tr><th>Data</th><th>Source</th><th>Year</th></tr></thead>
        <tbody>{shown.map((r) => (
          <tr key={r.column}><td>{r.description}{r.is_estimate ? <span className="chip">{DATA_LABEL[r.label] ?? 'Estimate'}</span> : null}</td>
            <td>{r.source}</td><td>{r.year}</td></tr>))}</tbody></table>

      <h4>7. Limitations</h4>
      <ul className="meta">{LIMITS.map((l) => <li key={l}>{l}</li>)}</ul>
      {replay && <p className="meta">You are viewing a replay of a past heatwave.</p>}
    </div>
  )
}
