import { type ReactNode, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  getVendorIncentives,
  type Incentive,
  type ResultChange,
  type Simulation,
  simulateIncentive,
  type TargetCheck,
  type VendorIncentive,
  type VendorLocation,
} from '../api'
import Card from '../components/Card'
import MoneyValue from '../components/MoneyValue'
import { ErrorMessage, Loading } from '../components/StatusMessage'
import { formatDate, formatMonth, number, percent } from '../format'
import { useApi } from '../useApi'

function unit(key: string): string {
  return key === 'inspection_avg' ? '' : '%'
}

function value(n: number, key: string): string {
  return `${number(n, 1)}${unit(key)}`
}

export default function VendorIncentives() {
  const { data, error } = useApi((signal) => getVendorIncentives(signal), [])
  // Vendors with a bonus program first; otherwise the API's order.
  const vendors = data ? [...data.vendors].sort((a, b) => Number(b.has_program) - Number(a.has_program)) : []

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <header>
        <h1 className="text-2xl font-semibold">Vendor incentives</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          Bonus = min(bonus rate × monthly invoice, cap), paid only when <em>every</em> target is met. Failures marked
          customer-caused are excluded from the calculation and listed for exception review. Contribution is shown after
          the bonus{data && <> · {formatMonth(data.month)}</>}.
        </p>
      </header>

      {error && <ErrorMessage error={error} />}
      {!data && !error && <Loading label="Checking vendor targets…" />}
      {vendors.map((v) => (v.has_program ? <ProgramVendorCard key={v.vendor_id} vendor={v} /> : <PlainVendorCard key={v.vendor_id} vendor={v} />))}
    </div>
  )
}

// ---------------------------------------------------------------- vendors with a bonus program

