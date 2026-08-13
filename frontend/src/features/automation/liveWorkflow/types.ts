export type CaseManagerChoice = {
  name: string
  email: string
}

export type LiveAssignment = {
  work_item_id: string
  case_id: string
  patient_label: string | null
  status: 'waiting' | 'ready' | 'completed' | 'blocked' | 'failed'
  owner_role: 'case_manager' | 'intake_team' | 'system'
  recommended_assignee: string | null
  recommendation_reason: string | null
  assigned_to: string | null
  assigned_case_manager: CaseManagerChoice | null
  payload: Record<string, unknown>
  updated_at: string
}

export type HandoffOperation = {
  operation_id: string
  operation_type: string
  status: 'ready' | 'running' | 'succeeded' | 'blocked' | 'failed'
  updated_at: string
  request_payload: Record<string, unknown>
}

export type LiveHandoff = {
  case_id: string
  patient_label: string | null
  status: string
  assigned_case_manager: CaseManagerChoice | null
  operations: HandoffOperation[]
}

export type WorkflowExecutionState = {
  status: 'loading' | 'connected' | 'unavailable'
  assignments: LiveAssignment[]
  handoffs: LiveHandoff[]
  caseManagers: CaseManagerChoice[]
  error?: string
}
