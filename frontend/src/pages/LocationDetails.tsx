import type { ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getLocation, getOverview, type LocationDetail, type Money, type Site } from '../api'
import Card from '../components/Card'
import ContributionWaterfall from '../components/ContributionWaterfall'
import CostRangeBar from '../components/CostRangeBar'
import DiagnosisPanel from '../components/DiagnosisPanel'
import LocationPicker from '../components/LocationPicker'
import LocationSwitcher from '../components/LocationSwitcher'
import MoneyValue from '../components/MoneyValue'
import SavedActions from '../components/SavedActions'
import { ErrorMessage, Loading } from '../components/StatusMessage'
import { count, formatAssumption, formatDate, formatMonth, minutes, number } from '../format'
import { useApi } from '../useApi'

export default function LocationDetails() {
  const { id } = useParams()
  const locationId = id ? Number(id) : null
  const detailedSites = useApi((signal) => getOverview({ detailed_only: true }, signal), [])

  if (locationId === null || Number.isNaN(locationId)) {
    return (
      <LocationPicker
        title="Location details"
        description="Choose one of the detailed locations to inspect its contribution, reasonable cost and evidence. Loss-making sites are listed first."
        sites={detailedSites.data?.sites}
        error={detailedSites.error}
        hrefFor={(siteId) => `/locations/${siteId}`}
      />
    )
  }
  return <LocationView locationId={locationId} sites={detailedSites.data?.sites ?? []} />
}

// ---------------------------------------------------------------- one location

