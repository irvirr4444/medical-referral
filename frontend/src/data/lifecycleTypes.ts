export type LifecycleStageId =
  | 'assignment'
  | 'provider'
  | 'scheduling'
  | 'provider_response'
  | 'end_of_day'
  | 'weekly_visits'
  | 'not_seen'
  | 'holds'
  | 'healed_expired'
  | 'qa_discharge'

export type LifecycleCaseStatus =
  | 'pending'
  | 'suggested'
  | 'awaiting_human'
  | 'completed'
  | 'escalated'
  | 'monitoring'

export interface LifecycleCase {
  id: string
  patientName: string
  stageId: LifecycleStageId
  summary: string
  detail: string
  owner: string
  status: LifecycleCaseStatus
  minutesReturned: number
  actionLabel: string
  resultLabel: string
}

export interface LifecycleStage {
  id: LifecycleStageId
  label: string
  description: string
  beforeCount: number
  afterVerb: string
  runLabel: string
}
