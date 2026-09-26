import * as maplibregl from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { useEffect, useRef } from 'react'
import { featureColor, valueText } from '../layers.js'
import { LAYERS } from '../theme.js'

// MapLibre 6 ships its worker as a separate module; bundle it and tell MapLibre where it is.
maplibregl.setWorkerUrl(workerUrl)

const dark = window.matchMedia?.('(prefers-color-scheme: dark)').matches
// OpenFreeMap: free vector basemap, no API key (OpenStreetMap data)
const BASEMAP = `https://tiles.openfreemap.org/styles/${dark ? 'dark' : 'positron'}`
const CENTER = [72.585, 23.03]

export default function MapView({ data, layer, selected, cooling, onSelect }) {
  const box = useRef(null)
  const map = useRef(null)
  const ready = useRef(false)
  const latest = useRef({ data, layer, selected, cooling, onSelect })
  latest.current = { data, layer, selected, cooling, onSelect }

  useEffect(() => {
    const m = new maplibregl.Map({ container: box.current, style: BASEMAP, center: CENTER, zoom: 10.6, attributionControl: { compact: true } })
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 })
    m.on('load', () => {
      // ward layers go under the basemap's place labels so neighbourhood names stay readable
      const labels = m.getStyle().layers.find((l) => l.type === 'symbol')?.id
      m.addSource('wards', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      m.addLayer({ id: 'fill', type: 'fill', source: 'wards',
        paint: { 'fill-color': ['get', '_color'], 'fill-opacity': ['case', ['get', '_faint'], 0.45, 0.85] } }, labels)
      m.addLayer({ id: 'edge', type: 'line', source: 'wards', paint: { 'line-color': dark ? '#1a1a19' : '#fcfcfb', 'line-width': 1 } }, labels)
      m.addLayer({ id: 'faint', type: 'line', source: 'wards', filter: ['==', ['get', '_faint'], true],
        paint: { 'line-color': dark ? '#c3c2b7' : '#52514e', 'line-width': 1.2, 'line-dasharray': [2, 2] } }, labels)
      m.addLayer({ id: 'selected', type: 'line', source: 'wards', filter: ['==', ['get', 'ward_id'], ''],
        paint: { 'line-color': dark ? '#ffffff' : '#0b0b0b', 'line-width': 2.5 } })
      // Cooling layer extras: existing AMC cooling places (small dots) and recommended new sites (ranked)
      const none = { type: 'FeatureCollection', features: [] }
      m.addSource('cool-pts', { type: 'geojson', data: none })
      m.addSource('cool-sites', { type: 'geojson', data: none })
      m.addLayer({ id: 'cool-pts', type: 'circle', source: 'cool-pts',
        paint: { 'circle-radius': 3, 'circle-color': dark ? '#3987e5' : '#2a78d6', 'circle-stroke-width': 1,
          'circle-stroke-color': dark ? '#1a1a19' : '#fcfcfb' } })
      m.addLayer({ id: 'cool-sites', type: 'circle', source: 'cool-sites',
        paint: { 'circle-radius': 9, 'circle-color': dark ? '#199e70' : '#1baf7a', 'circle-stroke-width': 3,
          'circle-stroke-color': dark ? '#ffffff' : '#0b0b0b' } })
      m.addLayer({ id: 'cool-sites-label', type: 'symbol', source: 'cool-sites',
        layout: { 'text-field': ['to-string', ['get', 'rank']], 'text-size': 11, 'text-allow-overlap': true,
          'text-font': ['Noto Sans Bold'] }, paint: { 'text-color': '#ffffff' } })
      ready.current = true
      render()
    })
    m.on('mousemove', 'fill', (e) => {
      const p = e.features[0].properties
      m.getCanvas().style.cursor = 'pointer'
      const el = document.createElement('div')
      el.className = 'maptip'
      const name = document.createElement('b')
      name.textContent = p.ward_name
      const val = document.createElement('div')
      val.textContent = `${LAYERS[latest.current.layer].label}: ${valueText(latest.current.layer, JSON.parse(p._props))}`
      el.append(name, val)
      popup.setLngLat(e.lngLat).setDOMContent(el).addTo(m)
    })
    m.on('mouseleave', 'fill', () => { m.getCanvas().style.cursor = ''; popup.remove() })
    m.on('click', 'fill', (e) => latest.current.onSelect(e.features[0].properties.ward_id))
    map.current = m
    return () => { ready.current = false; m.remove() }
  }, [])

  function render() {
    const m = map.current
    const { data, layer, selected } = latest.current
    if (!m || !ready.current || !data) return
    const def = LAYERS[layer]
    const features = data.features.map((f) => ({
      ...f,
      properties: {
        ward_id: f.properties.ward_id, ward_name: f.properties.ward_name,
        _color: featureColor(layer, f.properties),
        // Low forecast confidence: shown fainter with a dashed outline on alert layers
        _faint: def.kind === 'alert' && f.properties.confidence === 'low',
        _props: JSON.stringify(f.properties),
      },
    }))
    m.getSource('wards').setData({ type: 'FeatureCollection', features })
    m.setFilter('selected', ['==', ['get', 'ward_id'], selected ?? ''])
    const none = { type: 'FeatureCollection', features: [] }
    m.getSource('cool-pts').setData(latest.current.cooling?.existing_points ?? none)
    m.getSource('cool-sites').setData(latest.current.cooling?.recommended_sites ?? none)
  }

  useEffect(render, [data, layer, selected, cooling])

  return <div className="map" ref={box} role="region" aria-label="Ward risk map" />
}
