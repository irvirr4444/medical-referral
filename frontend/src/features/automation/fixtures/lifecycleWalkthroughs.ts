import type { FlowOpsPageId } from '../../../data/flowOps'
import type {
  AutomationMicrostep,
  AutomationRunFixture,
  MicrostepExample,
  MicrostepRunStatus,
} from '../types'

interface WalkthroughMoment {
  input: string
  output: string
  duration: string
  status: MicrostepRunStatus
}

interface LifecycleWalkthrough {
  run: AutomationRunFixture
  steps: Record<string, WalkthroughMoment>
}

const SCHEDULING_WALKTHROUGH: LifecycleWalkthrough = {
  run: {
    id: 'maria-scheduling',
    label: 'Maria Alvarez - scheduling walkthrough',
    source: 'Illustrative WCW scheduling scenario',
    startedAt: 'August 10, 2026 at 10:05 AM',
    summary:
      'Shows the planned path from a confirmed provider to a verified appointment.',
    patientName: 'Maria Alvarez',
  },
  steps: {
    'send-referral-provider': {
      input: 'Approved referral and confirmed provider',
      output: 'Referral sent to provider with delivery recorded',
      duration: 'Planned',
      status: 'planned',
    },
    'capture-provider-response': {
      input: 'Referral delivery and one-hour response window',
      output: 'Provider accepted; three open windows within 48 hours',
      duration: 'Planned',
      status: 'planned',
    },
    'confirm-record-appointment': {
      input: 'Open windows, route, and travel buffers',
      output: 'Thu 10:20 AM selected and prepared for Monday and DRK',
      duration: 'Planned',
      status: 'planned',
    },
    'verify-scheduling': {
      input: 'Expected appointment and destination responses',
      output: 'Appointment verified or mismatch sent for review',
      duration: 'Planned',
      status: 'planned',
    },
  },
}

const END_OF_DAY_WALKTHROUGH: LifecycleWalkthrough = {
  run: {
    id: 'evelyn-end-of-day',
    label: 'Evelyn Brooks - end-of-day walkthrough',
    source: 'Illustrative Monday and DRK monitoring snapshots',
    startedAt: 'August 10, 2026 at 5:00 PM',
    summary:
      'Shows how an unscheduled referral is followed up and escalated at day\'s end.',
    patientName: 'Evelyn Brooks',
  },
  steps: {
    'find-unscheduled': {
      input: 'Active referrals due by August 10',
      output: 'Ana assigned; appointment date missing',
      duration: '4.8 seconds',
      status: 'attention',
    },
    'notify-owner': {
      input: 'Evelyn, Ana, and the missing appointment details',
      output: 'Follow-up sent to Ana and the intake lead',
      duration: 'Under 1 second',
      status: 'attention',
    },
    'escalate-unresolved': {
      input: 'Unresolved blocker and Ana follow-up history',
      output: 'Case escalated to Nicole with supporting details',
      duration: 'Under 1 second',
      status: 'attention',
    },
    'verify-resolution': {
      input: 'Unresolved scheduling status',
      output: 'Weekly-cycle entry held until an appointment is confirmed',
      duration: 'Next monitoring cycle',
      status: 'waiting',
    },
  },
}

const WEEKLY_WALKTHROUGH: LifecycleWalkthrough = {
  run: {
    id: 'gloria-weekly',
    label: 'Gloria Bennett - weekly visit walkthrough',
    source: 'Illustrative Monday and DRK visit snapshots',
    startedAt: 'August 10, 2026 at 6:00 PM',
    summary:
      'Shows how a third explicit Not Seen visit creates a human discharge-review request.',
    patientName: 'Gloria Bennett',
  },
  steps: {
    'record-visit-outcome': {
      input: 'Gloria\'s Monday item and DRK patient ID',
      output: 'DRK progress note recorded as Not Seen',
      duration: '4.6 seconds',
      status: 'attention',
    },
    'apply-weekly-rules': {
      input: 'Previous count 2; new explicit Not Seen event',
      output: 'Not Seen count 3; human discharge review required',
      duration: 'Under 1 second',
      status: 'attention',
    },
    'assign-follow-up': {
      input: 'Three Not Seen visits and the review reason',
      output: 'Discharge-review task prepared for management',
      duration: 'Under 1 second',
      status: 'attention',
    },
    'verify-weekly-result': {
      input: 'Prepared review task and approved recipients',
      output: 'WCW systems updated; review sent; no automatic discharge',
      duration: 'Under 1 second',
      status: 'waiting',
    },
  },
}

const WALKTHROUGHS: Partial<Record<FlowOpsPageId, LifecycleWalkthrough>> = {
  scheduling: SCHEDULING_WALKTHROUGH,
  'end-of-day': END_OF_DAY_WALKTHROUGH,
  weekly: WEEKLY_WALKTHROUGH,
}

export function walkthroughRunForStage(
  stageId: FlowOpsPageId,
): AutomationRunFixture | null {
  return WALKTHROUGHS[stageId]?.run ?? null
}

export function walkthroughExampleForStep(
  stageId: FlowOpsPageId,
  step: AutomationMicrostep,
): MicrostepExample | null {
  const moment = WALKTHROUGHS[stageId]?.steps[step.id]
  if (!moment) return null

  return {
    ...step.example,
    status: moment.status,
    duration: moment.duration,
    inputs: [{ label: 'Received', value: moment.input }],
    outputs: [{ label: 'Produced', value: moment.output }],
  }
}
