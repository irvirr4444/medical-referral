import type { FlowOpsPageId } from '../../data/flowOps'
import type { DemoState } from '../../types'
import {
  COMBINED_ASSIGNMENT_STEP_IDS,
  canonicalOpsPageId,
  isCombinedAssignmentStage,
} from './combinedAssignment'
import { STAGE_STEP_IDS } from './ops/fixtures/patientSteps'

type UnreadFlag = keyof Pick<
  DemoState,
  | 'intakeMondayUnread'
  | 'intakeDrkUnread'
  | 'intakePartnerUnread'
  | 'assignmentOwnerUnread'
  | 'assignmentNotifyUnread'
  | 'handoffNotifyUnread'
  | 'handoffMondayUnread'
  | 'handoffDrkUnread'
  | 'providerSelectUnread'
  | 'providerAvailabilityUnread'
  | 'providerRecordsUnread'
  | 'schedulingHandoffUnread'
  | 'eodFollowUpUnread'
  | 'eodEscalationUnread'
>

/** Which demo flag marks each microstep as having an unread update. */
const UNREAD_STEP_FLAGS: Record<string, UnreadFlag> = {
  'check-monday': 'intakeMondayUnread',
  'check-drk': 'intakeDrkUnread',
  'confirm-referral-contacted': 'intakePartnerUnread',
  'assign-owner': 'assignmentOwnerUnread',
  'notify-referral-source': 'handoffNotifyUnread',
  'create-monday-record': 'handoffMondayUnread',
  'create-update-drk': 'handoffDrkUnread',
  'select-provider': 'providerSelectUnread',
  'confirm-provider-availability': 'providerAvailabilityUnread',
  'update-monday-drk': 'providerRecordsUnread',
  'send-referral-provider': 'schedulingHandoffUnread',
  'follow-up-case-manager': 'eodFollowUpUnread',
  'escalate-unresolved-cases': 'eodEscalationUnread',
}

export function unreadStepCounts(state: DemoState): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const [stepId, flag] of Object.entries(UNREAD_STEP_FLAGS)) {
    if (state[flag]) counts[stepId] = 1
  }
  return counts
}

export function unreadCountForStage(state: DemoState, stageId: string): number {
  const canonicalId = canonicalOpsPageId(stageId)
  const stepIds = isCombinedAssignmentStage(canonicalId)
    ? COMBINED_ASSIGNMENT_STEP_IDS
    : STAGE_STEP_IDS[canonicalId as FlowOpsPageId] ?? []
  return stepIds.reduce((total, stepId) => {
    const flag = UNREAD_STEP_FLAGS[stepId]
    return total + (flag && state[flag] ? 1 : 0)
  }, 0)
}
