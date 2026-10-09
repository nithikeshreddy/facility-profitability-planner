import { Fragment, useEffect, useState } from 'react'
import { Link, useOutletContext, useSearchParams } from 'react-router-dom'
import { type Action, getRenewals, type Money, type RenewalItem, type RenewalTrigger, saveAction } from '../api'
import Card from '../components/Card'
import MoneyValue from '../components/MoneyValue'
import SaveActionButton from '../components/SaveActionButton'
import { ErrorMessage, Loading } from '../components/StatusMessage'
import { formatDate } from '../format'
import { type LayoutContext, useApi } from '../useApi'

const TRIGGERS: Record<RenewalTrigger, { label: string; style: string }> = {
  pricing_scope_problem: { label: 'Pricing/scope problem', style: 'bg-violet-100 text-violet-900' },
  loss_after_best_plan: { label: 'Loss-making after best plan', style: 'bg-red-100 text-red-900' },
}

const COLUMNS = ['Location', 'Revenue', 'Reasonable cost', 'Actual cost', 'Monthly gap', 'Renewal']

function percent(ratio: number): string {
  return `${Math.round(ratio * 1000) / 10}%`
}

function days(n: number): string {
  if (n === 0) return 'today'
  return n > 0 ? `in ${n} day${n === 1 ? '' : 's'}` : `${-n} day${n === -1 ? '' : 's'} ago`
}

export default function RenewalReview() {
  const { dataVersion } = useOutletContext<LayoutContext>()
  // Remount after Reset demo so save confirmations start fresh.
  return <RenewalView key={dataVersion} />
}

