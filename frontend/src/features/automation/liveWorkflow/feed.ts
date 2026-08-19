import { parseOpsDate } from '../ops'
import type {
  PatientStepStatus,
  StepFeedDay,
  StepFeedRow,
} from '../ops/types'
import {
  isAssignmentGateStep,
  isCombinedAssignmentStage,
  isHandoffOperationStep,
} from '../combinedAssignment'
import type { LiveAssignment, LiveHandoff, HandoffOperation } from './types'

export type LiveWorkflowFeedRow = StepFeedRow & {
  source: 'workflow'
  assignment?: LiveAssignment
  handoff?: LiveHandoff
  operation?: HandoffOperation
}

export function mergeWorkflowFeed({
  demoDays,
  assignments,
  handoffs,
  stageId,
  selectedStepId,
  patientQuery,
  statuses,
}: {
  demoDays: StepFeedDay[]
  assignments: LiveAssignment[]
  handoffs: LiveHandoff[]
  stageId: 'assignment' | 'handoff'
  selectedStepId: string
  patientQuery: string
  statuses: PatientStepStatus[]
}): StepFeedDay[] {
  const rows = isCombinedAssignmentStage(stageId)
    ? isAssignmentGateStep(selectedStepId)
      ? assignmentRows(assignments, selectedStepId)
      : isHandoffOperationStep(selectedStepId)
        ? handoffRows(handoffs, selectedStepId)
        : []
    : []
  const query = patientQuery.trim().toLowerCase()
  const visible = rows.filter((row) =>
    statuses.includes(row.status)
    && (!query || row.patientName.toLowerCase().includes(query)),
  )
  if (!visible.length) return demoDays

  const liveDays = groupRows(visible)
  const merged = new Map(demoDays.map((day) => [day.key, { ...day, rows: [...day.rows] }]))
  for (const day of liveDays) {
    const existing = merged.get(day.key)
    merged.set(day.key, {
      ...day,
      rows: [...day.rows, ...(existing?.rows ?? [])].sort(
        (left, right) =>
          parseOpsDate(right.occurredAt).timeMs - parseOpsDate(left.occurredAt).timeMs,
      ),
    })
  }
  return [...merged.values()].sort((left, right) => right.key.localeCompare(left.key))
}

export function isLiveWorkflowRow(row: StepFeedRow): row is LiveWorkflowFeedRow {
  return 'source' in row && row.source === 'workflow'
}

function assignmentRows(
  assignments: LiveAssignment[],
  stepId: string,
): LiveWorkflowFeedRow[] {
  if (!isAssignmentGateStep(stepId)) return []
  return assignments.map((assignment) => {
    const patientName = assignment.patient_label ?? 'Referral'
    return {
      patientId: assignment.case_id,
      patientName,
      stepId,
      status: assignmentStatus(assignment),
      summary: assignmentSummary(assignment),
      occurredAt: assignment.updated_at,
      source: 'workflow' as const,
      assignment,
    }
  })
}

function handoffRows(
  handoffs: LiveHandoff[],
  stepId: string,
): LiveWorkflowFeedRow[] {
  const operationType = {
    'notify-referral-source': 'notify-assigned-case-manager',
    'create-monday-record': 'create-monday-record',
    'create-update-drk': 'prefill-drk-chart',
  }[stepId]
  if (!operationType) return []
  return handoffs.flatMap((handoff) => {
    const operation = handoff.operations.find(
      (item) => item.operation_type === operationType,
    )
    if (!operation) return []
    return [{
      patientId: handoff.case_id,
      patientName: handoff.patient_label ?? 'Referral',
      stepId,
      status: operationStatus(operation.status),
      summary: operationSummary(operationType, operation.status),
      occurredAt: operation.updated_at,
      source: 'workflow' as const,
      handoff,
      operation,
    }]
  })
}

function assignmentStatus(assignment: LiveAssignment): PatientStepStatus {
  if (assignment.status === 'completed') return 'done'
  if (assignment.status === 'blocked' || assignment.status === 'failed') return 'blocked'
  return 'waiting'
}

function assignmentSummary(assignment: LiveAssignment) {
  if (assignment.status === 'completed') {
    return `${assignment.assigned_case_manager?.name ?? 'Case manager'} confirmed as Case Manager`
  }
  if (assignment.owner_role === 'intake_team') return 'Intake team follow-up required'
  return 'Case Manager needs to be confirmed'
}

function operationStatus(status: HandoffOperation['status']): PatientStepStatus {
  if (status === 'succeeded') return 'done'
  if (status === 'running') return 'current'
  if (status === 'blocked' || status === 'failed') return 'blocked'
  return 'waiting'
}

function operationSummary(type: string, status: HandoffOperation['status']) {
  const labels: Record<string, string> = {
    'notify-assigned-case-manager': 'Notify assigned case manager',
    'create-monday-record': 'Monday.com record ready to create',
    'prefill-drk-chart': 'DRK chart ready to prefill',
  }
  const label = labels[type] ?? 'Handoff action'
  if (status === 'succeeded') return `${label} completed`
  if (status === 'failed' || status === 'blocked') return `${label} needs attention`
  return label
}

function groupRows(rows: LiveWorkflowFeedRow[]): StepFeedDay[] {
  const grouped = new Map<string, LiveWorkflowFeedRow[]>()
  for (const row of rows) {
    const parsed = parseOpsDate(row.occurredAt)
    grouped.set(parsed.key, [...(grouped.get(parsed.key) ?? []), row])
  }
  return [...grouped.entries()].map(([key, dayRows]) => {
    dayRows.sort(
      (left, right) =>
        parseOpsDate(right.occurredAt).timeMs - parseOpsDate(left.occurredAt).timeMs,
    )
    const parsed = parseOpsDate(dayRows[0].occurredAt)
    return {
      key,
      label: parsed.label,
      month: parsed.month,
      day: parsed.day,
      rows: dayRows,
    }
  })
}
