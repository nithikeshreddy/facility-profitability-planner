import { Link } from 'react-router-dom'
import { listActions } from '../api'
import { formatDateTime } from '../format'
import { useApi } from '../useApi'
import Card from './Card'
import MoneyValue from './MoneyValue'
import { ErrorMessage, Loading } from './StatusMessage'

const OVERRIDE_LABELS: Record<string, (v: number) => string> = {
  local_loaded_wage: (v) => `wage $${v}/hr`,
  margin_low: (v) => `margin low ${Math.round(v * 1000) / 10}%`,
  margin_high: (v) => `margin high ${Math.round(v * 1000) / 10}%`,
  return_visit_reduction: (v) => `return visits removed ${Math.round(v * 1000) / 10}%`,
  amortization_months: (v) => `amortized over ${v} months`,
}

/** Proposed actions saved from Compare plans for one location. Re-fetched after Reset demo (which clears them). */
export default function SavedActions({ locationId }: { locationId: number }) {
  const { data, error } = useApi((signal) => listActions(locationId, signal), [locationId])

  return (
    <Card
      title="Proposed actions"
      subtitle="Saved from Compare plans. Savings stay projected until invoices confirm them; a manager approves every change."
      actions={
        <Link to={`/compare?location=${locationId}`} className="shrink-0 text-sm text-slate-600 underline hover:text-slate-900">
          Compare plans
        </Link>
      }
    >
      {error && <ErrorMessage error={error} />}
      {!data && !error && <Loading label="Loading proposed actions…" />}
      {data && data.length === 0 && (
        <p className="text-sm text-slate-500">
          No proposed actions saved yet.{' '}
          <Link to={`/compare?location=${locationId}`} className="underline hover:text-slate-800">
            Compare plans
          </Link>{' '}
          to propose one.
        </p>
      )}
      {data && data.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {data.map((a) => (
            <li key={a.id} className="py-3 first:pt-0 last:pb-0">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-900">{a.summary}</p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    <span className="rounded bg-amber-100 px-1.5 py-px font-medium text-amber-900">
                      Proposed — awaiting manager approval
                    </span>{' '}
                    · saved {formatDateTime(a.created_at)}
                    {a.overrides && Object.keys(a.overrides).length > 0 && (
                      <>
                        {' '}
                        · assumptions:{' '}
                        {Object.entries(a.overrides)
                          .map(([k, v]) => OVERRIDE_LABELS[k]?.(v) ?? `${k} ${v}`)
                          .join(', ')}
                      </>
                    )}
                  </p>
                  {a.note && <p className="mt-1 text-sm italic text-slate-700">“{a.note}”</p>}
                </div>
                <div className="text-right">
                  <div className="text-xs text-slate-500">Projected contribution</div>
                  <MoneyValue money={a.projected_contribution} signed className="font-semibold" />
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
