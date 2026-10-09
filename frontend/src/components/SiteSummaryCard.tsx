import type { ReactNode } from 'react'
import type { Site } from '../api'
import MoneyValue from './MoneyValue'

/** Summary of a lightweight site: shown in the map popup and the table popover (no details page exists). */
export default function SiteSummaryCard({ site }: { site: Site }) {
  return (
    <div className="w-60 text-slate-900">
      <div className="text-sm font-semibold leading-tight">{site.name}</div>
      <div className="mt-0.5 text-xs text-slate-500">
        {site.code} · {site.city}, {site.state}
      </div>
      <dl className="mt-3 space-y-1.5 text-xs">
        <Row label="Revenue">
          <MoneyValue money={site.revenue} />
        </Row>
        <Row label="Direct costs">
          <MoneyValue money={site.direct_costs} />
        </Row>
        <Row label="Contribution">
          <MoneyValue money={site.contribution} signed className="font-semibold" />
        </Row>
      </dl>
      <p className="mt-3 rounded bg-slate-100 px-2 py-1 text-[11px] text-slate-600">
        Summary data only — no visits, issues or inspections are recorded for this site.
      </p>
    </div>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}
