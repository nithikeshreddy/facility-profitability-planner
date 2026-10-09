import type { ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getOverview, type Money, type Totals } from '../api'
import Card from '../components/Card'
import KindBadge from '../components/KindBadge'
import SiteMap from '../components/SiteMap'
import SiteTable from '../components/SiteTable'
import { ErrorMessage, Loading } from '../components/StatusMessage'
import { count, usd } from '../format'
import { useApi } from '../useApi'

export default function Overview() {
  // Filters live in the URL so Back from a location keeps them.
  const [params, setParams] = useSearchParams()
  const state = params.get('state') ?? ''
  const lossOnly = params.get('loss_only') === 'true'
  const detailedOnly = params.get('detailed_only') === 'true'

  const { data, error, loading } = useApi(
    (signal) => getOverview({ state: state || undefined, loss_only: lossOnly, detailed_only: detailedOnly }, signal),
    [state, lossOnly, detailedOnly],
  )

  function setFilter(key: string, value: string | boolean) {
    setParams(
      (p) => {
        const next = new URLSearchParams(p)
        if (value === '' || value === false) next.delete(key)
        else next.set(key, String(value))
        return next
      },
      { replace: true },
    )
  }

  const filtered = Boolean(state || lossOnly || detailedOnly)

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Overview</h1>
          <p className="mt-1 text-sm text-slate-500">
            Monthly contribution by location. Open a loss-making detailed site to inspect the evidence.
          </p>
        </div>
        <Filters
          states={data?.states ?? []}
          state={state}
          lossOnly={lossOnly}
          detailedOnly={detailedOnly}
          onChange={setFilter}
        />
      </header>

      {error && <ErrorMessage error={error} />}
      {!data && loading && <Loading label="Loading sites…" />}

      {data && (
        <div className={`space-y-5 transition-opacity ${loading ? 'opacity-60' : ''}`}>
          <KpiTiles totals={data.totals} filtered={filtered} />

          <Card
            title="All sites"
            subtitle="Red = loss-making, green = profitable. Outlined markers are the 12 detailed sites; click one to open its evidence."
          >
            <SiteMap sites={data.sites} />
          </Card>

          <Card
            title="Sites"
            subtitle="Click a detailed site to open it. Summary sites show their figures only."
            actions={<BadgeLegend />}
          >
            <SiteTable sites={data.sites} />
          </Card>
        </div>
      )}
    </div>
  )
}

function KpiTiles({ totals, filtered }: { totals: Totals; filtered: boolean }) {
  const scope = filtered ? 'filtered sites' : 'all sites'
  return (
    <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
      <Tile label="Revenue" note={`Monthly, ${scope}`}>
        <TileMoney money={totals.revenue} />
      </Tile>
      <Tile label="Direct costs" note="Vendor invoices, return visits, credits, other direct costs, bonuses">
        <TileMoney money={totals.direct_costs} />
      </Tile>
      <Tile label="Contribution" note="Revenue − direct costs">
        <TileMoney money={totals.contribution} signed />
      </Tile>
      <Tile label="Loss-making sites" note={`of ${count(totals.sites)} sites · ${count(totals.detailed_sites)} detailed`}>
        <span className={totals.loss_making > 0 ? 'text-red-700' : ''}>{count(totals.loss_making)}</span>
      </Tile>
    </div>
  )
}

/** Portfolio totals rounded to whole dollars so they fit a tile; the badge sits beside the label line. */
function TileMoney({ money, signed = false }: { money: Money; signed?: boolean }) {
  const tone = !signed ? '' : money.amount < 0 ? 'text-red-700' : 'text-green-700'
  return (
    <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
      <span className={tone}>{usd(Math.round(money.amount))}</span>
      <KindBadge kind={money.kind} />
    </span>
  )
}

function Tile({ label, note, children }: { label: string; note: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-5 py-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold tabular-nums">{children}</div>
      <div className="mt-1 text-xs text-slate-500">{note}</div>
    </div>
  )
}

function Filters({
  states,
  state,
  lossOnly,
  detailedOnly,
  onChange,
}: {
  states: string[]
  state: string
  lossOnly: boolean
  detailedOnly: boolean
  onChange: (key: string, value: string | boolean) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm shadow-sm">
      <label className="flex items-center gap-2">
        <span className="text-slate-600">State</span>
        <select
          value={state}
          onChange={(e) => onChange('state', e.target.value)}
          className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
        >
          <option value="">All states</option>
          {states.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      <Checkbox label="Loss-making only" checked={lossOnly} onChange={(v) => onChange('loss_only', v)} />
      <Checkbox label="Detailed sites only" checked={detailedOnly} onChange={(v) => onChange('detailed_only', v)} />
    </div>
  )
}

function Checkbox({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-slate-700">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-slate-300 accent-slate-900"
      />
      {label}
    </label>
  )
}

function BadgeLegend() {
  return (
    <div className="flex items-center gap-2 text-[11px] text-slate-500">
      <KindBadge kind="actual" compact /> actual
      <KindBadge kind="estimated" compact /> estimated
      <KindBadge kind="quoted" compact /> quoted
    </div>
  )
}
