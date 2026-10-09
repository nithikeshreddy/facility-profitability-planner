import { Link } from 'react-router-dom'
import type { Site } from '../api'
import MoneyValue from './MoneyValue'
import { ErrorMessage, Loading } from './StatusMessage'

interface Props {
  title: string
  description: string
  sites: Site[] | undefined
  error: Error | null
  hrefFor: (id: number) => string
}

/** Grid of the detailed locations, loss-making first. Shown when a page has no location selected. */
export default function LocationPicker({ title, description, sites, error, hrefFor }: Props) {
  const sorted = sites ? [...sites].sort((a, b) => a.contribution.amount - b.contribution.amount) : []
  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <header>
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </header>
      {error && <ErrorMessage error={error} />}
      {!sites && !error && <Loading />}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-3">
        {sorted.map((s) => (
          <Link
            key={s.id}
            to={hrefFor(s.id)}
            className="group rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm transition hover:border-slate-400 hover:shadow"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-medium text-slate-900 group-hover:underline">{s.name}</div>
                <div className="text-xs text-slate-500">
                  {s.code} · {s.city}, {s.state}
                </div>
              </div>
              <MoneyValue money={s.contribution} signed className="text-sm font-semibold" />
            </div>
            <div className="mt-2 flex gap-4 text-xs text-slate-500">
              <span>
                Revenue <MoneyValue money={s.revenue} compact />
              </span>
              <span>
                Costs <MoneyValue money={s.direct_costs} compact />
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