function ProgramVendorCard({ vendor }: { vendor: VendorIncentive }) {
  const t = vendor.targets
  return (
    <Card
      title={vendor.vendor_name}
      subtitle={
        <>
          Bonus program: {percent(vendor.bonus_rate ?? 0)} of the monthly invoice, capped at{' '}
          {vendor.bonus_cap && <MoneyValue money={vendor.bonus_cap} compact />}
          {t ? (
            <span className="mt-1.5 flex flex-wrap gap-1.5">
              <TargetChip>Visits completed ≥ {t.completion_min}%</TargetChip>
              <TargetChip>Inspection average ≥ {t.inspection_avg_min}</TargetChip>
              <TargetChip>Issues fixed within 24h ≥ {t.fix_within_24h_min}%</TargetChip>
            </span>
          ) : (
            <span className="mt-1 block text-amber-800">Evidence missing: no performance targets recorded.</span>
          )}
        </>
      }
      actions={<VendorTotals vendor={vendor} />}
    >
      <div className="space-y-6">
        {vendor.locations.map((l) => (
          <LocationResult key={l.location_id} vendorId={vendor.vendor_id} location={l} />
        ))}
        {vendor.locations.length === 0 && <p className="text-sm text-slate-500">No detailed locations served.</p>}

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Excluded — for exception review</h3>
          {vendor.exceptions.length === 0 ? (
            <p className="mt-1 text-sm text-slate-500">Nothing excluded this month.</p>
          ) : (
            <ul className="mt-1 space-y-1 text-sm text-slate-700">
              {vendor.exceptions.map((e) => (
                <li key={`${e.ref.type}-${e.ref.id}`} className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2">
                  <span className="font-medium">{e.location_name}:</span> {e.reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Card>
  )
}

function TargetChip({ children }: { children: ReactNode }) {
  return <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">{children}</span>
}

function VendorTotals({ vendor }: { vendor: VendorIncentive }) {
  return (
    <div className="flex shrink-0 gap-6 text-right">
      <div>
        <div className="text-xs text-slate-500">Bonus this month</div>
        <MoneyValue money={vendor.total_bonus} className="font-semibold" />
      </div>
      <div>
        <div className="text-xs text-slate-500">Contribution after bonus</div>
        <MoneyValue money={vendor.total_contribution} signed className="font-semibold" />
      </div>
    </div>
  )
}

function eligibility(inc: Incentive): { label: string; style: string } {
  if (inc.eligible) return { label: '✓ Eligible', style: 'bg-emerald-100 text-emerald-900' }
  if (inc.checks.some((c) => c.actual === null)) return { label: 'Evidence missing — no bonus', style: 'bg-amber-100 text-amber-900' }
  return { label: '✗ Not eligible', style: 'bg-red-100 text-red-900' }
}

function EligibilityPill({ incentive }: { incentive: Incentive }) {
  const e = eligibility(incentive)
  return <span className={`rounded px-2 py-0.5 text-xs font-semibold ${e.style}`}>{e.label}</span>
}

function LocationResult({ vendorId, location }: { vendorId: number; location: VendorLocation }) {
  const inc = location.incentive
  const canSimulate = location.inspections.length > 0 || location.issues.length > 0

  return (
    <section className="rounded-md border border-slate-200">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <Link to={`/locations/${location.location_id}`} className="font-medium text-slate-900 hover:underline">
            {location.name}
          </Link>
          <span className="text-xs text-slate-500">
            {location.code} · {location.city}, {location.state}
          </span>
          <EligibilityPill incentive={inc} />
        </div>
      </header>
      <div className="grid grid-cols-[minmax(0,1fr)_19rem] gap-5 px-4 py-3">
        <ChecksTable checks={inc.checks} />
        <dl className="space-y-1.5 text-sm">
          <Fact label="Monthly invoice (basis)">
            <MoneyValue money={inc.invoice_basis} />
          </Fact>
          <Fact label="Contribution before bonus">
            <MoneyValue money={location.contribution_before_bonus} signed />
          </Fact>
          <Fact label="Vendor bonus">
            <MoneyValue money={inc.bonus} />
          </Fact>
          <div className="border-t border-slate-200 pt-1.5">
            <Fact label={<span className="font-medium text-slate-900">Contribution after bonus</span>}>
              <MoneyValue money={location.contribution} signed className="font-semibold" />
            </Fact>
          </div>
        </dl>
      </div>
      {inc.reasons.length > 0 && (
        <details className="px-4 pb-3 text-xs">
          <summary className="cursor-pointer font-medium text-slate-600 hover:text-slate-900">Why</summary>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-slate-600">
            {inc.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </details>
      )}
      {canSimulate && <WhatIf vendorId={vendorId} location={location} />}
    </section>
  )
}

function Fact({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-slate-600">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  )
}

function ChecksTable({ checks, compareTo }: { checks: TargetCheck[]; compareTo?: TargetCheck[] }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-slate-200 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
          <th className="pb-1.5 pr-3">Target</th>
          <th className="pb-1.5 pr-3 text-right">Goal</th>
          <th className="pb-1.5 pr-3 text-right">Result</th>
          <th className="pb-1.5">Status</th>
        </tr>
      </thead>
      <tbody>
        {checks.map((c) => {
          const before = compareTo?.find((b) => b.key === c.key)
          const changed = before !== undefined && (before.actual !== c.actual || before.met !== c.met)
          return (
            <tr key={c.key} className={`border-b border-slate-100 align-top ${changed ? 'bg-amber-50' : ''}`}>
              <td className="py-1.5 pr-3">
                <div className="text-slate-800">{c.label}</div>
                <div className="text-xs text-slate-500">{c.detail}</div>
              </td>
              <td className="whitespace-nowrap py-1.5 pr-3 text-right tabular-nums text-slate-600">≥ {value(c.target, c.key)}</td>
              <td className="whitespace-nowrap py-1.5 pr-3 text-right tabular-nums">
                {c.actual === null ? <span className="text-amber-800">Evidence missing</span> : value(c.actual, c.key)}
              </td>
              <td className="whitespace-nowrap py-1.5">
                {c.met ? <span className="font-medium text-emerald-700">✓ Met</span> : <span className="font-medium text-red-700">✗ Not met</span>}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

// ---------------------------------------------------------------- what-if simulation

function sameChange(a: ResultChange | null, b: ResultChange): boolean {
  return a !== null && JSON.stringify(a) === JSON.stringify(b)
}

function WhatIf({ vendorId, location }: { vendorId: number; location: VendorLocation }) {
  const [change, setChange] = useState<ResultChange | null>(null)
  const [result, setResult] = useState<{ change: ResultChange; simulation: Simulation } | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [inspectionId, setInspectionId] = useState(location.inspections[0]?.id ?? 0)
  const selected = location.inspections.find((i) => i.id === inspectionId)
  const [score, setScore] = useState(String(selected?.score ?? ''))

  useEffect(() => {
    if (!change) return
    const controller = new AbortController()
    simulateIncentive(vendorId, change, controller.signal).then(
      (simulation) => setResult({ change, simulation }),
      (e: unknown) => {
        if (!controller.signal.aborted) setError(e instanceof Error ? e : new Error(String(e)))
      },
    )
    return () => controller.abort()
  }, [vendorId, change])

  function run(next: ResultChange) {
    setError(null)
    setChange(next)
  }

  function backToRecorded() {
    setChange(null)
    setResult(null)
    setError(null)
    setScore(String(selected?.score ?? ''))
  }

  const scoreValue = Number(score)
  const scoreValid = score.trim() !== '' && scoreValue >= 0 && scoreValue <= 100
  const sim = result && change && sameChange(change, result.change) ? result.simulation : null
  const running = change !== null && sim === null && error === null

  return (
    <div className="border-t border-dashed border-slate-300 bg-slate-50 px-4 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-900">What if one service result were different?</h3>
        <p className="text-xs text-slate-500">Simulation only — nothing is saved.</p>
      </div>

      <div className="mt-2 grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] gap-5">
        <div className="space-y-4 text-sm">
          {location.inspections.length > 0 && (
            <fieldset>
              <legend className="text-xs font-semibold uppercase tracking-wide text-slate-500">Change one inspection score</legend>
              <div className="mt-1.5 flex flex-wrap items-end gap-2">
                <label className="text-xs text-slate-600">
                  Inspection
                  <select
                    value={inspectionId}
                    onChange={(e) => {
                      const id = Number(e.target.value)
                      setInspectionId(id)
                      setScore(String(location.inspections.find((i) => i.id === id)?.score ?? ''))
                    }}
                    className="mt-0.5 block rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900"
                  >
                    {location.inspections.map((i) => (
                      <option key={i.id} value={i.id}>
                        {formatDate(i.date)} — recorded {i.score}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs text-slate-600">
                  New score
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={score}
                    onChange={(e) => setScore(e.target.value)}
                    className="mt-0.5 block w-20 rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900"
                  />
                </label>
                <button
                  type="button"
                  disabled={!scoreValid || scoreValue === selected?.score}
                  onClick={() => run({ inspection_id: inspectionId, score: scoreValue })}
                  className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600"
                >
                  Simulate
                </button>
              </div>
            </fieldset>
          )}

          {location.issues.length > 0 && (
            <fieldset>
              <legend className="text-xs font-semibold uppercase tracking-wide text-slate-500">Toggle customer-caused on an issue</legend>
              <ul className="mt-1.5 space-y-1.5">
                {location.issues.map((i) => {
                  const toggled: ResultChange = { issue_id: i.id, customer_caused: !i.customer_caused }
                  const active = sameChange(change, toggled)
                  const shown = active ? !i.customer_caused : i.customer_caused
                  return (
                    <li key={i.id} className={`flex items-start justify-between gap-3 rounded border bg-white px-2.5 py-1.5 ${active ? 'border-amber-400' : 'border-slate-200'}`}>
                      <div className="min-w-0 text-xs">
                        <div className="text-slate-800">
                          {formatDate(i.date)} · {i.category}: {i.description}
                        </div>
                        <div className="text-slate-500">
                          Recorded as {i.customer_caused ? 'customer-caused' : 'vendor-caused'}
                          {i.resolved_hours !== null && <> · fixed in {i.resolved_hours}h</>}
                        </div>
                      </div>
                      <label className="flex shrink-0 cursor-pointer items-center gap-1.5 text-xs text-slate-700">
                        <input
                          type="checkbox"
                          checked={shown}
                          onChange={() => (active ? backToRecorded() : run(toggled))}
                          className="h-3.5 w-3.5"
                        />
                        Customer-caused
                      </label>
                    </li>
                  )
                })}
              </ul>
            </fieldset>
          )}
        </div>

        <div aria-live="polite">
          {error && <ErrorMessage error={error} />}
          {!change && !error && (
            <p className="rounded-md border border-dashed border-slate-300 px-3 py-6 text-center text-sm text-slate-500">
              Change a score or a customer-caused flag to see eligibility and contribution before and after.
            </p>
          )}
          {running && <Loading label="Recalculating…" />}
          {sim && <BeforeAfter simulation={sim} onBack={backToRecorded} />}
        </div>
      </div>
    </div>
  )
}

function BeforeAfter({ simulation, onBack }: { simulation: Simulation; onBack: () => void }) {
  const { recorded, simulated } = simulation
  return (
    <div className="space-y-3">
      <div className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-950">
        <span className="font-semibold">Simulated change:</span> {simulation.changes.join(' ')}
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <th className="pb-1.5" />
            <th className="pb-1.5 text-right">Recorded</th>
            <th className="pb-1.5 text-right">Simulated</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b border-slate-100">
            <td className="py-1.5 text-slate-600">Eligibility</td>
            <td className="py-1.5 text-right">
              <EligibilityPill incentive={recorded.incentive} />
            </td>
            <td className="py-1.5 text-right">
              <EligibilityPill incentive={simulated.incentive} />
            </td>
          </tr>
          <tr className="border-b border-slate-100">
            <td className="py-1.5 text-slate-600">Vendor bonus</td>
            <td className="py-1.5 text-right">
              <MoneyValue money={recorded.incentive.bonus} />
            </td>
            <td className="py-1.5 text-right">
              <MoneyValue money={simulated.incentive.bonus} />
            </td>
          </tr>
          <tr>
            <td className="py-1.5 font-medium text-slate-900">Contribution after bonus</td>
            <td className="py-1.5 text-right">
              <MoneyValue money={recorded.contribution} signed className="font-semibold" />
            </td>
            <td className="py-1.5 text-right">
              <MoneyValue money={simulated.contribution} signed className="font-semibold" />
            </td>
          </tr>
        </tbody>
      </table>
      <ChecksTable checks={simulated.incentive.checks} compareTo={recorded.incentive.checks} />
      <button
        type="button"
        onClick={onBack}
        className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100"
      >
        Back to recorded results
      </button>
    </div>
  )
}

// ---------------------------------------------------------------- vendors without a bonus program

function PlainVendorCard({ vendor }: { vendor: VendorIncentive }) {
  return (
    <Card
      title={vendor.vendor_name}
      subtitle="No bonus program — no targets to check, and contribution carries no vendor bonus."
      actions={<VendorTotals vendor={vendor} />}
    >
      {vendor.locations.length === 0 ? (
        <p className="text-sm text-slate-500">No detailed locations served.</p>
      ) : (
        <ul className="divide-y divide-slate-100 text-sm">
          {vendor.locations.map((l) => (
            <li key={l.location_id} className="flex items-center justify-between gap-3 py-1.5">
              <span>
                <Link to={`/locations/${l.location_id}`} className="text-slate-900 hover:underline">
                  {l.name}
                </Link>{' '}
                <span className="text-xs text-slate-500">{l.code}</span>
              </span>
              <MoneyValue money={l.contribution} signed compact />
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
