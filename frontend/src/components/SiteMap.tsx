import { latLngBounds, type LeafletEventHandlerFnMap } from 'leaflet'
import { memo, useCallback, useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, Popup, Tooltip, useMap } from 'react-leaflet'
import { useNavigate } from 'react-router-dom'
import type { Site } from '../api'
import { DETAIL_OUTLINE, LOSS, PROFIT } from '../colors'
import { usd } from '../format'
import KindBadge from './KindBadge'
import OsmTileLayer from './OsmTileLayer'
import SiteSummaryCard from './SiteSummaryCard'

const US_CENTER: [number, number] = [39.5, -97]

interface Props {
  sites: Site[]
}

/** Canvas-rendered map of every site. Detailed sites open their page; lightweight sites show a summary popup. */
export default function SiteMap({ sites }: Props) {
  // Each click gets a fresh key so the popup re-opens even after the user closed it (Leaflet removes a
  // closed popup on its own; React still holds the selection).
  const [selected, setSelected] = useState<{ site: Site; key: number } | null>(null)
  const select = useCallback((site: Site) => setSelected((cur) => ({ site, key: (cur?.key ?? 0) + 1 })), [])
  // Hide the popup when the filtered set no longer contains its site.
  const popup = selected && sites.some((s) => s.id === selected.site.id) ? selected : null
  // Stable reference: react-leaflet re-opens the popup whenever `position` changes identity.
  const popupPosition = useMemo<[number, number] | null>(
    () => (popup ? [popup.site.lat, popup.site.lng] : null),
    [popup],
  )

  return (
    <div className="relative isolate h-[460px] overflow-hidden rounded-lg border border-slate-200">
      <MapContainer center={US_CENTER} zoom={4} minZoom={3} preferCanvas className="site-map h-full w-full" scrollWheelZoom>
        <OsmTileLayer />
        <FitBounds sites={sites} />
        <Markers sites={sites} onSelectLightweight={select} />
        {popup && popupPosition && (
          <Popup key={popup.key} position={popupPosition}>
            <SiteSummaryCard site={popup.site} />
          </Popup>
        )}
      </MapContainer>
      <Legend />
    </div>
  )
}

/** Memoized so opening a popup doesn't re-render ~2,000 markers. */
const Markers = memo(function Markers({
  sites,
  onSelectLightweight,
}: {
  sites: Site[]
  onSelectLightweight: (site: Site) => void
}) {
  const navigate = useNavigate()
  // Natural order (not losses-on-top) so a dense metro cluster shows its real mix of loss and profit.
  const { lightweight, detailed } = useMemo(
    () => ({ lightweight: sites.filter((s) => !s.detailed), detailed: sites.filter((s) => s.detailed) }),
    [sites],
  )

  return (
    <>
      {lightweight.map((s) => {
        const loss = s.contribution.amount < 0
        const handlers: LeafletEventHandlerFnMap = { click: () => onSelectLightweight(s) }
        return (
          <CircleMarker
            key={s.id}
            center={[s.lat, s.lng]}
            radius={3.5}
            bubblingMouseEvents={false}
            pathOptions={{ stroke: false, fillColor: loss ? LOSS : PROFIT, fillOpacity: 0.85 }}
            eventHandlers={handlers}
          />
        )
      })}
      {detailed.map((s) => {
        const loss = s.contribution.amount < 0
        return (
          <CircleMarker
            key={s.id}
            center={[s.lat, s.lng]}
            radius={8}
            bubblingMouseEvents={false}
            pathOptions={{ color: DETAIL_OUTLINE, weight: 2, fillColor: loss ? LOSS : PROFIT, fillOpacity: 0.95 }}
            eventHandlers={{ click: () => navigate(`/locations/${s.id}`) }}
          >
            <Tooltip direction="top" offset={[0, -8]}>
              <span className="inline-flex items-center gap-1">
                <span className="font-medium">{s.name}</span> · {usd(s.contribution.amount)}
                <KindBadge kind={s.contribution.kind} compact /> contribution
              </span>
              <br />
              <span className="text-slate-500">Click to open location details</span>
            </Tooltip>
          </CircleMarker>
        )
      })}
    </>
  )
})

function FitBounds({ sites }: { sites: Site[] }) {
  const map = useMap()
  useEffect(() => {
    if (sites.length === 0) return
    map.fitBounds(latLngBounds(sites.map((s) => [s.lat, s.lng] as [number, number])), {
      padding: [24, 24],
      maxZoom: 10,
    })
  }, [map, sites])
  return null
}

function Legend() {
  return (
    <div className="pointer-events-none absolute bottom-6 left-3 z-[1000] rounded-md border border-slate-200 bg-white/95 px-3 py-2 text-xs text-slate-700 shadow-sm">
      <div className="flex items-center gap-2">
        <Dot color={LOSS} /> Loss-making (contribution &lt; $0)
      </div>
      <div className="mt-1 flex items-center gap-2">
        <Dot color={PROFIT} /> Profitable
      </div>
      <div className="mt-1 flex items-center gap-2">
        <span className="inline-block h-3 w-3 rounded-full border-2 bg-slate-300" style={{ borderColor: DETAIL_OUTLINE }} />
        Detailed site — click to open
      </div>
    </div>
  )
}

function Dot({ color }: { color: string }) {
  return <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
}
