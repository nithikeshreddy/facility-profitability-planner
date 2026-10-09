import { divIcon, latLngBounds } from 'leaflet'
import { useMemo } from 'react'
import { MapContainer, Marker, Polyline, Tooltip } from 'react-leaflet'
import type { BundleSite } from '../api'
import { DETAIL_OUTLINE, LOSS, PROFIT } from '../colors'
import { usd } from '../format'
import KindBadge from './KindBadge'
import OsmTileLayer from './OsmTileLayer'

/** Small route map for a vendor bundle: numbered stops in route order, colored by projected contribution. */
export default function BundleMap({ sites }: { sites: BundleSite[] }) {
  const points = useMemo(() => sites.map((s) => [s.lat, s.lng] as [number, number]), [sites])
  const bounds = useMemo(() => latLngBounds(points), [points])

  return (
    <div className="relative isolate h-64 overflow-hidden rounded-lg border border-slate-200">
      <MapContainer
        bounds={bounds}
        boundsOptions={{ padding: [36, 36], maxZoom: 14 }}
        scrollWheelZoom={false}
        className="site-map h-full w-full"
      >
        <OsmTileLayer />
        <Polyline positions={points} pathOptions={{ color: DETAIL_OUTLINE, weight: 2, dashArray: '6 6' }} />
        {sites.map((s, i) => (
          <Marker key={s.location_id} position={[s.lat, s.lng]} icon={stopIcon(i + 1, s)}>
            <Tooltip direction="top" offset={[0, -14]}>
              <span className="font-medium">
                Stop {i + 1}: {s.location_name}
              </span>
              <br />
              <span className="inline-flex items-center gap-1">
                {usd(s.current_contribution.amount)} <KindBadge kind={s.current_contribution.kind} compact /> →{' '}
                {usd(s.projected_contribution.amount)} <KindBadge kind={s.projected_contribution.kind} compact /> projected
              </span>
            </Tooltip>
          </Marker>
        ))}
      </MapContainer>
    </div>
  )
}

function stopIcon(n: number, site: BundleSite) {
  const loss = site.projected_contribution.amount < 0
  const fill = loss ? LOSS : PROFIT
  const text = loss ? '#fff' : DETAIL_OUTLINE // dark digits on the light green for contrast
  const ring = site.is_this_location ? `3px solid ${DETAIL_OUTLINE}` : '2px solid #fff'
  return divIcon({
    className: '',
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    html: `<div style="width:26px;height:26px;border-radius:9999px;background:${fill};border:${ring};box-shadow:0 1px 3px rgba(0,0,0,.4);color:${text};font:600 12px/20px system-ui,sans-serif;display:flex;align-items:center;justify-content:center">${n}</div>`,
  })
}
