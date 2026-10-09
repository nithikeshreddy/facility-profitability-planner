import type { Money } from '../api'
import { usd } from '../format'
import KindBadge from './KindBadge'

interface Props {
  money: Money
  /** Color the amount by sign (red loss / green profit). */
  signed?: boolean
  /** Prefix positive amounts with "+" (for changes). */
  plus?: boolean
  compact?: boolean
  className?: string
}

/** A money amount with its kind badge. Every money value in the UI goes through here. */
export default function MoneyValue({ money, signed = false, plus = false, compact = false, className = '' }: Props) {
  const tone = !signed ? '' : money.amount < 0 ? 'text-red-700' : 'text-green-700'
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap tabular-nums ${className}`}>
      <span className={tone}>
        {plus && money.amount > 0 ? '+' : ''}
        {usd(money.amount)}
      </span>
      <KindBadge kind={money.kind} compact={compact} />
    </span>
  )
}
