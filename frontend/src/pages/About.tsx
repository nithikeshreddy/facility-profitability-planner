import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { getOverview } from '../api'
import Card from '../components/Card'
import KindBadge from '../components/KindBadge'
import { ErrorMessage, Loading } from '../components/StatusMessage'
import { useApi } from '../useApi'

// Explains the method only. Every figure lives on the linked screens, computed by the API from records.

interface CaseLink {
  label: string
  /** Location code to resolve to an id, or null for a page that needs none. */
  code: string | null
  href: (id: number) => string
}

interface DemoCase {
  title: string
  code: string
  story: ReactNode
  links: CaseLink[]
}

const CASES: DemoCase[] = [
  {
    title: '1. Suitable vendor bundle — Dallas',
    code: 'DAL-01',
    story: (
      <>
        Three nearby sites, each loss-making because two different vendors drive out separately. One vendor quotes a
        single route for all three. The bundle passes every service window and crew-capacity check, and each site's
        projected contribution turns positive.
      </>
    ),
    links: [{ label: 'Compare plans', code: 'DAL-01', href: (id) => `/compare?location=${id}` }],
  },
  {
    title: '2. Operational fix — Phoenix',
    code: 'PHX-01',
    story: (
      <>
        Company-paid return visits caused by a locked stockroom (four <em>access</em> issue records with dates). A
        one-time lockbox removes most return visits with no vendor change — a delivery problem fixed operationally.
      </>
    ),
    links: [
      { label: 'Location details', code: 'PHX-01', href: (id) => `/locations/${id}` },
      { label: 'Compare plans', code: 'PHX-01', href: (id) => `/compare?location=${id}` },
    ],
  },
  {
    title: '3. Underpriced agreement — Columbus',
    code: 'COL-01',
    story: (
      <>
        Even the low end of the reasonable-cost range is above revenue: a pricing/scope problem no vendor change can
        fix. The contract is in the renewal review queue with a suggested price.
      </>
    ),
    links: [
      { label: 'Location details', code: 'COL-01', href: (id) => `/locations/${id}` },
      { label: 'Renewal review', code: 'COL-01', href: (id) => `/renewals?location=${id}` },
    ],
  },
  {
    title: '4. Infeasible cheap offer — Atlanta',
    code: 'ATL-01',
    story: (
      <>
        A cheaper single-cleaner offer cannot finish inside the site's late-night service window, so it is rejected
        with a plain-English reason and cannot be saved as a proposed action.
      </>
    ),
    links: [{ label: 'Compare plans', code: 'ATL-01', href: (id) => `/compare?location=${id}` }],
  },
  {
    title: '5. Performance bonus — Denver',
    code: 'DEN-01',
    story: (
      <>
        The vendor meets every target and earns a capped bonus, which is part of contribution. Lower one inspection
        score, or un-mark a customer-caused failure, and the vendor becomes ineligible — contribution updates.
      </>
    ),
    links: [
      { label: 'Vendor incentives', code: null, href: () => '/incentives' },
      { label: 'Location details', code: 'DEN-01', href: (id) => `/locations/${id}` },
    ],
  },
  {
    title: 'Evidence missing — Minneapolis',
    code: 'MSP-01',
    story: (
      <>
        No inspections are recorded, so the app says <em>Evidence missing</em> instead of guessing.
      </>
    ),
    links: [{ label: 'Location details', code: 'MSP-01', href: (id) => `/locations/${id}` }],
  },
]

const INTERPRETATIONS: [string, ReactNode][] = [
  [
    'Return visits',
    <>
      Invoice lines marked as return visits <em>are</em> the company-paid return visits. "Vendor invoices" means base
      and extra lines only, so a return visit is never counted twice.
    </>,
  ],
  [
    'Vendor bonuses',
    'Contribution uses the bonus calculated by the incentive rules, so changing a service result changes contribution. A stored bonus cost is never added on top.',
  ],
  ['Travel to the first stop', 'Counts as 0 minutes in the feasibility check — it happens before the service window opens.'],
  [
    'Same-night capacity',
    "The crew-capacity check assumes every site in an offer is serviced the same night (worst case): total crew-minutes ≤ crews available × shift length.",
  ],
  ['Equal bundle split', "A bundle's quoted monthly price and amortized transition cost are split equally across its sites."],
  [
    'Vendor changes keep return visits',
    'A vendor offer or bundle keeps the current company-paid return visits; only an operational fix reduces them.',
  ],
  [
    'Renewal price',
    'Suggested price = max(monthly cost after the best feasible plan, reasonable-cost low) ÷ (1 − target margin). The default target margin is 10%.',
  ],
]

