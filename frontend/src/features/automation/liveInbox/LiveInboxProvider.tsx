import type { ReactNode } from 'react'
import { LiveInboxContext } from './LiveInboxContext'
import { useLiveInbox } from './useLiveInbox'

/**
 * Mounted once at the app root so the fetched inbox feed survives stage
 * navigation instead of resetting to a loading state on every remount.
 */
export function LiveInboxProvider({ children }: { children: ReactNode }) {
  const liveInbox = useLiveInbox(true)
  return (
    <LiveInboxContext.Provider value={liveInbox}>
      {children}
    </LiveInboxContext.Provider>
  )
}
