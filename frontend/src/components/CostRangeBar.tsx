import type { ReactNode } from 'react'
import type { CostRange, Money } from '../api'
import { usd } from '../format'
import KindBadge from './KindBadge'
import MoneyValue from './MoneyValue'

const BAND_FILL = '#fcd34d' // amber-300: estimated values share the "estimated" badge hue
const ACTUAL_FILL = '#0f172a' // slate-900
const REVENUE_FILL = '#0369a1' // sky-700

interface Props {
  revenue: Money
  actual: Money
  range: CostRange
}

/** One scale: the reasonable-cost band (estimated) against actual cleaning cost and revenue. */
export default function CostRangeBar({ revenue, actual, range }: Props) {
  const max = Math.max(revenue.amount, actual.amount, range.high.amount) * 1.08 || 1
  const x = (v: number) => `${(Math.max(0, v) / max) * 100}%`
  const step = max > 3000 ? 1000 : max > 1500 ? 500 : 250
  const ticks = Array.from({ length: Math.floor(max / step) + 1 }, (_, i) => i * step)

  return (
    <div>
      <div className="relative mx-1 pb-6 pt-7">
        {/* actual-cost label above the track */}
        <Marker at={x(actual.amount)} color={ACTUAL_FILL} label={`Actual ${usd(actual.amount)}`} position="top" />
        <div className="relative h-8 rounded bg-slate-100">
          <div
            className="absolute inset-y-0 rounded-sm"
            style={{
              left: x(range.low.amount),
              width: `calc(${x(range.high.amount)} - ${x(range.low.amount)})`,
              backgroundColor: BAND_FILL,
            }}
            title={`Reasonable cost ${usd(range.low.amount)}–${usd(range.high.amount)} (estimated)`}
          />
          <Tick at={x(actual.amount)} color={ACTUAL_FILL} width={3} title={`Actual cleaning cost ${usd(actual.amount)}`} />
          <Tick at={x(revenue.amount)} color={REVENUE_FILL} width={2} dashed title={`Revenue ${usd(revenue.amount)}`} />
        </div>
        <Marker at={x(revenue.amount)} color={REVENUE_FILL} label={`Revenue ${usd(revenue.amount)}`} position="bottom" />
      </div>
      <div className="relative mx-1 h-4 text-[10px] text-slate-400">
        {ticks.map((t) => (
          <span key={t} className="absolute -translate-x-1/2" style={{ left: x(t) }}>
            {usd(t)}
          </span>
        ))}
      </div>

      <dl className="mt-4 grid grid-cols-[1.4fr_1fr_1fr] gap-3 text-sm">
        <Legend swatch={<span className="h-3 w-3 rounded-sm" style={{ backgroundColor: BAND_FILL }} />} label="Reasonable cost">
          {range.low.kind === range.high.kind ? (
            <span className="inline-flex items-center gap-1.5 whitespace-nowrap tabular-nums">
              {usd(range.low.amount)}–{usd(range.high.amount)}
              <KindBadge kind={range.low.kind} />
            </span>
          ) : (
            <>
              <MoneyValue money={range.low} /> <span className="text-slate-400">–</span> <MoneyValue money={range.high} />
            </>
          )}
        </Legend>
        <Legend swatch={<span className="h-3 w-[3px]" style={{ backgroundColor: ACTUAL_FILL }} />} label="Actual cleaning cost">
          <MoneyValue money={actual} />
        </Legend>
        <Legend
          swatch={<span className="h-3 w-0 border-l-2 border-dashed" style={{ borderColor: REVENUE_FILL }} />}
          label="Revenue"
        >
          <MoneyValue money={revenue} />
        </Legend>
      </dl>
    </div>
  )
}

function Tick({ at, color, width, dashed, title }: { at: string; color: string; width: number; dashed?: boolean; title: string }) {
  return (
    <div
      className="absolute -inset-y-1.5"
      style={{
        left: `calc(${at} - ${width / 2}px)`,
        width: 0,
        borderLeft: `${width}px ${dashed ? 'dashed' : 'solid'} ${color}`,
      }}
      title={title}
    />
  )
}

function Marker({ at, color, label, position }: { at: string; color: string; label: string; position: 'top' | 'bottom' }) {
  return (
    <span
      className={`absolute -translate-x-1/2 whitespace-nowrap text-[11px] font-medium ${position === 'top' ? 'top-1' : 'bottom-0'}`}
      style={{ left: `clamp(3rem, ${at}, calc(100% - 3rem))`, color }}
    >
      {label}
    </span>
  )
}

function Legend({ swatch, label, children }: { swatch: ReactNode; label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="flex items-center gap-2 text-xs text-slate-500">
        {swatch}
        {label}
      </dt>
      <dd className="mt-1 flex flex-wrap items-center gap-1">{children}</dd>
    </div>
  )
}
