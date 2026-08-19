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
  const inboxControllerRef = useRef<AbortController | null>(null)
  const monitorControllerRef = useRef<AbortController | null>(null)
  const inboxInFlightRef = useRef(false)
  const pendingForceRef = useRef(false)
  const enabledRef = useRef(enabled)
  const mountedRef = useRef(true)
  enabledRef.current = enabled

  const refreshMonitor = useCallback(async () => {
    if (!enabledRef.current) return
    monitorControllerRef.current?.abort()
    const controller = new AbortController()
    monitorControllerRef.current = controller
    try {
      const monitor = await fetchLiveInboxMonitor({ signal: controller.signal })
      if (controller.signal.aborted || !enabledRef.current || !mountedRef.current) return
      setState((current) => ({
        ...current,
        monitor,
        status:
          current.status === 'loading' || current.status === 'syncing'
            ? 'syncing'
            : current.status,
      }))
    } catch {
      if (controller.signal.aborted || !enabledRef.current || !mountedRef.current) return
    }
  }, [])

  const refreshInbox = useCallback(async (force = false) => {
    if (!enabledRef.current) return
    if (inboxInFlightRef.current) {
      if (force) pendingForceRef.current = true
      return
    }
    inboxInFlightRef.current = true
    const controller = new AbortController()
    inboxControllerRef.current = controller
    try {
      const payload = await fetchLiveInbox({ signal: controller.signal, force })
      if (controller.signal.aborted || !enabledRef.current || !mountedRef.current) return
      setState((current) => ({
        ...current,
        status: 'connected',
        referrals: payload.referrals,
        fetchedAt: payload.fetched_at,
        error: undefined,
      }))
    } catch (error) {
      if (controller.signal.aborted || !enabledRef.current || !mountedRef.current) return
      const message =
        error instanceof Error ? error.message : 'Testing infobox is unavailable.'
      setState((current) => {
        if (current.status === 'connected') {
          return { ...current, error: message }
        }
        return {
          ...current,
          status: 'unavailable',
          error: message,
        }
      })
    } finally {
      if (inboxControllerRef.current === controller) {
        inboxControllerRef.current = null
        inboxInFlightRef.current = false
        if (mountedRef.current && enabledRef.current && pendingForceRef.current) {
          pendingForceRef.current = false
          void refreshInbox(true)
        }
      }
    }
  }, [])

  useEffect(() => {
    if (!enabled) {
      inboxControllerRef.current?.abort()
      inboxControllerRef.current = null
      monitorControllerRef.current?.abort()
      inboxInFlightRef.current = false
      pendingForceRef.current = false
      return
    }
    void refreshInbox()
    void refreshMonitor()
    const interval = window.setInterval(() => {
      void refreshInbox()
      void refreshMonitor()
    }, pollIntervalMs)
    return () => {
      window.clearInterval(interval)
      pendingForceRef.current = false
      inboxControllerRef.current?.abort()
      inboxControllerRef.current = null
      monitorControllerRef.current?.abort()
      inboxInFlightRef.current = false
    }
  }, [enabled, pollIntervalMs, refreshInbox, refreshMonitor])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  return { ...state, refresh: () => void refreshInbox(true) }
}
