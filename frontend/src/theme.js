// Colour and layer definitions. Alert colours use the reserved status palette
// (good / warning / serious / critical), which lines up with IMD's green / yellow /
// orange / red and is always paired with a text label. Continuous layers use one
// orange ramp (validated light→dark for both themes).

export const ALERTS = [
  { key: 'green', label: 'Green', color: '#0ca30c', range: '≤ 40' },
  { key: 'yellow', label: 'Yellow', color: '#fab219', range: '41–60' },
  { key: 'orange', label: 'Orange', color: '#ec835a', range: '61–80' },
  { key: 'red', label: 'Red', color: '#d03b3b', range: '81–100' },
]
export const ALERT_COLOR = Object.fromEntries(ALERTS.map((a) => [a.key, a.color]))
export const ALERT_LABEL = Object.fromEntries(ALERTS.map((a) => [a.key, a.label]))

export const RAMP = ['#fe936c', '#f5713e', '#dd5b25', '#bf4301', '#9a3501']
export const NO_DATA = '#b8b6ae'

// Categorical slots for chart series (first three validate all-pairs)
export const SERIES = { light: ['#2a78d6', '#eb6834', '#1baf7a'], dark: ['#3987e5', '#d95926', '#199e70'] }

// Map layers. `classes` are [upper bound, label] pairs for continuous layers.
export const LAYERS = {
  mri: { label: 'Mortality risk (MRI)', kind: 'alert', field: 'alert_mri', value: 'mri',
    help: 'Heat stress × population vulnerability × past heat-illness history.' },
  hri: { label: 'Hospitalization risk (HRI)', kind: 'alert', field: 'alert_hri', value: 'hri',
    help: 'Heat stress × vulnerability × hospital capacity pressure (capacity currently at default).' },
  htsi: { label: 'Heat stress (HTSI)', kind: 'ramp', field: 'htsi', unit: '/100',
    classes: [[20, 'Low'], [40, 'Moderate'], [60, 'High'], [80, 'Very high'], [Infinity, 'Extreme']],
    help: 'UTCI, WBGT and Heat Index, plus hot nights, consecutive hot days and sheet roofs.' },
  tmax: { label: 'Max temperature', kind: 'ramp', field: 'tmax', unit: '°C',
    classes: [[38, '< 38 °C'], [41, '38–41'], [43, '41–43'], [45, '43–45'], [Infinity, '≥ 45']],
    help: 'Ward-adjusted daily maximum. 41 / 43 / 45 °C are the Heat Action Plan alert thresholds.' },
  pvi: { label: 'Vulnerability (PVI)', kind: 'ramp', field: 'pvi', unit: '/100',
    classes: [[40, '< 40'], [45, '40–45'], [50, '45–50'], [55, '50–55'], [Infinity, '≥ 55']],
    help: 'Slums, hospital access and density (elderly, children and outdoor workers held at midpoint until data arrives).' },
  indoor: { label: 'Indoor heat (sheet roofs)', kind: 'ramp', field: 'pts_indoor', unit: 'pts', missing: 'indoor_data_missing',
    classes: [[0.01, 'None'], [2.5, '0–2.5'], [5, '2.5–5'], [7.5, '5–7.5'], [Infinity, '7.5–10']],
    help: 'Extra heat-stress points for homes with metal/asbestos roofs (Innovation 1). Roof data not yet available.' },
  p_red: { label: 'Chance of Red', kind: 'ramp', field: 'p_red', unit: '%', percent: true,
    classes: [[0.1, '< 10%'], [0.3, '10–30%'], [0.5, '30–50%'], [0.7, '50–70%'], [Infinity, '≥ 70%']],
    help: 'Share of ensemble forecast runs in which the ward reaches Red (each weather model weighted equally).' },
}

export const ROLES = {
  municipal: { label: 'Municipal', layer: 'mri' },
  healthcare: { label: 'Healthcare', layer: 'hri' },
}

export const DATA_LABELS = {
  live: 'Live', census: 'Census', satellite_derived: 'Satellite', historical: 'Historical',
  model_estimate: 'Estimate', scenario_estimate: 'Scenario',
}

export function classColor(layer, value) {
  const def = LAYERS[layer]
  if (value === null || value === undefined || Number.isNaN(value)) return NO_DATA
  const i = def.classes.findIndex(([upper]) => value < upper)
  return RAMP[i === -1 ? RAMP.length - 1 : i]
}
