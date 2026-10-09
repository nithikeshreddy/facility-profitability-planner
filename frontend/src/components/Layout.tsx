import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { resetDemo } from '../api'
import type { LayoutContext } from '../useApi'

const NAV_ITEMS = [
  { to: '/', label: 'Overview' },
  { to: '/locations', label: 'Location details' },
  { to: '/compare', label: 'Compare plans' },
  { to: '/renewals', label: 'Renewal review' },
  { to: '/incentives', label: 'Vendor incentives' },
]

export default function Layout() {
  const [dataVersion, setDataVersion] = useState(0)
  const [resetting, setResetting] = useState(false)
  const [resetError, setResetError] = useState<string | null>(null)

  async function onReset() {
    setResetting(true)
    setResetError(null)
    try {
      await resetDemo()
      setDataVersion((v) => v + 1)
    } catch (e) {
      setResetError(e instanceof Error ? e.message : 'Reset failed')
    } finally {
      setResetting(false)
    }
  }

  const context: LayoutContext = { dataVersion }

  return (
    <div className="flex h-screen flex-col bg-slate-50 text-slate-900">
      <div className="bg-amber-100 px-4 py-1.5 text-center text-sm font-medium text-amber-900">
        Demonstration data — all locations, vendors, and figures are synthetic.
      </div>
      <div className="flex min-h-0 flex-1">
        <nav className="flex w-56 shrink-0 flex-col border-r border-slate-200 bg-white">
          <div className="px-4 py-4">
            <div className="text-base font-semibold leading-tight">Facility Profitability Planner</div>
            <div className="mt-1 text-xs text-slate-500">Managers approve every change</div>
          </div>
          <ul className="flex-1 space-y-1 px-2">
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `block rounded px-3 py-2 text-sm ${
                      isActive ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
          <div className="border-t border-slate-200 p-3">
            <button
              type="button"
              onClick={onReset}
              disabled={resetting}
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 disabled:cursor-wait disabled:opacity-60"
            >
              {resetting ? 'Resetting…' : 'Reset demo'}
            </button>
            {resetError && <p className="mt-2 text-xs text-red-700">{resetError}</p>}
          </div>
        </nav>
        <main className="min-w-0 flex-1 overflow-y-auto p-6">
          <Outlet context={context} />
        </main>
      </div>
    </div>
  )
}
