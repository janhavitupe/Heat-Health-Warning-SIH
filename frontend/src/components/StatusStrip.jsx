import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { ALERTS } from '../theme.js'

// City status for the chosen day: ward counts by level, heatwave event, alerts awaiting review.
export default function StatusStrip({ day, replay, role, onOpenAlerts, refreshKey }) {
  const [d, setD] = useState(null)
  useEffect(() => {
    let live = true
    if (day) api.dashboard(day, replay, role === 'healthcare' ? 'healthcare' : 'municipal')
      .then((x) => live && setD(x)).catch(() => live && setD(null))
    return () => { live = false }
  }, [day, replay, role, refreshKey])
  if (!d) return null
  const ev = d.event
  return (
    <div className="strip" role="status">
      <span className="counts" aria-label="Wards by alert level">
        {ALERTS.map((a) => d.counts[a.key] > 0 && (
          <span key={a.key} className="cnt"><span className="dot" style={{ background: a.color }} />{d.counts[a.key]} {a.label}</span>
        ))}
      </span>
      {ev && <span>Heatwave {ev.start <= d.day ? 'under way' : 'forecast'}: {ev.start.slice(5)} to {ev.end.slice(5)}{ev.open_ended ? '+' : ''} · peak {ev.peak.slice(5)}</span>}
      <span>Cooling deserts: {d.cooling.deserts.length}</span>
      {d.report_flags?.length > 0 && <span className="flagged">Case reports above expected: {d.report_flags.map((f) => `${f.ward_name} (${f.reports} vs ${f.expected.toFixed(1)})`).join(', ')}{d.reports_synthetic ? ' · synthetic' : ''}</span>}
      <button className="linkish" onClick={onOpenAlerts}>{d.alerts_pending_review} alert{d.alerts_pending_review === 1 ? '' : 's'} awaiting review</button>
      <span className={`mode ${d.dispatch_mode}`}>{d.dispatch_mode === 'simulated' ? 'Simulated delivery (nothing is sent)' : 'Live Twilio sandbox'}</span>
    </div>
  )
}
