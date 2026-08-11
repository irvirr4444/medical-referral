import type { FlowOpsPageId } from '../../../data/flowOps'
import type {
  HumanDecisionRecord,
  PatientStepProgress,
} from './types'

export interface HumanGateDefinition {
  actionLabel: string
  blockedActionLabel?: string
  confirmedLabel: string
  decisionSummary: string
  options?: Array<{
    value: string
    label: string
    detail?: string
    recommended?: boolean
  }>
}

const HUMAN_GATES: Partial<
  Record<FlowOpsPageId, Record<string, HumanGateDefinition>>
> = {
  intake: {
    'confirm-referral-contacted': {
      actionLabel: 'Record partner contacted',
      confirmedLabel: 'Partner contact recorded',
      decisionSummary: 'Referral partner contact was confirmed by a WCW reviewer.',
    },
    'confirm-information-complete': {
      actionLabel: 'Approve referral',
      blockedActionLabel: 'Resolve gaps and approve',
      confirmedLabel: 'Referral approved',
      decisionSummary: 'Referral completeness was approved for handoff.',
    },
  },
  assignment: {
    'assign-owner': {
      actionLabel: 'Assign owner',
      blockedActionLabel: 'Confirm routing owner',
      confirmedLabel: 'Owner decision recorded',
      decisionSummary: 'The case-manager or marketer routing decision was recorded.',
      options: [
        { value: 'Cole Ramirez', label: 'Cole Ramirez', detail: 'South Bay territory', recommended: true },
        { value: 'Carla Mendoza', label: 'Carla Mendoza', detail: 'Coastal backup' },
        { value: 'Linda Nguyen', label: 'Linda Nguyen', detail: 'Marketer follow-up' },
      ],
    },
  },
  provider: {
    'record-provider': {
      actionLabel: 'Record provider',
      confirmedLabel: 'Provider confirmed',
      decisionSummary: 'The case manager confirmed the selected provider.',
      options: [
        { value: 'Dr. Sofia Lee', label: 'Dr. Sofia Lee', detail: '4.2 mi - capacity available', recommended: true },
        { value: 'Dr. Mina Patel', label: 'Dr. Mina Patel', detail: '6.8 mi - capacity available' },
        { value: 'Dr. James Nguyen', label: 'Dr. James Nguyen', detail: '9.1 mi - limited capacity' },
      ],
    },
  },
  scheduling: {
    'confirm-record-appointment': {
      actionLabel: 'Record appointment',
      blockedActionLabel: 'Record blocker and continue',
      confirmedLabel: 'Appointment decision recorded',
      decisionSummary: 'The appointment selection or scheduling blocker was confirmed.',
      options: [
        { value: '08/11/2026 10:00 AM', label: 'Aug 11 at 10:00 AM', detail: 'Recommended', recommended: true },
        { value: '08/12/2026 1:30 PM', label: 'Aug 12 at 1:30 PM', detail: 'Alternate slot' },
      ],
    },
  },
  'end-of-day': {
    'escalate-unresolved': {
      actionLabel: 'Send escalation',
      confirmedLabel: 'Escalation sent',
      decisionSummary: 'The unresolved scheduling case was escalated.',
    },
  },
  weekly: {
    'assign-follow-up': {
      actionLabel: 'Confirm review route',
      confirmedLabel: 'Review route confirmed',
      decisionSummary: 'The weekly visit exception was routed for human review.',
    },
    'verify-weekly-result': {
      actionLabel: 'Record follow-up complete',
      confirmedLabel: 'Follow-up recorded',
      decisionSummary: 'The responsible team follow-up was confirmed and recorded.',
    },
  },
}

export function humanGateForStep(
  stageId: FlowOpsPageId,
  stepId: string,
): HumanGateDefinition | undefined {
  return HUMAN_GATES[stageId]?.[stepId]
}

export function applyHumanDecisions<T extends PatientStepProgress>(
  rows: T[],
  decisions: HumanDecisionRecord[],
): T[] {
  if (decisions.length === 0) return rows

  const confirmedSteps = new Set(decisions.map((decision) => decision.stepId))
  const next = rows.map((row) =>
    confirmedSteps.has(row.stepId)
      ? {
          ...row,
          status: 'done' as const,
          summary: `${row.summary} - human decision recorded`,
        } as T
      : row,
  )

  for (const decision of decisions) {
    const index = next.findIndex((row) => row.stepId === decision.stepId)
    const following = next[index + 1]
    if (following?.status === 'upcoming') {
      next[index + 1] = {
        ...following,
        status: 'current',
        summary: 'Ready after the recorded human decision',
      } as T
    }
  }

  return next
}
