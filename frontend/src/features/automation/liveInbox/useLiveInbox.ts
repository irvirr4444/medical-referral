import { useCallback, useEffect, useRef, useState } from 'react'
import {
  fetchLiveInbox,
  fetchLiveInboxMonitor,
} from './api'
import type { LiveInboxState } from './types'

const INITIAL_STATE: LiveInboxState = {
  status: 'loading',
  referrals: [],
}

export function useLiveInbox(enabled: boolean, pollIntervalMs = 10_000) {
  const [state, setState] = useState<LiveInboxState>(INITIAL_STATE)
  const controllerRef = useRef<AbortController | null>(null)

  const refresh = useCallback(async (force = false) => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    const [inboxResult, monitorResult] = await Promise.allSettled([
      fetchLiveInbox({ signal: controller.signal, force }),
      fetchLiveInboxMonitor({ signal: controller.signal }),
    ])
    if (controller.signal.aborted) return
    if (inboxResult.status === 'fulfilled') {
      const payload = inboxResult.value
      setState({
        status: 'connected',
        referrals: payload.referrals,
        fetchedAt: payload.fetched_at,
        monitor: monitorResult.status === 'fulfilled' ? monitorResult.value : undefined,
      })
    } else {
      const error = inboxResult.reason
      setState((current) => ({
        ...current,
        status: 'unavailable',
        error: error instanceof Error ? error.message : 'Testing infobox is unavailable.',
        monitor: monitorResult.status === 'fulfilled' ? monitorResult.value : current.monitor,
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

  return { ...state, refresh: () => refresh(true) }
}
