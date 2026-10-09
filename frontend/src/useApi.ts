import { type DependencyList, useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'

export interface ApiState<T> {
  data: T | null
  error: Error | null
  loading: boolean
}

export interface LayoutContext {
  /** Bumped by "Reset demo" so every page re-fetches. */
  dataVersion: number
}

/** Runs `fn` whenever `deps` or the demo data version change; stale responses are aborted.
 *  With `keepDataOnError`, a failed request keeps the last good `data` alongside the error. */
export function useApi<T>(
  fn: (signal: AbortSignal) => Promise<T>,
  deps: DependencyList,
  { keepDataOnError = false }: { keepDataOnError?: boolean } = {},
): ApiState<T> {
  const { dataVersion } = useOutletContext<LayoutContext>()
  const [state, setState] = useState<ApiState<T>>({ data: null, error: null, loading: true })

  useEffect(() => {
    const controller = new AbortController()
    setState((s) => ({ ...s, error: null, loading: true }))
    fn(controller.signal).then(
      (data) => setState({ data, error: null, loading: false }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        setState((s) => ({
          data: keepDataOnError ? s.data : null,
          error: error instanceof Error ? error : new Error(String(error)),
          loading: false,
        }))
      },
    )
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, dataVersion])

  return state
}
