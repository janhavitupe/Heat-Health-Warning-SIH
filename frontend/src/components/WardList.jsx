import { useState } from 'react'
import { ALERT_COLOR, ALERT_LABEL, LAYERS } from '../theme.js'

// Table view of every ward for the chosen day: the accessible alternative to the map.
export default function WardList({ data, layer, onSelect }) {
  const def = LAYERS[layer]
  const target = def.kind === 'alert' ? def : LAYERS.mri
  const [sort, setSort] = useState({ key: target.value, desc: true })
  const rows = [...(data?.features ?? [])].map((f) => f.properties)
  rows.sort((a, b) => {
    const x = a[sort.key] ?? -Infinity, y = b[sort.key] ?? -Infinity
    return (x > y ? 1 : x < y ? -1 : 0) * (sort.desc ? -1 : 1)
  })
  const cols = [
    ['ward_name', 'Ward'], [target.value, target === LAYERS.hri ? 'HRI' : 'MRI'], ['htsi', 'HTSI'], ['pvi', 'PVI'],
    ['tmax', 'Tmax °C'], ['p_red', 'P(Red)'],
  ]
  const th = (key, label) => (
    <th key={key} scope="col" aria-sort={sort.key === key ? (sort.desc ? 'descending' : 'ascending') : 'none'}
      onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : key !== 'ward_name' }))}>
      {label}{sort.key === key ? (sort.desc ? ' ↓' : ' ↑') : ''}
    </th>
  )
  return (
    <table className="list">
      <caption className="meta" style={{ textAlign: 'left', marginBottom: 6 }}>All 48 wards for {data?.day}. Select a row for details.</caption>
      <thead><tr>{cols.map(([k, l]) => th(k, l))}</tr></thead>
      <tbody>
        {rows.map((p) => {
          const lvl = p[target.field]
          return (
            <tr key={p.ward_id} onClick={() => onSelect(p.ward_id)} tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && onSelect(p.ward_id)}>
              <td>{p.ward_name}</td>
              <td className="n"><span className="badge"><span className="dot" style={{ background: ALERT_COLOR[lvl] }} />
                {p[target.value]?.toFixed(0)} {ALERT_LABEL[lvl]}</span></td>
              <td className="n">{p.htsi?.toFixed(0)}</td>
              <td className="n">{p.pvi?.toFixed(0)}</td>
              <td className="n">{p.tmax?.toFixed(1)}</td>
              <td className="n">{p.p_red === null || p.p_red === undefined ? '—' : `${Math.round(p.p_red * 100)}%`}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
