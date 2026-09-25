import { ALERTS } from '../theme.js'

const fmt = (d, opts) => new Date(`${d}T00:00:00`).toLocaleDateString('en-IN', opts)

// One button per day: the bar shows how many wards are at each alert level.
export default function DaySlider({ days, day, today, onChange }) {
  return (
    <div className="days" role="group" aria-label="Choose day">
      {days.map((d) => {
        const total = Object.values(d.counts).reduce((a, b) => a + b, 0) || 1
        const worst = [...ALERTS].reverse().find((a) => d.counts[a.key] > 0)
        const label = `${fmt(d.date, { weekday: 'long', day: 'numeric', month: 'long' })}: ` +
          ALERTS.map((a) => `${d.counts[a.key]} ${a.label}`).join(', ') +
          (d.max_p_red !== null ? `; highest chance of Red ${Math.round(d.max_p_red * 100)}%` : '')
        return (
          <button key={d.date} className={`day${today && d.date < today ? ' past' : ''}`} aria-pressed={d.date === day}
            aria-label={label} title={label} onClick={() => onChange(d.date)}>
            <div className="d">{fmt(d.date, { weekday: 'short', day: 'numeric' })}{d.date === today ? ' · today' : ''}</div>
            <div className="w">{worst ? `${d.counts[worst.key]} ${worst.label}` : '—'}</div>
            <div className="bar" aria-hidden="true">
              {ALERTS.map((a) => d.counts[a.key] > 0 && (
                <span key={a.key} style={{ width: `${(100 * d.counts[a.key]) / total}%`, background: a.color }} />
              ))}
            </div>
          </button>
        )
      })}
    </div>
  )
}
