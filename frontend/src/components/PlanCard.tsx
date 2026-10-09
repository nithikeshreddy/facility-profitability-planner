import { type ReactNode, useState } from 'react'
import type { Plan } from '../api'
import { usd } from '../format'
import MoneyValue from './MoneyValue'

const TYPE_LABELS: Record<Plan['plan_type'], string> = {
  current: 'Current',
  operational_fix: 'Operational fix',
  vendor_offer: 'Vendor offer',
  vendor_bundle: 'Vendor bundle',
}

interface Props {
  plan: Plan
  /** The recommended plan: feasible, beats current, and the best of those. */
  best?: boolean
  /** Saves this plan as a proposed action; rejects with the API's message. Omitted for the current plan. */
  onSave?: (plan: Plan, note: string) => Promise<void>
}

/** One plan side by side with the others: costs, projected contribution, feasibility and why. */
export default function PlanCard({ plan, best = false, onSave }: Props) {
  const isCurrent = plan.plan_type === 'current'
  const ring = best ? 'border-emerald-500 ring-2 ring-emerald-500' : 'border-slate-200'

  return (
    <section className={`flex flex-col rounded-lg border bg-white shadow-sm ${ring}`}>
      <header className="border-b border-slate-100 px-5 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{TYPE_LABELS[plan.plan_type]}</span>
          {best && <span className="rounded bg-emerald-600 px-2 py-0.5 text-xs font-semibold text-white">★ Recommended</span>}
          {plan.recommended && !best && (
            <span className="rounded bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800 ring-1 ring-inset ring-emerald-200">
              Also beats current
            </span>
          )}
          {plan.vendor_change && (
            <span className="rounded bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-800 ring-1 ring-inset ring-sky-200">
              Vendor change
            </span>
          )}
        </div>
        <h2 className="mt-1 text-base font-semibold text-slate-900">{plan.name}</h2>
        {plan.vendor_name && <p className="text-xs text-slate-500">Vendor: {plan.vendor_name}</p>}
      </header>

      <div className="flex flex-1 flex-col gap-4 px-5 py-4">
        <dl className="space-y-1.5 text-sm">
          <Row label={isCurrent ? 'Monthly cost' : 'Monthly cost (projected)'}>
            <MoneyValue money={plan.monthly_cost} />
          </Row>
          <Row label="Transition cost">
            {plan.transition_one_time.amount > 0 ? (
              <span className="flex flex-col items-end">
                <MoneyValue money={plan.transition_monthly} />
                <span className="text-xs text-slate-500">
                  {usd(plan.transition_one_time.amount)} one-time{plan.plan_type === 'vendor_bundle' ? ' for the bundle' : ''},
                  amortized
                </span>
              </span>
            ) : (
              <span className="text-slate-500">None</span>
            )}
          </Row>
          <Row label={!isCurrent && plan.bonus.amount > 0 ? 'Vendor bonus (full cap assumed)' : 'Vendor bonus'}>
            <MoneyValue money={plan.bonus} />
          </Row>
          <div className="border-t border-slate-200 pt-2">
            <Row label={<span className="font-medium text-slate-900">{isCurrent ? 'Contribution' : 'Projected contribution'}</span>}>
              <MoneyValue money={plan.projected_contribution} signed className="text-lg font-semibold" />
            </Row>
          </div>
          {!isCurrent && (
            <Row label="Change vs current (projected)">
              <MoneyValue money={plan.change} signed plus className="font-medium" />
            </Row>
          )}
        </dl>

        <Feasibility plan={plan} />

        <details className="text-sm">
          <summary className="cursor-pointer text-xs font-medium text-slate-600 hover:text-slate-900">Cost lines</summary>
          <table className="mt-1 w-full">
            <tbody>
              <tr className="border-b border-slate-100">
                <td className="py-1 pr-2 text-slate-700">Revenue</td>
                <td className="py-1 text-right">
                  <MoneyValue money={plan.revenue} compact />
                </td>
              </tr>
              {plan.lines.map((l) => (
                <tr key={l.key} className="border-b border-slate-100">
                  <td className="py-1 pr-2 text-slate-700">− {l.label}</td>
                  <td className="py-1 text-right">
                    <MoneyValue money={l.money} compact />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Why</h3>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-slate-600">
            {plan.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      </div>

      {onSave && <SaveFooter plan={plan} onSave={onSave} />}
    </section>
  )
}

function Row({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-slate-600">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  )
}

function Feasibility({ plan }: { plan: Plan }) {
  const f = plan.feasibility
  if (!f) {
    return (
      <p className="rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600">
        <span className="font-semibold text-emerald-700">✓ Feasible</span> — same vendor and crew; no route check needed.
      </p>
    )
  }
  return (
    <div
      className={`rounded-md px-3 py-2 text-xs ${
        f.feasible ? 'bg-emerald-50 text-emerald-900' : 'border border-red-200 bg-red-50 text-red-900'
      }`}
    >
      <p className="font-semibold">{f.feasible ? '✓ Feasible' : '✗ Not feasible'}</p>
      <ul className="mt-1 space-y-0.5">
        {f.reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
    </div>
  )
}

function SaveFooter({ plan, onSave }: { plan: Plan; onSave: (plan: Plan, note: string) => Promise<void> }) {
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const blocked = plan.feasible ? null : plan.reasons[0]

  async function confirm() {
    setSaving(true)
    setError(null)
    try {
      await onSave(plan, note)
      setOpen(false)
      setNote('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the proposed action.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <footer className="border-t border-slate-100 px-5 py-3">
      {!open ? (
        <>
          <button
            type="button"
            onClick={() => setOpen(true)}
            disabled={blocked !== null}
            title={blocked ?? undefined}
            className="w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600"
          >
            Save proposed action
          </button>
          {blocked && <p className="mt-2 text-xs text-red-800">Cannot be saved: {blocked}</p>}
        </>
      ) : (
        <div className="space-y-2">
          <label className="block text-xs font-medium text-slate-600">
            Note for the approving manager (optional)
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={2000}
              rows={3}
              className="mt-1 block w-full rounded border border-slate-300 px-2 py-1 text-sm font-normal text-slate-900"
              placeholder="e.g. Confirm the lockbox code with the site manager."
            />
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={confirm}
              disabled={saving}
              className="flex-1 rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-wait disabled:opacity-60"
            >
              {saving ? 'Saving…' : 'Confirm save'}
            </button>
            <button
              type="button"
              onClick={() => setOpen(false)}
              disabled={saving}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
            >
              Cancel
            </button>
          </div>
          {error && (
            <p role="alert" className="text-xs text-red-800">
              {error}
            </p>
          )}
        </div>
      )}
    </footer>
  )
}
