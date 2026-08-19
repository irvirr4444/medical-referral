import { createContext, useContext } from 'react'
import type { LiveInboxState } from './types'

export type LiveInboxContextValue = LiveInboxState & {
  refresh: () => void
}

export const LiveInboxContext = createContext<LiveInboxContextValue | null>(null)

export function useLiveInboxContext(): LiveInboxContextValue {
  const value = useContext(LiveInboxContext)
  if (!value) {
    throw new Error('useLiveInboxContext must be used within LiveInboxProvider')
  }
  return value
}
