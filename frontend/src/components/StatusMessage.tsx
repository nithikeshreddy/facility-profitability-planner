import { ApiError } from '../api'

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-slate-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
      {label}
    </div>
  )
}

export function ErrorMessage({ error }: { error: Error }) {
  const status = error instanceof ApiError ? error.status : null
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <p className="font-medium">{status === 404 ? 'Not found' : 'Could not load data'}</p>
      <p className="mt-1">{error.message}</p>
    </div>
  )
}
