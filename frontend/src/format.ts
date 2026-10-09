// Display formatting only — values themselves always come from the API.

import type { Assumption } from './api'

/** $1,234 or $67.50, with a true minus sign like the backend's reason sentences. */
export function usd(amount: number): string {
  const sign = amount < 0 ? '−' : ''
  const a = Math.abs(amount)
  const cents = Math.abs(a - Math.round(a)) >= 0.005
  return `${sign}$${a.toLocaleString('en-US', {
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  })}`
}

/** Compact form for KPI tiles: $4.62M, $641.6K. */
export function usdCompact(amount: number): string {
  const sign = amount < 0 ? '−' : ''
  return `${sign}$${Math.abs(amount).toLocaleString('en-US', { notation: 'compact', maximumFractionDigits: 2 })}`
}

export function count(n: number): string {
  return n.toLocaleString('en-US')
}

/** "2026-09-14" → "Sep 14, 2026" (parsed as a calendar date, not shifted by time zone). */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

/** "2026-09" → "September 2026". */
export function formatMonth(month: string): string {
  const [y, m] = month.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
}

export function minutes(n: number): string {
  return `${Number.isInteger(n) ? n : n.toFixed(1)} min`
}

export function number(n: number, digits = 2): string {
  return n.toLocaleString('en-US', { maximumFractionDigits: digits })
}

/** An assumption's value in its unit: 15%, $22/hr, 12 months. */
export function formatAssumption(a: Assumption): string {
  switch (a.unit) {
    case 'ratio':
      return `${number(a.value * 100, 1)}%`
    case 'USD':
      return usd(a.value)
    case 'USD/hr':
      return `${usd(a.value)}/hr`
    case 'min':
      return minutes(a.value)
    default:
      return `${number(a.value)} ${a.unit}`
  }
}

/** API timestamp → "Oct 8, 2026, 3:04 PM" local. Timestamps without a zone are UTC (the backend stores UTC). */
export function formatDateTime(iso: string): string {
  const utc = /(Z|[+-]\d\d:\d\d)$/i.test(iso) ? iso : `${iso}Z`
  return new Date(utc).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })
}
