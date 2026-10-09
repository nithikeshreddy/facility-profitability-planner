import { TileLayer } from 'react-leaflet'

/** OpenStreetMap tiles with the attribution their tile policy requires. Every map uses this layer. */
export default function OsmTileLayer() {
  return (
    <TileLayer
      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    />
  )
}
