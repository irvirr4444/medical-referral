import { useMemo, type ReactNode } from 'react'
import { isDemoDataMode } from './demoDataMode'
import { AttentionContext } from './AttentionContext'
import {
  applyAttentionNavigation,
  selectAttentionTimers,
} from './liveWorkflow/attentionDisplay'
import { useWorkflowAttention } from './liveWorkflow/useWorkflowAttention'
import { useDemo } from '../../state/useDemo'

export function AttentionProvider({ children }: { children: ReactNode }) {
  const { state } = useDemo()
  const live = useWorkflowAttention(true)
  const timers = useMemo(
    () =>
      selectAttentionTimers({
        liveStatus: live.status,
        liveItems: live.payload?.items ?? [],
        demoMode: isDemoDataMode(),
        demoTimers: state.actionTimers,
      }),
    [live.status, live.payload, state.actionTimers],
  )

  const value = useMemo(
    () => ({
      timers,
      live: { status: live.status, payload: live.payload, error: live.error },
      refresh: live.refresh,
      openSignal: applyAttentionNavigation,
    }),
    [timers, live.status, live.payload, live.error, live.refresh],
  )

  return <AttentionContext.Provider value={value}>{children}</AttentionContext.Provider>
}
