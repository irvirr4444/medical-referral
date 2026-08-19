import { createContext, useContext, type Dispatch } from 'react'
import type { ActionTimer } from '../../types'
import type { DemoAction } from '../../state/demoReducer'
import type { AttentionState } from './liveWorkflow/attention'

export type AttentionContextValue = {
  timers: Record<string, ActionTimer>
  live: AttentionState
  refresh: () => void
  openSignal: (timer: ActionTimer, dispatch: Dispatch<DemoAction>) => void
}

export const AttentionContext = createContext<AttentionContextValue | null>(null)

export function useAttention(): AttentionContextValue {
  const value = useContext(AttentionContext)
  if (!value) {
    throw new Error('useAttention must be used within AttentionProvider')
  }
  return value
}
