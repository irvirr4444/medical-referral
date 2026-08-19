import type { ReactNode } from 'react'
import { LiveWorkflowContext } from './LiveWorkflowContext'
import { useWorkflowExecution } from './useWorkflowExecution'

/**
 * Mounted once at the app root so assignments/handoffs survive stage
 * navigation instead of resetting to a loading state on every remount.
 */
export function LiveWorkflowProvider({ children }: { children: ReactNode }) {
  const liveWorkflow = useWorkflowExecution(true)
  return (
    <LiveWorkflowContext.Provider value={liveWorkflow}>
      {children}
    </LiveWorkflowContext.Provider>
  )
}
