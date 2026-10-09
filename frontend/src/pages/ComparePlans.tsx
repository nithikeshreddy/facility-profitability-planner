import { useState } from 'react'
import { Link, useNavigate, useOutletContext, useSearchParams } from 'react-router-dom'
import {
  type Action,
  comparePlans,
  getLocation,
  getOverview,
  type Plan,
  type PlanComparison,
  type PlanOverrides,
  type Recommended,
  saveAction,
  type Site,
} from '../api'
import AssumptionsPanel from '../components/AssumptionsPanel'
import BundleMap from '../components/BundleMap'
import Card from '../components/Card'
import LocationPicker from '../components/LocationPicker'
import LocationSwitcher from '../components/LocationSwitcher'
import MoneyValue from '../components/MoneyValue'
import PlanCard from '../components/PlanCard'
import { ErrorMessage, Loading } from '../components/StatusMessage'
import { formatMonth, minutes } from '../format'
import { type LayoutContext, useApi } from '../useApi'

const TYPE_ORDER: Record<Plan['plan_type'], number> = { current: 0, operational_fix: 1, vendor_offer: 2, vendor_bundle: 3 }

export default function ComparePlans() {
  const [params] = useSearchParams()
  const { dataVersion } = useOutletContext<LayoutContext>()
  const detailedSites = useApi((signal) => getOverview({ detailed_only: true }, signal), [])
  const raw = params.get('location')
  const locationId = raw ? Number(raw) : NaN

  if (!Number.isInteger(locationId)) {
    return (
      <LocationPicker
        title="Compare plans"
        description="Choose a detailed location to compare its current delivery with an operational fix and vendor offers or bundles. Loss-making sites are listed first."
        sites={detailedSites.data?.sites}
        error={detailedSites.error}
        hrefFor={(id) => `/compare?location=${id}`}
      />
    )
  }
  // Remount on a new location or after Reset demo: assumption edits, open notes and confirmations start fresh.
  return <CompareView key={`${locationId}-${dataVersion}`} locationId={locationId} sites={detailedSites.data?.sites ?? []} />
}

function samePlan(p: Plan, r: Recommended | null): boolean {
  return r !== null && p.plan_type === r.plan_type && p.offer_id === r.offer_id && p.fix_id === r.fix_id
}

function planKey(p: Plan): string {
  return `${p.plan_type}:${p.offer_id ?? ''}:${p.fix_id ?? ''}`
}

function CompareView({ locationId, sites }: { locationId: number; sites: Site[] }) {
  const navigate = useNavigate()
  const [overrides, setOverrides] = useState<PlanOverrides>({})
  const [saved, setSaved] = useState<Action | null>(null)

  const detail = useApi((signal) => getLocation(locationId, signal), [locationId])
  // Keep the overrides that produced each response, so saving re-uses exactly what the cards show.
  const run = useApi(
    (signal) => comparePlans(locationId, overrides, signal).then((comparison) => ({ comparison, overrides })),
    [locationId, JSON.stringify(overrides)],
    { keepDataOnError: true },
  )

  async function save(plan: Plan, note: string) {
    const used = run.data?.overrides ?? {}
    const action = await saveAction({
      location_id: locationId,
      plan_type: plan.plan_type,
      offer_id: plan.offer_id,
      fix_id: plan.fix_id,
      overrides: Object.keys(used).length > 0 ? used : null,
      note: note.trim() || null,
    })
    setSaved(action)
    document.querySelector('main')?.scrollTo({ top: 0, behavior: 'smooth' }) // Layout's scroll container
  }

  const top = (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <Link to={`/locations/${locationId}`} className="text-sm text-slate-600 hover:underline">
        ← Location details
      </Link>
      <LocationSwitcher sites={sites} value={locationId} onChange={(id) => navigate(`/compare?location=${id}`)} />
    </div>
  )

  const error = detail.error ?? (run.data ? null : run.error)
  if (error) {
    return (
      <div className="mx-auto max-w-7xl space-y-4">
        {top}
        <ErrorMessage error={error} />
      </div>
    )
  }
  if (!detail.data || !run.data) return <Loading label="Evaluating plans…" />

  const loc = detail.data.location
  const comparison = run.data.comparison
  const plans = [comparison.current, ...comparison.options].sort((a, b) => TYPE_ORDER[a.plan_type] - TYPE_ORDER[b.plan_type])
  const best = comparison.options.find((p) => samePlan(p, comparison.recommended)) ?? null
  const bundles = comparison.options.filter((p) => p.sites.length > 0)
  const pricingFlag = detail.data.diagnosis.flags.find((f) => f.key === 'pricing_scope_problem')

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <header className="space-y-3">
        {top}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">Compare plans — {loc.name}</h1>
            <p className="mt-1 text-sm text-slate-600">
              {loc.code} · {loc.city}, {loc.state} · Current vendor: {loc.current_vendor_name ?? 'none recorded'} ·{' '}
              {formatMonth(detail.data.month)}
            </p>
          </div>
          <div className="text-right">
            <div className="text-xs uppercase tracking-wide text-slate-500">Current contribution</div>
            <MoneyValue money={comparison.current.projected_contribution} signed className="text-2xl font-semibold" />
          </div>
        </div>
      </header>

      {saved && <SavedConfirmation action={saved} onDismiss={() => setSaved(null)} />}

      <RecommendationBanner comparison={comparison} best={best} pricingReason={pricingFlag?.reasons[0] ?? null} />

      <AssumptionsPanel
        assumptions={comparison.assumptions}
        reasonableCost={comparison.reasonable_cost}
        overrides={run.data.overrides}
        onApply={setOverrides}
        running={run.loading}
        error={run.error}
      />

      <div className={`grid grid-cols-1 items-start gap-5 lg:grid-cols-2 2xl:grid-cols-3 ${run.loading ? 'opacity-60' : ''}`}>
        {plans.map((p) => (
          <PlanCard
            key={planKey(p)}
            plan={p}
            best={samePlan(p, comparison.recommended)}
            onSave={p.plan_type === 'current' ? undefined : save}
          />
        ))}
      </div>

      {bundles.map((p) => (
        <BundleSection key={planKey(p)} plan={p} />
      ))}

      <p className="text-xs text-slate-500">
        Projected figures use quoted prices and labeled assumptions; savings stay projected until invoices confirm them.
      </p>
    </div>
  )
}

