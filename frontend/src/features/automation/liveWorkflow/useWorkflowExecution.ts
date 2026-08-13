import { useCallback, useEffect, useRef, useState } from 'react'
import { confirmAssignment, fetchAssignments, fetchHandoffs } from './api'
import type { WorkflowExecutionState } from './types'

const INITIAL_STATE: WorkflowExecutionState = {
  status: 'loading',
  assignments: [],
  handoffs: [],
  caseManagers: [],
}

export function useWorkflowExecution(enabled: boolean, pollIntervalMs = 10_000) {
  const [state, setState] = useState(INITIAL_STATE)
  const controllerRef = useRef<AbortController | null>(null)

  const refresh = useCallback(async () => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    try {
      const [assignmentResult, handoffs] = await Promise.all([
        fetchAssignments(controller.signal),
        fetchHandoffs(controller.signal),
      ])
      if (controller.signal.aborted) return
      setState({
        status: 'connected',
        assignments: assignmentResult.assignments,
        handoffs,
        caseManagers: assignmentResult.caseManagers,
      })
    } catch (error) {
      if (controller.signal.aborted) return
      setState((current) => ({
        ...current,
        status: 'unavailable',
        error: error instanceof Error ? error.message : 'Workflow API is unavailable.',
      }))
    }
  }, [])

  const confirm = useCallback(async (caseId: string, caseManagerEmail: string) => {
    await confirmAssignment({ caseId, caseManagerEmail })
    await refresh()
  }, [refresh])

  useEffect(() => {
    if (!enabled) return
    void refresh()
    const interval = window.setInterval(() => void refresh(), pollIntervalMs)
    return () => {
      window.clearInterval(interval)
      controllerRef.current?.abort()
    }
  }, [enabled, pollIntervalMs, refresh])

  return { ...state, refresh, confirm }
}
