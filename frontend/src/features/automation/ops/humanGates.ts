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
  handoff: {
    'resolve-agency': {
      actionLabel: 'Confirm routing',
      blockedActionLabel: 'Choose agency and continue',
      confirmedLabel: 'Routing confirmed',
      decisionSummary: 'The referral routing and agency relationship were confirmed.',
    },
    'prepare-drk': {
      actionLabel: 'Approve DRK entry',
      confirmedLabel: 'DRK entry approved',
      decisionSummary: 'The prepared DRK patient record was approved for entry.',
    },
  },
  assignment: {
    'classify-assignment': {
      actionLabel: 'Confirm recommended owner',
      blockedActionLabel: 'Confirm routing owner',
      confirmedLabel: 'Owner decision recorded',
      decisionSummary: 'The case-manager or marketer routing decision was recorded.',
    },
    'confirm-assignment': {
      actionLabel: 'Confirm assignment',
      confirmedLabel: 'Assignment confirmed',
      decisionSummary: 'The selected WCW owner was confirmed.',
    },
  },
  provider: {
    'classify-provider-result': {
      actionLabel: 'Confirm provider path',
      blockedActionLabel: 'Send coverage gap to Nicole',
      confirmedLabel: 'Provider path recorded',
      decisionSummary: 'The provider recommendation or coverage escalation was recorded.',
    },
    'confirm-provider': {
      actionLabel: 'Confirm provider',
      confirmedLabel: 'Provider confirmed',
      decisionSummary: 'The case manager confirmed the selected provider.',
    },
  },
  scheduling: {
    'classify-response': {
      actionLabel: 'Confirm appointment',
      blockedActionLabel: 'Record blocker and continue',
      confirmedLabel: 'Appointment decision recorded',
      decisionSummary: 'The appointment selection or scheduling blocker was confirmed.',
    },
  },
  'end-of-day': {
    'create-eod-exceptions': {
      actionLabel: 'Send escalation',
      confirmedLabel: 'Escalation sent',
      decisionSummary: 'The unresolved scheduling case was escalated.',
    },
    'resolve-eod': {
      actionLabel: 'Confirm weekly-cycle handoff',
      confirmedLabel: 'Weekly-cycle handoff confirmed',
      decisionSummary: 'The patient was confirmed ready for weekly visit tracking.',
    },
  },
  weekly: {
    'classify-weekly-review': {
      actionLabel: 'Confirm review route',
      confirmedLabel: 'Review route confirmed',
      decisionSummary: 'The weekly visit exception was routed for human review.',
    },
    'notify-and-reconcile': {
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
