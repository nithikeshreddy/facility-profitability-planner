import { NavLink, Outlet } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Overview' },
  { to: '/locations', label: 'Location details' },
  { to: '/compare', label: 'Compare plans' },
  { to: '/renewals', label: 'Renewal review' },
  { to: '/incentives', label: 'Vendor incentives' },
]

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <div className="bg-amber-100 px-4 py-1.5 text-center text-sm font-medium text-amber-900">
        Demonstration data — all locations, vendors, and figures are synthetic.
      </div>
      <div className="flex flex-1">
        <nav className="flex w-56 shrink-0 flex-col border-r border-slate-200 bg-white">
          <div className="px-4 py-4 text-base font-semibold">Facility Profitability Planner</div>
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
            {/* Not wired yet: will call the backend reset endpoint. */}
            <button
              type="button"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
            >
              Reset demo
            </button>
          </div>
        </nav>
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