function RecommendationBanner({
  comparison,
  best,
  pricingReason,
}: {
  comparison: PlanComparison
  best: Plan | null
  pricingReason: string | null
}) {
  if (!best) {
    return (
      <div role="status" className="rounded-lg border border-slate-300 bg-white px-5 py-4 text-sm shadow-sm">
        <p className="font-semibold text-slate-900">No plan recommended</p>
        <ul className="mt-1 space-y-0.5 text-slate-700">
          {comparison.recommendation_reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
        {pricingReason && (
          <p className="mt-2 text-slate-700">
            <span className="font-medium">Pricing/scope problem:</span> {pricingReason}{' '}
            <Link to="/renewals" className="font-medium underline hover:text-slate-900">
              Send to renewal review →
            </Link>
          </p>
        )}
      </div>
    )
  }
  return (
    <div role="status" className="rounded-lg border border-emerald-300 bg-emerald-50 px-5 py-4 text-sm text-emerald-950 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">★ Recommended plan</p>
          <p className="mt-0.5 text-lg font-semibold">{best.name}</p>
          {comparison.recommendation_reasons.map((r) => (
            <p key={r}>{r}</p>
          ))}
        </div>
        <div className="flex gap-6 text-right">
          <div>
            <div className="text-xs text-emerald-800">Projected contribution</div>
            <MoneyValue money={best.projected_contribution} signed className="text-lg font-semibold" />
          </div>
          <div>
            <div className="text-xs text-emerald-800">Change vs current</div>
            <MoneyValue money={best.change} signed plus className="text-lg font-semibold" />
          </div>
        </div>
      </div>
      <ul className="mt-2 list-disc space-y-0.5 pl-5 text-emerald-900">
        {best.reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
    </div>
  )
}

function SavedConfirmation({ action, onDismiss }: { action: Action; onDismiss: () => void }) {
  return (
    <div role="status" className="flex items-start justify-between gap-4 rounded-lg border border-green-300 bg-green-50 px-5 py-3 text-sm text-green-950">
      <div>
        <p className="font-semibold">✓ Saved as proposed — awaiting manager approval</p>
        <p className="mt-0.5">{action.summary}</p>
        {action.note && <p className="mt-0.5 italic">“{action.note}”</p>}
        <Link to={`/locations/${action.location_id}`} className="mt-1 inline-block font-medium underline">
          View proposed actions on location details →
        </Link>
      </div>
      <button type="button" onClick={onDismiss} aria-label="Dismiss" className="text-green-800 hover:text-green-950">
        ✕
      </button>
    </div>
  )
}

function BundleSection({ plan }: { plan: Plan }) {
  return (
    <Card
      title={`${plan.name}: route and per-site results`}
      subtitle={`${plan.sites.length} sites on one route, in stop order. The quoted price and transition cost are split equally across the sites.`}
    >
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-5">
        <div className="xl:col-span-2">
          <BundleMap sites={plan.sites} />
        </div>
        <div className="overflow-x-auto xl:col-span-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                <th className="py-1.5 pr-3 font-medium">Stop</th>
                <th className="py-1.5 pr-3 font-medium">Site</th>
                <th className="py-1.5 pr-3 font-medium">Route check</th>
                <th className="py-1.5 pr-3 text-right font-medium">Current</th>
                <th className="py-1.5 pr-3 text-right font-medium">Projected</th>
                <th className="py-1.5 text-right font-medium">Change</th>
              </tr>
            </thead>
            <tbody>
              {plan.sites.map((s, i) => (
                <tr key={s.location_id} className={`border-b border-slate-100 ${s.is_this_location ? 'bg-slate-50 font-medium' : ''}`}>
                  <td className="py-2 pr-3 tabular-nums">{i + 1}</td>
                  <td className="py-2 pr-3">
                    {s.is_this_location ? (
                      <>
                        {s.location_name} <span className="text-xs font-normal text-slate-500">(this location)</span>
                      </>
                    ) : (
                      <Link to={`/compare?location=${s.location_id}`} className="hover:underline">
                        {s.location_name}
                      </Link>
                    )}
                  </td>
                  <td className={`py-2 pr-3 whitespace-nowrap ${s.fits ? 'text-emerald-800' : 'text-red-800'}`}>
                    {s.fits ? '✓' : '✗'} {minutes(s.required_minutes)}
                    {s.window_minutes != null ? ` of ${minutes(s.window_minutes)}` : ' — window missing'}
                  </td>
                  <td className="py-2 pr-3 text-right">
                    <MoneyValue money={s.current_contribution} signed compact />
                  </td>
                  <td className="py-2 pr-3 text-right">
                    <MoneyValue money={s.projected_contribution} signed compact />
                  </td>
                  <td className="py-2 text-right">
                    <MoneyValue money={s.change} signed plus compact />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {plan.feasibility && (
            <p className="mt-2 text-xs text-slate-500">{plan.feasibility.reasons[plan.feasibility.reasons.length - 1]}</p>
          )}
        </div>
      </div>
    </Card>
  )
}
