import type { FlowOpsPageId } from './flowOps'

export type ScenarioBucket = 'ready' | 'attention' | 'blocked' | 'approval'

export type ScenarioCaseStatus =
  | 'open'
  | 'in_progress'
  | 'waiting_human'
  | 'completed'
  | 'escalated'
  | 'monitoring'

export type ScenarioActionVerb =
  | 'Review'
  | 'Assign'
  | 'Confirm'
  | 'Escalate'
  | 'Approve'
  | 'Resolve'
  | 'Prepare'
  | 'Verify'
  | 'Record'

export interface ScenarioCase {
  id: string
  patientName: string
  summary: string
  detail: string
  owner: string
  facilityOrContext: string
  status: ScenarioCaseStatus
  minutesReturned: number
  deadlineLabel?: string
  actionLabel: string
  resultLabel: string
  humanOnly: boolean
}

export interface WorkflowScenario {
  id: string
  tab: FlowOpsPageId
  title: string
  branchLabel: string
  bucket: ScenarioBucket
  description: string
  rule: string
  humanControlNote: string
  actionVerb: ScenarioActionVerb
  cases: ScenarioCase[]
}

export interface ScenarioFilterState {
  bucket: 'all' | ScenarioBucket
}

export function scenarioCaseIsOpen(status: ScenarioCaseStatus): boolean {
  return status !== 'completed' && status !== 'escalated'
}