export default function About() {
  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <header>
        <h1 className="text-2xl font-semibold">About this demo</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          A prototype for the abrightlab 2,000-Location Challenge. An operations manager can open a loss-making
          location, inspect the evidence, compare possible fixes, review costs and feasibility, and save a proposed
          action. The loop: find the loss, prove its cause, apply the matching fix, and keep only changes confirmed by
          invoices. Savings are labeled <em>projected</em> until invoices confirm them, and managers approve every
          change.
        </p>
        <p className="mt-3 inline-block rounded bg-amber-100 px-2 py-1 text-sm font-medium text-amber-900">
          All data is synthetic.
        </p>
      </header>

      <Card title="Where to see each demo case" subtitle="Each link opens the screen where the numbers are computed from records.">
        <CaseList />
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Contribution" subtitle="Monthly, USD">
          <Formula>
            Contribution = revenue − vendor invoices − other direct costs − company-paid return visits − customer credits
            − vendor bonuses
          </Formula>
          <p className="mt-3 text-sm text-slate-600">
            Estimated labor and travel only <em>explain</em> an invoice; they are never added on top of an actual
            invoice.
          </p>
        </Card>

        <Card title="Reasonable cost" subtitle="What the work should cost, from the site profile">
          <ul className="space-y-1.5 text-sm text-slate-700">
            <li>
              <Formula inline>visits per month = frequency per week × 4.33</Formula>
            </li>
            <li>
              <Formula inline>labor = crew minutes per visit ÷ 60 × visits × local loaded wage</Formula>
            </li>
            <li>
              <Formula inline>travel = travel minutes per visit ÷ 60 × visits × local loaded wage</Formula>
            </li>
            <li>
              <Formula inline>supplies = supplies per visit × visits</Formula>
            </li>
            <li>
              <Formula inline>range = (labor + travel + supplies) × 1.15 to × 1.25</Formula>
            </li>
          </ul>
          <p className="mt-3 text-sm text-slate-600">
            Every assumption (wage, margin band, supplies) is stored, labeled, and shown on each location's details
            page, and can be changed in Compare plans.
          </p>
        </Card>

        <Card title="Diagnosis" subtitle="Both can be true; both are shown">
          <ul className="space-y-2 text-sm text-slate-700">
            <li>
              <span className="font-medium">Delivery problem</span> — actual cost is above the reasonable-cost high.
              Fix how the work is delivered: an operational fix, a vendor offer, or a vendor bundle.
            </li>
            <li>
              <span className="font-medium">Pricing/scope problem</span> — the reasonable-cost low is above revenue.
              Send the contract to renewal review for a price, scope, or frequency change.
            </li>
          </ul>
        </Card>

        <Card title="Plans and feasibility">
          <ul className="space-y-2 text-sm text-slate-700">
            <li>
              <Formula inline>
                projected contribution = revenue − projected vendor cost − projected other costs − bonus − transition
                cost ÷ 12
              </Formula>{' '}
              The bonus assumes the full cap, and only if that vendor has a bonus program.
            </li>
            <li>
              A plan is recommended only if it is <span className="font-medium">feasible</span> and beats current
              contribution.
            </li>
            <li>
              Feasible means each site's cleaning minutes ÷ crew size plus travel from the previous stop fits its
              service window, and total crew time fits the vendor's crews × shift length. A failed check gives the
              reason in a sentence.
            </li>
            <li>
              Vendor incentives: bonus = min(rate × monthly invoice, cap), paid only when every target is met.
              Customer-caused failures are excluded and listed for exception review.
            </li>
          </ul>
        </Card>
      </div>

      <Card title="Settled interpretations" subtitle="Each cost is counted once">
        <dl className="grid gap-x-6 gap-y-3 text-sm md:grid-cols-2">
          {INTERPRETATIONS.map(([term, text]) => (
            <div key={term}>
              <dt className="font-medium text-slate-900">{term}</dt>
              <dd className="mt-0.5 text-slate-600">{text}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card title="Money labels">
        <ul className="space-y-1.5 text-sm text-slate-700">
          <li className="flex items-center gap-2">
            <KindBadge kind="actual" /> from invoices or recorded costs
          </li>
          <li className="flex items-center gap-2">
            <KindBadge kind="estimated" /> calculated from labeled assumptions (including every projection)
          </li>
          <li className="flex items-center gap-2">
            <KindBadge kind="quoted" /> from a vendor offer
          </li>
        </ul>
        <p className="mt-3 text-sm text-slate-600">
          Explanations are rule-based templates — there are no live AI calls. <strong>All data is synthetic.</strong>{' '}
          Everyone shares one demo state; <span className="font-medium">Reset demo</span> restores it.
        </p>
      </Card>
    </div>
  )
}

function CaseList() {
  const { data, error } = useApi((signal) => getOverview({ detailed_only: true }, signal), [])
  const ids = new Map(data?.sites.map((s) => [s.code, s.id]))

  return (
    <div className="space-y-3">
      {error && <ErrorMessage error={error} />}
      {!data && !error && <Loading label="Finding the demo locations…" />}
      <ul className="divide-y divide-slate-100">
        {CASES.map((c) => (
          <li key={c.title} className="grid gap-2 py-3 first:pt-0 last:pb-0 md:grid-cols-[1fr_auto] md:gap-6">
            <div>
              <div className="text-sm font-medium text-slate-900">
                {c.title} <span className="font-normal text-slate-400">· {c.code}</span>
              </div>
              <p className="mt-0.5 text-sm text-slate-600">{c.story}</p>
            </div>
            <div className="flex flex-wrap items-start gap-2 md:justify-end">
              {c.links.map((l) => {
                const id = l.code === null ? 0 : ids.get(l.code)
                if (id === undefined) {
                  return data ? (
                    <span key={l.label} className="text-xs text-slate-400">
                      {l.label}: not in current data
                    </span>
                  ) : null
                }
                return (
                  <Link
                    key={l.label}
                    to={l.href(id)}
                    className="whitespace-nowrap rounded border border-slate-300 px-2.5 py-1 text-sm text-slate-700 hover:bg-slate-100"
                  >
                    {l.label} →
                  </Link>
                )
              })}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Formula({ children, inline = false }: { children: ReactNode; inline?: boolean }) {
  const Tag = inline ? 'span' : 'p'
  return <Tag className={`font-mono text-[13px] text-slate-800 ${inline ? '' : 'rounded bg-slate-50 px-3 py-2'}`}>{children}</Tag>
}
