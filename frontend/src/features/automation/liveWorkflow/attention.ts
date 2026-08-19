import type { AttentionSeverity } from '../../../types'

export type { AttentionSeverity }
export type AttentionSource = 'workflow_case' | 'work_item' | 'exception'

export type AttentionSignal = {
  signal_id: string
  case_id: string
  patient_label: string
  stage: number
  step_id: string
  severity: AttentionSeverity
  status: string
  due_at: string | null
  overdue_seconds: number
  action_label: string
  source: AttentionSource
}

export type AttentionSummary = {
  overdue: number
  due_soon: number
  blocked: number
  by_stage: Record<string, { overdue: number; due_soon: number; blocked: number }>
}

export type AttentionPayload = {
  generated_at: string
  summary: AttentionSummary
  items: AttentionSignal[]
}

export type AttentionState = {
  status: 'loading' | 'connected' | 'unavailable'
  payload: AttentionPayload | null
  error?: string
}
