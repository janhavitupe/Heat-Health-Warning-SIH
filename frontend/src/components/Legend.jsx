import { ALERTS, LAYERS, NO_DATA, RAMP } from '../theme.js'

export default function Legend({ layer, hasConfidence }) {
  const def = LAYERS[layer]
  const rows = def.kind === 'alert'
    ? ALERTS.map((a) => ({ color: a.color, label: `${a.label} (${a.range})` }))
    : def.classes.map(([, label], i) => ({ color: RAMP[i], label }))
  return (
    <div className="legend" aria-label={`Legend: ${def.label}`}>
      <h4>{def.label}</h4>
      {rows.map((r) => (
        <div className="row" key={r.label}><span className="sw" style={{ background: r.color }} />{r.label}</div>
      ))}
      <div className="row"><span className="sw" style={{ background: NO_DATA }} />No data</div>
      {def.kind === 'alert' && hasConfidence && (
        <div className="row"><span className="dash" />Low forecast confidence</div>
      )}
      <div className="note">Model estimate, not a clinical prediction.</div>
    </div>
  )
}
