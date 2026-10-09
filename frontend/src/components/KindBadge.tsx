import type { Kind } from '../api'

const STYLES: Record<Kind, string> = {
  actual: 'bg-slate-100 text-slate-700 ring-slate-300',
  estimated: 'bg-amber-50 text-amber-800 ring-amber-300',
  quoted: 'bg-sky-50 text-sky-800 ring-sky-300',
}

const HINTS: Record<Kind, string> = {
  actual: 'Actual — from invoices or recorded costs',
  estimated: 'Estimated — calculated from labeled assumptions',
  quoted: 'Quoted — from a vendor offer',
}

/** Small label for where a money value comes from. `compact` shows one letter (for dense tables). */
export default function KindBadge({ kind, compact = false }: { kind: Kind; compact?: boolean }) {
  return (
    <span
      title={HINTS[kind]}
      className={`inline-flex shrink-0 items-center rounded px-1 py-px text-[10px] font-medium uppercase leading-4 tracking-wide ring-1 ring-inset ${STYLES[kind]}`}
    >
      {compact ? kind[0] : kind}
    </span>
  )
}
