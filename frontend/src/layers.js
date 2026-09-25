import { ALERT_COLOR, ALERT_LABEL, LAYERS, NO_DATA, classColor } from './theme.js'

// Colour and hover text for one ward on the current map layer.
export function featureColor(layer, p) {
  const def = LAYERS[layer]
  if (def.kind === 'alert') return ALERT_COLOR[p[def.field]] ?? NO_DATA
  if (def.missing && p[def.missing]) return NO_DATA
  return classColor(layer, p[def.field])
}

export function valueText(layer, p) {
  const def = LAYERS[layer]
  if (def.kind === 'alert') return `${ALERT_LABEL[p[def.field]] ?? '—'} (${p[def.value]?.toFixed(0) ?? '—'}/100)`
  if (def.missing && p[def.missing]) return 'No data'
  const v = p[def.field]
  if (v === null || v === undefined) return 'No data'
  return def.percent ? `${Math.round(v * 100)}%` : `${v.toFixed(1)} ${def.unit}`
}