function RenewalView() {
  const [params] = useSearchParams()
  const highlightId = Number(params.get('location')) || null
  const { data, error } = useApi((signal) => getRenewals(signal), [])
  const [saved, setSaved] = useState<Record<number, Action>>({})

  useEffect(() => {
    if (data && highlightId) document.getElementById(`renewal-${highlightId}`)?.scrollIntoView({ block: 'center' })
  }, [data, highlightId])

  async function save(item: RenewalItem, note: string) {
    const action = await saveAction({ location_id: item.location_id, plan_type: 'renewal_review', note: note.trim() || null })
    setSaved((s) => ({ ...s, [item.location_id]: action }))
  }

  const highlightMissing = data && highlightId && !data.items.some((i) => i.location_id === highlightId)

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <header>
        <h1 className="text-2xl font-semibold">Renewal review</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          Contracts where the reasonable cost is above revenue (a pricing/scope problem no vendor change can fix), or
          that stay loss-making after the best feasible plan. Sorted by renewal date, then by the largest monthly gap.
          {data && (
            <>
              {' '}
              Suggested prices reach a {percent(data.target_margin)} target margin; as of {formatDate(data.as_of)}.
            </>
          )}
        </p>
      </header>

      {error && <ErrorMessage error={error} />}
      {!data && !error && <Loading label="Building the renewal queue…" />}

      {highlightMissing && (
        <p role="status" className="rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700">
          The selected location is not in the renewal queue: its reasonable cost is not above revenue and it is not
          loss-making after the best feasible plan.
        </p>
      )}

      {data && (
        <Card
          title={`${data.items.length} contract${data.items.length === 1 ? '' : 's'} to review before renewal`}
          subtitle="Suggested prices are projected until a renewed contract and invoices confirm them. A manager approves every change."
        >
          {data.items.length === 0 ? (
            <p className="text-sm text-slate-500">No contracts need a renewal review.</p>
          ) : (
            <table className="w-full table-fixed text-sm">
              <colgroup>
                <col />
                <col className="w-28" />
                <col className="w-48" />
                <col className="w-28" />
                <col className="w-28" />
                <col className="w-36" />
              </colgroup>
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                  {COLUMNS.map((c, i) => (
                    <th key={c} className={`px-3 pb-2 ${i > 0 && i < 5 ? 'text-right' : ''}`}>
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <QueueRows
                    key={item.location_id}
                    item={item}
                    highlighted={item.location_id === highlightId}
                    saved={saved[item.location_id] ?? null}
                    onSave={(note) => save(item, note)}
                  />
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}
    </div>
  )
}

function QueueRows({
  item,
  highlighted,
  saved,
  onSave,
}: {
  item: RenewalItem
  highlighted: boolean
  saved: Action | null
  onSave: (note: string) => Promise<void>
}) {
  const tint = highlighted ? 'bg-sky-50' : ''
  const edge = highlighted ? 'border-l-4 border-l-sky-500' : 'border-l-4 border-l-transparent'
  const price = item.suggestions.find((s) => s.key === 'price_review')
  const others = item.suggestions.filter((s) => s.key !== 'price_review')

  return (
    <Fragment>
      <tr id={`renewal-${item.location_id}`} className={`${tint} ${edge} align-top`} aria-current={highlighted || undefined}>
        <td className="px-3 pt-3">
          <Link to={`/locations/${item.location_id}`} className="font-medium text-slate-900 underline-offset-2 hover:underline">
            {item.location_name}
          </Link>
          {highlighted && <span className="ml-2 rounded bg-sky-600 px-1.5 py-0.5 text-[11px] font-medium text-white">Selected</span>}
        </td>
        <td className="px-3 pt-3 text-right">
          <MoneyValue money={item.revenue} compact />
        </td>
        <td className="px-3 pt-3 text-right">
          {item.estimate_low && item.estimate_high ? (
            <MoneyRange low={item.estimate_low} high={item.estimate_high} />
          ) : (
            <span className="text-xs text-amber-800">Evidence missing</span>
          )}
        </td>
        <td className="px-3 pt-3 text-right">
          {item.actual_cost ? <MoneyValue money={item.actual_cost} compact /> : <span className="text-slate-400">—</span>}
        </td>
        <td className="px-3 pt-3 text-right">
          <MoneyValue money={item.monthly_gap} compact className="text-red-700" />
          <div className="text-xs text-slate-500">cost above revenue</div>
        </td>
        <td className="px-3 pt-3">
          <div className="text-slate-900">{formatDate(item.renewal_date)}</div>
          <div className={`text-xs ${item.days_to_renewal <= 45 ? 'font-medium text-amber-800' : 'text-slate-500'}`}>
            {days(item.days_to_renewal)}
          </div>
        </td>
      </tr>
      <tr className={`${tint} ${edge} border-b border-slate-200`}>
        <td colSpan={COLUMNS.length} className="px-3 pb-4 pt-3">
          <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_15rem] gap-5">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Why it is in the queue</h3>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {item.triggers.map((t) => (
                  <span key={t} className={`rounded px-2 py-0.5 text-xs font-semibold ${TRIGGERS[t].style}`}>
                    {TRIGGERS[t].label}
                  </span>
                ))}
              </div>
              <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-xs text-slate-600">
                {item.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Suggested review</h3>
              <div className="mt-1 flex flex-wrap items-baseline gap-x-2 text-sm">
                <span className="text-slate-700">Price to reach a {percent(item.target_margin)} margin:</span>
                <MoneyValue money={item.suggested_price} className="font-semibold" />
                <span className="text-xs text-slate-500">/month</span>
              </div>
              <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-xs text-slate-600">
                {price && <li>{price.text}</li>}
                {others.map((s) => (
                  <li key={s.key}>{s.text}</li>
                ))}
              </ul>
            </div>
            <div>
              {saved ? (
                <div role="status" className="rounded-md border border-green-300 bg-green-50 px-3 py-2 text-xs text-green-950">
                  <p className="font-semibold">✓ Saved as proposed — awaiting manager approval</p>
                  <p className="mt-1">
                    Projected contribution <MoneyValue money={saved.projected_contribution} signed compact />
                  </p>
                  {saved.note && <p className="mt-1 italic">“{saved.note}”</p>}
                  <Link to={`/locations/${saved.location_id}`} className="mt-1 inline-block font-medium underline">
                    View on location details →
                  </Link>
                </div>
              ) : (
                <SaveActionButton onSave={onSave} placeholder="e.g. Raise the price at renewal or cut to 3 visits a week." />
              )}
            </div>
          </div>
        </td>
      </tr>
    </Fragment>
  )
}

function MoneyRange({ low, high }: { low: Money; high: Money }) {
  return (
    <span className="inline-flex flex-col items-end">
      <MoneyValue money={low} compact />
      <span className="text-xs text-slate-500">to</span>
      <MoneyValue money={high} compact />
    </span>
  )
}
