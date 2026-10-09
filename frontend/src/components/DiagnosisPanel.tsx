import { Link } from 'react-router-dom'
import type { Diagnosis, EvidenceItem, Flag } from '../api'
import { formatDate } from '../format'
import MoneyValue from './MoneyValue'

const FLAG_STYLES: Record<string, { pill: string; border: string; icon: string }> = {
  delivery_problem: { pill: 'bg-orange-100 text-orange-900', border: 'border-l-orange-500', icon: '⚙' },
  pricing_scope_problem: { pill: 'bg-violet-100 text-violet-900', border: 'border-l-violet-500', icon: '$' },
}
const DEFAULT_STYLE = { pill: 'bg-slate-100 text-slate-800', border: 'border-l-slate-400', icon: '!' }

const RECORD_LABELS: Record<string, string> = {
  invoice: 'Invoice line',
  cost_item: 'Cost item',
  issue: 'Issue',
  service_visit: 'Service visit',
  inspection: 'Inspection',
  site_task: 'Site task',
  contract: 'Contract',
  location: 'Location',
}

// Evidence grouped in this order: money first, then what happened on site.
const RECORD_ORDER = ['contract', 'invoice', 'cost_item', 'issue', 'service_visit', 'inspection', 'site_task', 'location']

interface Props {
  diagnosis: Diagnosis
  locationId: number
  /** Messages already shown in the "Evidence missing" warning; not repeated here. */
  missing: string[]
}

export default function DiagnosisPanel({ diagnosis, locationId, missing }: Props) {
  if (diagnosis.flags.length === 0) {
    const reasons = diagnosis.reasons.filter((r) => !missing.includes(r))
    // With evidence missing, "no problem" is only as good as the records we have — don't show it as a green all-clear.
    const style = missing.length
      ? 'border-slate-200 bg-slate-50 text-slate-800'
      : 'border-green-200 bg-green-50 text-green-900'
    return (
      <div className={`rounded-md border px-4 py-3 text-sm ${style}`}>
        <p className="font-medium">
          {missing.length
            ? 'No delivery or pricing/scope problem found in the records available — see the missing evidence above'
            : '✓ No delivery or pricing/scope problem found'}
        </p>
        {reasons.length > 0 && (
          <ul className="mt-1 space-y-0.5">
            {reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
      </div>
    )
  }
  return (
    <div className="space-y-4">
      {diagnosis.flags.length > 1 && (
        <p className="text-sm text-slate-600">
          Both problems apply: fix how the work is delivered <em>and</em> review the price or scope at renewal.
        </p>
      )}
      {diagnosis.flags.map((f) => (
        <FlagCard key={f.key} flag={f} locationId={locationId} />
      ))}
    </div>
  )
}

function FlagCard({ flag, locationId }: { flag: Flag; locationId: number }) {
  const style = FLAG_STYLES[flag.key] ?? DEFAULT_STYLE
  const next =
    flag.key === 'pricing_scope_problem'
      ? { to: '/renewals', label: 'Open renewal review' }
      : { to: `/compare?location=${locationId}`, label: 'Compare possible fixes' }
  const groups = groupEvidence(flag.evidence)

  return (
    <div className={`rounded-md border border-l-4 border-slate-200 ${style.border} bg-white`}>
      <div className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
        <div>
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-semibold ${style.pill}`}>
              <span aria-hidden>{style.icon}</span>
              {flag.label}
            </span>
            <span className="text-sm font-medium text-slate-800">{flag.action}</span>
          </div>
          <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm text-slate-700">
            {flag.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
        <Link
          to={next.to}
          className="shrink-0 rounded border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          {next.label} →
        </Link>
      </div>

      <div className="border-t border-slate-100 px-4 py-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Evidence ({flag.evidence.length} record{flag.evidence.length === 1 ? '' : 's'})
        </h4>
        {flag.evidence.length === 0 ? (
          <p className="mt-2 text-sm text-slate-500">No individual records attached to this flag.</p>
        ) : (
          <table className="mt-2 w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="w-28 py-1 pr-3 font-medium">Date</th>
                <th className="py-1 pr-3 font-medium">Record</th>
                <th className="w-32 py-1 text-right font-medium">Amount</th>
              </tr>
            </thead>
            {groups.map(([type, items]) => (
              <tbody key={type} className="border-t border-slate-100">
                <tr>
                  <th colSpan={3} className="pb-0.5 pt-2 text-left text-xs font-medium text-slate-600">
                    {RECORD_LABELS[type] ?? type} · {items.length}
                  </th>
                </tr>
                {items.map((e) => (
                  <tr key={`${e.type}-${e.id}`} className="align-top">
                    <td className="py-1 pr-3 text-slate-600 tabular-nums">{e.date ? formatDate(e.date) : '—'}</td>
                    <td className="py-1 pr-3 text-slate-800">
                      {e.summary}
                      <span className="ml-1.5 text-xs text-slate-400">#{e.id}</span>
                    </td>
                    <td className="py-1 text-right">{e.money ? <MoneyValue money={e.money} /> : null}</td>
                  </tr>
                ))}
              </tbody>
            ))}
          </table>
        )}
      </div>
    </div>
  )
}

function groupEvidence(items: EvidenceItem[]): [string, EvidenceItem[]][] {
  const groups = new Map<string, EvidenceItem[]>()
  for (const e of items) groups.set(e.type, [...(groups.get(e.type) ?? []), e])
  const rank = (t: string) => (RECORD_ORDER.includes(t) ? RECORD_ORDER.indexOf(t) : RECORD_ORDER.length)
  return [...groups.entries()].sort(([a], [b]) => rank(a) - rank(b))
}
