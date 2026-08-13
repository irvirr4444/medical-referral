import type { FlowOpsPageId } from '../../../data/flowOps'
import type { PatientStepProgress, PatientStepStatus } from './types'

const ACTION_GROUPS: Partial<
  Record<FlowOpsPageId, Record<string, string[]>>
> = {
  handoff: {
    'notify-referral-source': ['load-approved-plan', 'map-monday-fields'],
    'create-monday-record': ['write-monday'],
    'create-update-drk': ['prepare-drk', 'apply-drk'],
    'verify-handoff': ['link-destinations', 'reconcile-handoff'],
  },
  assignment: {
    'determine-owner': [
      'determine-owner',
      'assign-owner',
      'load-assignment-context',
      'normalize-location',
      'load-territories',
      'match-owner',
      'classify-assignment',
      'confirm-assignment',
      'write-assignment',
    ],
  },
  provider: {
    'find-eligible-providers': [
      'load-provider-context',
      'load-provider-roster',
      'filter-providers',
    ],
    'select-provider': ['rank-providers', 'classify-provider-result'],
    'record-provider': ['confirm-provider', 'write-provider'],
  },
  scheduling: {
    'send-referral-provider': ['load-scheduling-context', 'read-availability'],
    'capture-provider-response': ['generate-windows', 'present-windows'],
    'confirm-record-appointment': [
      'monitor-response',
      'classify-response',
      'write-appointment',
    ],
    'verify-scheduling': ['reconcile-appointment'],
  },
  'end-of-day': {
    'find-unscheduled': ['start-eod-cycle', 'load-due-referrals', 'read-eod-sources'],
    'notify-owner': ['normalize-scheduling'],
    'escalate-unresolved': ['dedupe-eod-alerts', 'create-eod-exceptions'],
    'verify-resolution': ['notify-eod', 'resolve-eod'],
  },
  weekly: {
    'record-visit-outcome': [
      'start-weekly-cycle',
      'read-visit-status',
      'normalize-visit-status',
    ],
    'apply-weekly-rules': [
      'detect-visit-change',
      'update-not-seen-counter',
      'classify-weekly-review',
    ],
    'assign-follow-up': ['create-weekly-exception'],
    'verify-weekly-result': ['notify-and-reconcile'],
  },
}

const RECOMMENDATION_ACTIONS = new Set(['determine-owner', 'select-provider'])
const CONFIRMATION_ACTIONS = new Set([
  'assign-owner',
  'record-provider',
  'confirm-record-appointment',
])

/** Collapse legacy fixture events into the business actions shown in the console. */
export function actionProgressForStage(
  stageId: FlowOpsPageId,
  rows: PatientStepProgress[],
  visibleStepIds: string[],
): PatientStepProgress[] {
  const groups = ACTION_GROUPS[stageId]
  if (!groups || rows.every((row) => visibleStepIds.includes(row.stepId))) {
    return rows
  }

  const collapsed: PatientStepProgress[] = visibleStepIds.map((stepId) => {
    const members = (groups[stepId] ?? [stepId])
      .map((legacyId) => rows.find((row) => row.stepId === legacyId))
      .filter((row): row is PatientStepProgress => Boolean(row))

    if (members.length === 0) {
      return { stepId, status: 'upcoming', summary: 'Not started' }
    }

    const status = groupStatus(stepId, members)
    const representative = representativeRow(members, status)
    return {
      ...representative,
      stepId,
      status,
      summary:
        status === 'upcoming' ? 'Not started' : representative.summary,
    }
  })

  return collapsed.map((row, index): PatientStepProgress => {
    if (
      row.status === 'upcoming' &&
      CONFIRMATION_ACTIONS.has(row.stepId) &&
      collapsed[index - 1]?.status === 'done'
    ) {
      return {
        ...row,
        status: 'waiting' as const,
        summary: 'Ready for confirmation',
      }
    }
    return row
  })
}

function groupStatus(
  stepId: string,
  rows: PatientStepProgress[],
): PatientStepStatus {
  if (rows.some((row) => row.status === 'blocked')) return 'blocked'
  if (rows.some((row) => row.status === 'waiting')) {
    return RECOMMENDATION_ACTIONS.has(stepId) ? 'done' : 'waiting'
  }
  if (rows.some((row) => row.status === 'current')) return 'current'
  if (rows.every((row) => row.status === 'done')) return 'done'
  if (rows.every((row) => row.status === 'upcoming')) return 'upcoming'
  return 'current'
}

function representativeRow(
  rows: PatientStepProgress[],
  status: PatientStepStatus,
): PatientStepProgress {
  return (
    rows.find((row) => row.status === status) ??
    [...rows].reverse().find((row) => row.status === 'done') ??
    rows[0]
  )
}
