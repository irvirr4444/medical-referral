import { createContext, useContext } from 'react'
import type { WorkflowExecutionState } from './types'

export type LiveWorkflowContextValue = WorkflowExecutionState & {
  refresh: () => void
  confirm: (caseId: string, caseManagerEmail: string) => Promise<void>
}

export const LiveWorkflowContext = createContext<LiveWorkflowContextValue | null>(null)

export function useLiveWorkflowContext(): LiveWorkflowContextValue {
  const value = useContext(LiveWorkflowContext)
  if (!value) {
    throw new Error('useLiveWorkflowContext must be used within LiveWorkflowProvider')
  }
  return value
}
