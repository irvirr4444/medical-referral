import type { PatientStepStatus, StepFeedDay, StepFeedRow } from '../ops/types'

export type LiveInboxReferral = {
  id: string
  filename: string
  subject: string | null
  sender: string | null
  received_at: string | null
  source: 'testing-infobox'
  status: 'pending_extraction' | 'discovered' | 'processing' | 'needs_attention' | 'completed' | 'failed'
  case_id: string | null
  patient_label: string | null
  steps: Record<string, LiveInboxStep>
}

export type LiveInboxStep = {
  step_id: string
  status: PatientStepStatus
  summary: string
  occurred_at: string
  details: Record<string, unknown>
}

export type LiveInboxPayload = {
  connected: boolean
  source: 'testing-infobox'
  fetched_at?: string
  referrals: LiveInboxReferral[]
  stale?: boolean
  error?: string
  error_code?: string
}

export type LiveInboxState = {
  status: 'loading' | 'syncing' | 'connected' | 'unavailable'
  referrals: LiveInboxReferral[]
  fetchedAt?: string
  error?: string
  monitor?: LiveInboxMonitorState
}

export type LiveInboxMonitorState = {
  available: boolean
  state: 'stopped' | 'starting' | 'monitoring' | 'processing' | 'stopping' | 'error'
  enabled: boolean
  active_cycle: string | null
  started_at: string | null
  stopped_at: string | null
  last_heartbeat_at: string | null
  next_poll_at: string | null
  cycle_count: number
  last_cycle: {
    kind: string
    status: string
    completed_at: string
    elapsed_seconds: number | null
  } | null
  error_type: string | null
  poll_interval_seconds: number
  max_messages: number
  safety: {
    monday_writes: false
    drk_writes: false
    review_email: boolean
    partner_acknowledgement: boolean
    drk_duplicate_check: boolean
  }
}

export type LiveInboxFeedRow = StepFeedRow & {
  source: 'testing-infobox'
  inbox: LiveInboxReferral
  workflowStep?: LiveInboxStep
}

export type IntakeFeedDay = Omit<StepFeedDay, 'rows'> & {
  rows: Array<StepFeedRow | LiveInboxFeedRow>
}
