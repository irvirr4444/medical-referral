import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchWorkflowAttention } from './attentionApi'
import type { AttentionState } from './attention'

const EMPTY: AttentionState = {
  status: 'loading',
  payload: null,
}

export function useWorkflowAttention(enabled = true, pollIntervalMs = 10_000) {
  const [state, setState] = useState<AttentionState>(EMPTY)
  const controllerRef = useRef<AbortController | null>(null)

  const refresh = useCallback(async () => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    try {
      const payload = await fetchWorkflowAttention(controller.signal)
      if (controller.signal.aborted) return
      setState({ status: 'connected', payload })
    } catch (error) {
      if (controller.signal.aborted) return
      setState((current) => ({
        ...current,
        status: 'unavailable',
        error: error instanceof Error ? error.message : 'Workflow attention is unavailable.',
      }))
    }
  }, [])

  useEffect(() => {
    if (!enabled) return
    void refresh()
    const interval = window.setInterval(() => void refresh(), pollIntervalMs)
    return () => {
      window.clearInterval(interval)
      controllerRef.current?.abort()
    }
  }, [enabled, pollIntervalMs, refresh])

  return { ...state, refresh }
}
