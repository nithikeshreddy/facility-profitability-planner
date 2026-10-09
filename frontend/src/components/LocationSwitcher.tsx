import type { Site } from '../api'

interface Props {
  sites: Site[]
  value: number
  onChange: (id: number) => void
}

/** Dropdown to jump between the detailed locations. Renders nothing until the list has loaded. */
export default function LocationSwitcher({ sites, value, onChange }: Props) {
  if (sites.length === 0) return null
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-slate-500">Location</span>
      <select
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="max-w-64 rounded border border-slate-300 bg-white px-2 py-1 text-sm"
      >
        {!sites.some((s) => s.id === value) && <option value={value}>Location {value}</option>}
        {sites.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
    </label>
  )
}
