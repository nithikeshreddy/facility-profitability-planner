import { type FormEvent, useState } from 'react'
import type { Assumption, CostRange, PlanOverrides } from '../api'
import Card from './Card'
import MoneyValue from './MoneyValue'

type Key = keyof PlanOverrides

interface Field {
  key: Key
  unit: string
  /** Stored as 0–1, edited as a percentage. */
  percent: boolean
  min: number
  max?: number
}

const FIELDS: Field[] = [
  { key: 'local_loaded_wage', unit: '$/hr', percent: false, min: 0.01 },
  { key: 'margin_low', unit: '%', percent: true, min: 0, max: 100 },
  { key: 'margin_high', unit: '%', percent: true, min: 0, max: 100 },
  { key: 'return_visit_reduction', unit: '%', percent: true, min: 0, max: 100 },
  { key: 'amortization_months', unit: 'months', percent: false, min: 1 },
]

interface Props {
  assumptions: Assumption[]
  reasonableCost: CostRange
  overrides: PlanOverrides
  onApply: (overrides: PlanOverrides) => void
  running: boolean
  error: Error | null
}

/** Editable assumptions. "Re-run" sends the edited values to POST /plans; the cards update from the response. */
export default function AssumptionsPanel({ assumptions, reasonableCost, overrides, onApply, running, error }: Props) {
  // Only what the user typed; untouched fields show the value the API used.
  const [edits, setEdits] = useState<Partial<Record<Key, string>>>({})
  const fields = FIELDS.flatMap((f) => {
    const a = assumptions.find((x) => x.key === f.key)
    return a ? [{ ...f, assumption: a }] : []
  })
  const shown = (f: Field, a: Assumption) =>
    edits[f.key] ?? String(Math.round((f.percent ? a.value * 100 : a.value) * 100) / 100)

  function submit(e: FormEvent) {
    e.preventDefault()
    const next: PlanOverrides = { ...overrides }
    for (const f of fields) {
      const raw = edits[f.key]
      if (raw === undefined || raw.trim() === '') continue
      const value = Number(raw)
      if (Number.isFinite(value)) next[f.key] = f.percent ? value / 100 : value
    }
    onApply(next)
  }

  function restore() {
    setEdits({})
    onApply({})
  }

  const hasOverrides = Object.keys(overrides).length > 0

  return (
    <Card
      title="Assumptions"
      subtitle="Edit and re-run: every card is recalculated by the API with these values."
    >
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {fields.map(({ assumption: a, ...f }) => (
            <label key={f.key} className="block text-xs text-slate-600">
              <span className="font-medium text-slate-700">{a.label}</span>
              <span className="mt-1 flex items-center gap-1.5">
                <input
                  type="number"
                  inputMode="decimal"
                  min={f.min}
                  max={f.max}
                  step="any" // only min/max are checked; a step would reject recorded values like $22.50
                  value={shown(f, a)}
                  onChange={(e) => setEdits((cur) => ({ ...cur, [f.key]: e.target.value }))}
                  className="w-full min-w-0 rounded border border-slate-300 px-2 py-1 text-sm tabular-nums text-slate-900"
                />
                <span className="shrink-0 text-slate-500">{f.unit}</span>
              </span>
              <span className={`mt-0.5 block ${a.source === 'override' ? 'font-medium text-amber-700' : 'text-slate-400'}`}>
                Source: {a.source}
              </span>
            </label>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-3">
          <div className="text-sm text-slate-700">
            Reasonable-cost range:{' '}
            {reasonableCost.available ? (
              <>
                <MoneyValue money={reasonableCost.low} /> – <MoneyValue money={reasonableCost.high} />
                <span className="text-slate-500"> per month</span>
              </>
            ) : (
              <span className="text-amber-800">Evidence missing — not calculated</span>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={restore}
              disabled={running || (!hasOverrides && Object.keys(edits).length === 0)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
            >
              Restore recorded values
            </button>
            <button
              type="submit"
              disabled={running}
              className="rounded-md bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-wait disabled:opacity-60"
            >
              {running ? 'Re-running…' : 'Re-run plans'}
            </button>
          </div>
        </div>
        {error && (
          <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            <span className="font-medium">Not accepted:</span> {error.message}
            <span className="mt-0.5 block text-xs">The cards still show the last valid run.</span>
          </p>
        )}
      </form>
    </Card>
  )
}
