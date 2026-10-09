import type { Contribution, Money } from '../api'
import { LOSS, PROFIT } from '../colors'
import { usd } from '../format'
import MoneyValue from './MoneyValue'

const REVENUE_FILL = '#334155' // slate-700
const COST_FILL = '#94a3b8' // slate-400

interface Step {
  key: string
  label: string
  money: Money
  from: number
  to: number
  fill: string
  muted?: boolean
  total?: boolean
}

/** Revenue, minus each cost line from the running total, down to contribution. Horizontal so labels stay readable. */
export default function ContributionWaterfall({ contribution }: { contribution: Contribution }) {
  const steps: Step[] = [
    {
      key: 'revenue',
      label: 'Revenue',
      money: contribution.revenue,
      from: 0,
      to: contribution.revenue.amount,
      fill: REVENUE_FILL,
    },
  ]
  let running = contribution.revenue.amount
  for (const line of contribution.lines) {
    const next = running - line.money.amount
    steps.push({
      key: line.key,
      label: line.label,
      money: { ...line.money, amount: -line.money.amount },
      from: running,
      to: next,
      fill: COST_FILL,
      muted: line.money.amount === 0,
    })
    running = next
  }
  const total = contribution.total
  steps.push({
    key: 'total',
    label: 'Contribution',
    money: total,
    from: 0,
    to: total.amount,
    fill: total.amount < 0 ? LOSS : PROFIT,
    total: true,
  })

  const values = steps.flatMap((s) => [s.from, s.to])
  const min = Math.min(0, ...values)
  const max = Math.max(0, ...values)
  const span = max - min || 1
  const x = (v: number) => ((v - min) / span) * 100

  return (
    <div>
      <div className="space-y-1.5">
        {steps.map((s) => {
          const left = x(Math.min(s.from, s.to))
          const width = Math.abs(x(s.to) - x(s.from))
          return (
            <div
              key={s.key}
              className={`grid grid-cols-[minmax(10rem,13.5rem)_1fr_7.5rem] items-center gap-3 text-sm ${
                s.total ? 'mt-2 border-t border-slate-200 pt-2.5 font-semibold' : ''
              } ${s.muted ? 'text-slate-400' : 'text-slate-700'}`}
            >
              <span className="truncate" title={s.label}>
                {s.key === 'revenue' || s.total ? s.label : `− ${s.label}`}
              </span>
              <div className="relative h-5">
                {min < 0 && (
                  <div className="absolute inset-y-[-4px] w-px bg-slate-400" style={{ left: `${x(0)}%` }} aria-hidden />
                )}
                {width > 0 && (
                  <div
                    className="absolute inset-y-0 rounded-sm"
                    style={{ left: `${left}%`, width: `max(${width}%, 2px)`, backgroundColor: s.fill }}
                    title={`${s.label}: ${usd(s.money.amount)}`}
                  />
                )}
              </div>
              <span className="text-right">
                <MoneyValue money={s.money} signed={s.total} />
              </span>
            </div>
          )
        })}
      </div>
      <ul className="mt-4 space-y-1 text-xs text-slate-600">
        {contribution.reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
    </div>
  )
}
