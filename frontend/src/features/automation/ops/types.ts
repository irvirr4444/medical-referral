import type { FlowOpsPageId } from '../../../data/flowOps'

export type OpsEventStatus = 'open' | 'resolved'

export interface OpsRecipeSection {
  id: string
  label: string
  /** Prefer expanding this section in Now when it has open items. */
  openByDefault: boolean
  /** True when this section represents blockers / exceptions. */
  isException?: boolean
}

export interface StageOpsRecipe {
  stageId: FlowOpsPageId
  sections: OpsRecipeSection[]
}

export interface OpsEvent {
  id: string
  stageId: FlowOpsPageId
  eventType: string
  patientId: string
  patientName: string
  occurredAt: string
  summary: string
  status: OpsEventStatus
  ageLabel?: string
}

export interface StageOpsFixture {
  stageId: FlowOpsPageId
  events: OpsEvent[]
}

export interface PatientStageOutcome {
  stageId: FlowOpsPageId
  status: 'done' | 'current' | 'blocked' | 'upcoming'
  headline: string
  outcomes: Array<{ occurredAt: string; summary: string }>
}

export interface PatientOpsJourney {
  patientId: string
  patientName: string
  context: string
  currentStageId: FlowOpsPageId
  stages: PatientStageOutcome[]
}

export type PatientStepStatus =
  | 'done'
  | 'current'
  | 'waiting'
  | 'blocked'
  | 'upcoming'

export interface PatientStepDetailFacts {
  artifactTitle?: string
  validation?: string
  duration?: string
  knownAtThisPoint?: Array<{ label: string; value: string }>
  fields?: Array<{ label: string; value: string; meta?: string }>
}

export interface PatientStepProgress {
  stepId: string
  status: PatientStepStatus
  summary: string
  occurredAt?: string
  /** Optional richer demo facts for Steps detail. */
  detail?: PatientStepDetailFacts
}

export interface StagePatientRef {
  patientId: string
  patientName: string
}

export interface ActivityFeedMessage {
  id: string
  patientId: string
  patientName: string
  occurredAt: string
  summary: string
  eventType: string
  status: OpsEventStatus
}