function LocationView({ locationId, sites }: { locationId: number; sites: Site[] }) {
  const navigate = useNavigate()
  const { data, error, loading } = useApi((signal) => getLocation(locationId, signal), [locationId])

  const switcher = (
    <LocationSwitcher sites={sites} value={locationId} onChange={(siteId) => navigate(`/locations/${siteId}`)} />
  )

  if (error) {
    return (
      <div className="mx-auto max-w-7xl space-y-4">
        <div className="flex items-center justify-between gap-4">
          <Link to="/locations" className="text-sm text-slate-600 hover:underline">
            ← All detailed locations
          </Link>
          {switcher}
        </div>
        <ErrorMessage error={error} />
      </div>
    )
  }
  if (!data) return <Loading label="Loading location…" />

  return (
    <div className={`mx-auto max-w-7xl space-y-5 transition-opacity ${loading ? 'opacity-60' : ''}`}>
      <Header detail={data} switcher={switcher} />

      {data.missing_evidence.length > 0 && (
        <div role="status" className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-semibold">⚠ Evidence missing</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            {data.missing_evidence.map((m) => (
              <li key={m.key}>{m.message}</li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-amber-800">
            Conclusions that depend on these records are not drawn; record them before acting.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 2xl:grid-cols-2">
        <Card title="Contribution" subtitle={`${formatMonth(data.month)} · revenue minus every direct cost`}>
          <ContributionWaterfall contribution={data.contribution} />
          {data.incentive.has_program && (
            <p className="mt-3 text-xs text-slate-500">
              Vendor bonus {data.incentive.eligible ? 'earned' : 'not earned'} this month —{' '}
              <Link to="/incentives" className="underline hover:text-slate-800">
                see vendor incentives
              </Link>
              .
            </p>
          )}
        </Card>

        <Card
          title="Reasonable cost vs actual vs revenue"
          subtitle="What this work should cost locally, from labeled assumptions"
        >
          {data.reasonable_cost.available ? (
            <CostRangeBar revenue={data.contribution.revenue} actual={data.actual_cleaning_cost} range={data.reasonable_cost} />
          ) : (
            <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              <p className="font-medium">Evidence missing — no reasonable-cost range calculated</p>
              <ul className="mt-1 list-disc pl-5">
                {[...data.reasonable_cost.missing, ...data.reasonable_cost.reasons].map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </div>
          )}
          <p className="mt-3 text-xs text-slate-500">
            Actual cleaning cost is vendor invoices plus company-paid return visits.
          </p>
        </Card>
      </div>

      <Card
        title="Diagnosis"
        subtitle="Delivery problem: actual cost above the reasonable-cost high. Pricing/scope problem: reasonable cost (low end) above revenue. Both can apply."
      >
        <DiagnosisPanel
          diagnosis={data.diagnosis}
          locationId={data.location.id}
          missing={data.missing_evidence.map((m) => m.message)}
        />
      </Card>

      <SavedActions locationId={data.location.id} />

      {data.reasonable_cost.available && <CostBuildUp detail={data} />}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <ContractCard detail={data} />
        <ServiceCard detail={data} />
      </div>
    </div>
  )
}

function Header({ detail, switcher }: { detail: LocationDetail; switcher: ReactNode }) {
  const loc = detail.location
  const facts = [
    loc.building_type,
    loc.sq_ft != null ? `${count(loc.sq_ft)} sq ft` : null,
    loc.floors != null ? `${loc.floors} floor${loc.floors === 1 ? '' : 's'}` : null,
    loc.restrooms != null ? `${loc.restrooms} restroom${loc.restrooms === 1 ? '' : 's'}` : null,
  ].filter(Boolean)
  const loss = detail.contribution.total.amount < 0

  return (
    <header className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to="/locations" className="text-sm text-slate-600 hover:underline">
          ← All detailed locations
        </Link>
        {switcher}
      </div>
      <div className="flex items-end justify-between gap-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold">{loc.name}</h1>
            <span
              className={`rounded px-2 py-0.5 text-xs font-semibold ${
                loss ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
              }`}
            >
              {loss ? '▼ Loss-making' : '▲ Profitable'}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-600">
            {loc.code} · {loc.city}, {loc.state} · Customer: {loc.customer_account} · Current vendor:{' '}
            {loc.current_vendor_name ?? 'none recorded'}
          </p>
          {facts.length > 0 && <p className="mt-0.5 text-xs text-slate-500">{facts.join(' · ')}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-4">
          <div className="text-right">
            <div className="text-xs uppercase tracking-wide text-slate-500">Contribution, {formatMonth(detail.month)}</div>
            <MoneyValue money={detail.contribution.total} signed className="text-2xl font-semibold" />
          </div>
          <Link
            to={`/compare?location=${loc.id}`}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Compare plans →
          </Link>
        </div>
      </div>
    </header>
  )
}

function CostBuildUp({ detail }: { detail: LocationDetail }) {
  const r = detail.reasonable_cost
  const marginLow = r.assumptions.find((a) => a.key === 'margin_low')
  const marginHigh = r.assumptions.find((a) => a.key === 'margin_high')
  const rows: { label: string; money: Money; total?: boolean }[] = [
    { label: `Labor (${number(r.crew_minutes_per_visit)} crew min × ${number(r.visits_per_month)} visits/month)`, money: r.labor },
    { label: 'Travel', money: r.travel },
    { label: 'Supplies', money: r.supplies },
    { label: 'Base cost', money: r.base, total: true },
    { label: `Low (base + ${marginLow ? formatAssumption(marginLow) : 'low'} vendor margin)`, money: r.low },
    { label: `High (base + ${marginHigh ? formatAssumption(marginHigh) : 'high'} vendor margin)`, money: r.high },
  ]

  return (
    <Card title="How the reasonable cost is calculated" subtitle="Every assumption is stored on a record and shown here">
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div>
          <table className="w-full text-sm">
            <tbody>
              {rows.map((row) => (
                <tr key={row.label} className={`border-b border-slate-100 ${row.total ? 'border-t border-t-slate-300 font-semibold' : ''}`}>
                  <td className="py-1.5 pr-3 text-slate-700">{row.label}</td>
                  <td className="py-1.5 text-right">
                    <MoneyValue money={row.money} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <ul className="mt-3 space-y-0.5 text-xs text-slate-500">
            {r.reasons.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Assumptions</h3>
          <table className="mt-1 w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="py-1 pr-3 font-medium">Assumption</th>
                <th className="py-1 pr-3 text-right font-medium">Value</th>
                <th className="py-1 font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {r.assumptions.map((a) => (
                <tr key={a.key} className="border-t border-slate-100">
                  <td className="py-1.5 pr-3 text-slate-700">{a.label}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{formatAssumption(a)}</td>
                  <td className="py-1.5 text-xs text-slate-500">{a.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  )
}

function ContractCard({ detail }: { detail: LocationDetail }) {
  const c = detail.contract
  if (!c) {
    return (
      <Card title="Contract">
        <p className="text-sm text-amber-800">Evidence missing — no contract is recorded for this location.</p>
      </Card>
    )
  }
  const renewal =
    c.days_to_renewal >= 0 ? `in ${c.days_to_renewal} day${c.days_to_renewal === 1 ? '' : 's'}` : `${-c.days_to_renewal} days ago`
  return (
    <Card title="Contract">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
        <Fact label="Price (customer pays)">
          <MoneyValue money={c.price_monthly} /> <span className="text-slate-500">/ month</span>
        </Fact>
        <Fact label="Frequency">{c.frequency_per_week} visits / week</Fact>
        <Fact label="Start date">{formatDate(c.start_date)}</Fact>
        <Fact label="Renewal date">
          {formatDate(c.renewal_date)} <span className="text-slate-500">({renewal})</span>
        </Fact>
      </dl>
      <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Scope</h3>
      <ul className="mt-1 flex flex-wrap gap-1.5">
        {c.scope.map((s) => (
          <li key={s} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
            {s}
          </li>
        ))}
      </ul>
    </Card>
  )
}

function ServiceCard({ detail }: { detail: LocationDetail }) {
  const s = detail.service_requirements
  return (
    <Card title="Service requirements">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
        <Fact label="Service window">
          {s.window_start && s.window_end ? (
            <>
              {s.window_start}–{s.window_end}
              {s.window_minutes != null && <span className="text-slate-500"> ({minutes(s.window_minutes)})</span>}
            </>
          ) : (
            <span className="text-amber-800">Evidence missing</span>
          )}
        </Fact>
        <Fact label="Visits per week">{s.frequency_per_week ?? '—'}</Fact>
        <Fact label="Current crew size">{s.current_crew_size ?? '—'}</Fact>
        <Fact label="Crew minutes per visit">{minutes(s.crew_minutes_per_visit)}</Fact>
      </dl>
      <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Site tasks</h3>
      {s.tasks.length === 0 ? (
        <p className="mt-1 text-sm text-amber-800">Evidence missing — no site tasks recorded.</p>
      ) : (
        <table className="mt-1 w-full text-sm">
          <tbody>
            {s.tasks.map((t) => (
              <tr key={t.id} className="border-b border-slate-100">
                <td className="py-1.5 text-slate-700">{t.task}</td>
                <td className="py-1.5 text-right tabular-nums text-slate-700">{minutes(t.minutes)}</td>
              </tr>
            ))}
            <tr>
              <td className="py-1.5 font-medium">Total per visit</td>
              <td className="py-1.5 text-right font-medium tabular-nums">{minutes(s.crew_minutes_per_visit)}</td>
            </tr>
          </tbody>
        </table>
      )}
    </Card>
  )
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-slate-900">{children}</dd>
    </div>
  )
}
