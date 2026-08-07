import type { FlowOpsPageId } from '../../data/flowOps'

export type ImplementationStatus = 'working' | 'partial' | 'planned'
export type MicrostepRunStatus =
  | 'completed'
  | 'attention'
  | 'waiting'
  | 'planned'

export interface AutomationValue {
  label: string
  value: string
}

export interface MicrostepExample {
  status: MicrostepRunStatus
  duration: string
  inputs: AutomationValue[]
  outputs: AutomationValue[]
  validation: string
}

export interface AutomationMicrostep {
  id: string
  name: string
  description: string
  implementationStatus: ImplementationStatus
  system: string
  next: string
  example: MicrostepExample
  exceptionExample?: MicrostepExample
}

export interface AutomationStageDefinition {
  id: FlowOpsPageId
  title: string
  shortTitle: string
  purpose: string
  trigger: string
  successDefinition: string
  implementationStatus: ImplementationStatus
  microsteps: AutomationMicrostep[]
}

export interface AutomationRunFixture {
  id: 'synthetic-complete' | 'synthetic-exception'
  label: string
  source: string
  startedAt: string
  summary: string
}

export interface MicrostepFeedback {
  id: string
  runId: string
  stepId: string
  category:
    | 'incorrect-output'
    | 'missing-context'
    | 'workflow-change'
    | 'question'
  comment: string
  createdAt: string
}
