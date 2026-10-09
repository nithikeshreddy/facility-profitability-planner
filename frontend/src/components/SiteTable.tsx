import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { Site } from '../api'
import { count } from '../format'
import MoneyValue from './MoneyValue'
import SiteSummaryCard from './SiteSummaryCard'

type SortKey = 'name' | 'city' | 'state' | 'detailed' | 'revenue' | 'direct_costs' | 'contribution'
type SortDir = 'asc' | 'desc'

const PAGE_SIZE = 50

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: 'name', label: 'Site' },
  { key: 'city', label: 'City' },
  { key: 'state', label: 'State' },
  { key: 'detailed', label: 'Data' },
  { key: 'revenue', label: 'Revenue', numeric: true },
  { key: 'direct_costs', label: 'Direct costs', numeric: true },
  { key: 'contribution', label: 'Contribution', numeric: true },
]

function sortValue(s: Site, key: SortKey): string | number {
  switch (key) {
    case 'revenue':
    case 'direct_costs':
    case 'contribution':
      return s[key].amount
    case 'detailed':
      return s.detailed ? 1 : 0
    default:
      return s[key].toLowerCase()
  }
}

export default function SiteTable({ sites }: { sites: Site[] }) {
  const navigate = useNavigate()
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({ key: 'contribution', dir: 'asc' })
  const [page, setPage] = useState(0)
  const [popoverId, setPopoverId] = useState<number | null>(null)

  // New data (filters changed, demo reset): back to the first page, popover closed.
  const [prevSites, setPrevSites] = useState(sites)
  if (sites !== prevSites) {
    setPrevSites(sites)
    setPage(0)
    setPopoverId(null)
  }

  const sorted = useMemo(() => {
    const factor = sort.dir === 'asc' ? 1 : -1
    return [...sites].sort((a, b) => {
      const va = sortValue(a, sort.key)
      const vb = sortValue(b, sort.key)
      return (va < vb ? -1 : va > vb ? 1 : a.id - b.id) * factor
    })
  }, [sites, sort])

  const pages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE))
  const rows = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  function toggleSort(key: SortKey) {
    setSort((cur) =>
      cur.key === key ? { key, dir: cur.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: COLUMNS.find((c) => c.key === key)?.numeric ? 'desc' : 'asc' },
    )
    setPage(0)
  }

  function openRow(site: Site) {
    if (site.detailed) navigate(`/locations/${site.id}`)
    else setPopoverId((cur) => (cur === site.id ? null : site.id))
  }

  return (
    <div>
      <table className="w-full table-fixed text-sm">
        <colgroup>
          <col className="w-[26%]" />
          <col className="w-[14%]" />
          <col className="w-[7%]" />
          <col className="w-[10%]" />
          <col className="w-[14%]" />
          <col className="w-[14%]" />
          <col className="w-[15%]" />
        </colgroup>
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs font-medium text-slate-500">
            {COLUMNS.map((c) => {
              const active = sort.key === c.key
              return (
                <th
                  key={c.key}
                  scope="col"
                  aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  className={`px-3 py-2 ${c.numeric ? 'text-right' : ''}`}
                >
                  <button
                    type="button"
                    onClick={() => toggleSort(c.key)}
                    className={`inline-flex items-center gap-1 hover:text-slate-900 ${active ? 'text-slate-900' : ''}`}
                  >
                    {c.label}
                    <span aria-hidden className="text-[10px]">
                      {active ? (sort.dir === 'asc' ? '▲' : '▼') : '↕'}
                    </span>
                  </button>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr
              key={s.id}
              onClick={() => openRow(s)}
              className={`cursor-pointer border-b border-slate-100 hover:bg-slate-50 ${popoverId === s.id ? 'bg-slate-50' : ''}`}
            >
              <td className="relative px-3 py-2">
                {s.detailed ? (
                  <Link
                    to={`/locations/${s.id}`}
                    onClick={(e) => e.stopPropagation()}
                    className="font-medium text-slate-900 underline decoration-slate-300 underline-offset-2 hover:decoration-slate-900"
                  >
                    {s.name}
                  </Link>
                ) : (
                  <button
                    type="button"
                    aria-expanded={popoverId === s.id}
                    onClick={(e) => {
                      e.stopPropagation()
                      openRow(s)
                    }}
                    className="text-left text-slate-800 hover:text-slate-950"
                  >
                    {s.name}
                  </button>
                )}
                <div className="text-xs text-slate-400">{s.code}</div>
                {popoverId === s.id && <RowPopover site={s} onClose={() => setPopoverId(null)} />}
              </td>
              <td className="truncate px-3 py-2 text-slate-700">{s.city}</td>
              <td className="px-3 py-2 text-slate-700">{s.state}</td>
              <td className="px-3 py-2">
                {s.detailed ? (
                  <span className="rounded bg-slate-900 px-1.5 py-0.5 text-[11px] font-medium text-white">Detailed</span>
                ) : (
                  <span className="text-xs text-slate-500">Summary</span>
                )}
              </td>
              <td className="px-3 py-2 text-right">
                <MoneyValue money={s.revenue} compact />
              </td>
              <td className="px-3 py-2 text-right">
                <MoneyValue money={s.direct_costs} compact />
              </td>
              <td className="px-3 py-2 text-right font-medium">
                <MoneyValue money={s.contribution} signed compact />
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={COLUMNS.length} className="px-3 py-8 text-center text-sm text-slate-500">
                No sites match these filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
        <span>
          {sorted.length === 0
            ? '0 sites'
            : `${count(page * PAGE_SIZE + 1)}–${count(Math.min((page + 1) * PAGE_SIZE, sorted.length))} of ${count(sorted.length)} sites`}
        </span>
        <div className="flex items-center gap-2">
          <PageButton disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            Previous
          </PageButton>
          <span>
            Page {page + 1} of {pages}
          </span>
          <PageButton disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)}>
            Next
          </PageButton>
        </div>
      </div>
    </div>
  )
}

function PageButton({ disabled, onClick, children }: { disabled: boolean; onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded border border-slate-300 bg-white px-2.5 py-1 text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </button>
  )
}

/** Small popover anchored under a lightweight site's name; closes on outside click or Esc. */
function RowPopover({ site, onClose }: { site: Site; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onPointer(e: MouseEvent) {
      const row = ref.current?.closest('tr')
      if (row && !row.contains(e.target as Node)) onClose()
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  return (
    <div
      ref={ref}
      role="dialog"
      aria-label={`${site.name} summary`}
      onClick={(e) => e.stopPropagation()}
      className="absolute left-3 top-full z-20 mt-1 cursor-default rounded-lg border border-slate-200 bg-white p-3 shadow-lg"
    >
      <SiteSummaryCard site={site} />
    </div>
  )
}
