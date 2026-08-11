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
    'load-scheduling-context': {
      input: 'Maria Alvarez; provider confirmed; Riverside address',
      output: 'Patient, provider, location, and contact details ready',
      duration: 'Planned',
      status: 'planned',
    },
    'read-availability': {
      input: 'Approved referral and confirmed provider',
      output: 'Referral sent to provider with delivery recorded',
      duration: 'Planned',
      status: 'planned',
    },
    'generate-windows': {
      input: 'Referral delivery and one-hour response window',
      output: 'Provider confirmed availability after 18 minutes',
      duration: 'Planned',
      status: 'planned',
    },
    'present-windows': {
      input: 'Confirmed provider and Riverside service area',
      output: 'Three open provider windows within 48 hours',
      duration: 'Planned',
      status: 'planned',
    },
    'monitor-response': {
      input: 'Open windows, route, and travel buffers',
      output: 'Thu 10:20 AM; Thu 2:45 PM; Fri 9:15 AM',
      duration: 'Planned',
      status: 'planned',
    },
    'classify-response': {
      input: 'Three route-compatible appointment options',
      output: 'WCW employee confirmed Thu 10:20 AM',
      duration: 'Planned',
      status: 'planned',
    },
    'write-appointment': {
      input: 'Human-confirmed date, time, patient, and provider',
      output: 'Target Monday and DRK appointment updates',
      duration: 'Planned',
      status: 'planned',
    },
    'reconcile-appointment': {
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
    'start-eod-cycle': {
      input: '5:00 PM cutoff; Monday and DRK readers healthy',
      output: 'August 10 end-of-day cycle started',
      duration: '0.1 seconds',
      status: 'completed',
    },
    'load-due-referrals': {
      input: 'Active referrals due by August 10',
      output: 'Evelyn Brooks included for scheduling review',
      duration: '0.2 seconds',
      status: 'completed',
    },
    'read-eod-sources': {
      input: 'Evelyn\'s Monday item and DRK patient ID',
      output: 'Ana assigned; appointment date missing',
      duration: '4.8 seconds',
      status: 'attention',
    },
    'normalize-scheduling': {
      input: 'Evelyn, Ana, and the missing appointment details',
      output: 'Follow-up sent to Ana and the intake lead',
      duration: 'Under 1 second',
      status: 'attention',
    },
    'dedupe-eod-alerts': {
      input: 'Open follow-up and current scheduling status',
      output: 'No resolution received before escalation cutoff',
      duration: 'Under 1 second',
      status: 'completed',
    },
    'create-eod-exceptions': {
      input: 'Unresolved blocker and Ana follow-up history',
      output: 'Case escalated to Nicole with supporting details',
      duration: 'Under 1 second',
      status: 'attention',
    },
    'notify-eod': {
      input: 'Follow-up result and refreshed Monday and DRK fields',
      output: 'Patient remains unscheduled',
      duration: 'Under 1 second',
      status: 'waiting',
    },
    'resolve-eod': {
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
    'start-weekly-cycle': {
      input: 'Healthy readers and last successful weekly cursor',
      output: 'Weekly schedule loaded; Gloria due for review',
      duration: '0.2 seconds',
      status: 'completed',
    },
    'read-visit-status': {
      input: 'Gloria\'s Monday item and DRK patient ID',
      output: 'DRK progress note records the visit as Not Seen',
      duration: '4.6 seconds',
      status: 'attention',
    },
    'normalize-visit-status': {
      input: 'DRK visit outcome: Not Seen',
      output: 'Visit marked Not Seen for weekly tracking',
      duration: 'Under 1 second',
      status: 'completed',
    },
    'detect-visit-change': {
      input: 'Visit result and current patient status',
      output: 'No healing, expiration, or hold condition recorded',
      duration: 'Under 1 second',
      status: 'completed',
    },
    'update-not-seen-counter': {
      input: 'Previous count 2; new explicit Not Seen event',
      output: 'Consecutive Not Seen count updated to 3',
      duration: 'Under 1 second',
      status: 'attention',
    },
    'classify-weekly-review': {
      input: 'Not Seen count reached the threshold of 3',
      output: 'Human discharge review required',
      duration: 'Under 1 second',
      status: 'attention',
    },
    'create-weekly-exception': {
      input: 'Three Not Seen visits and the review reason',
      output: 'Discharge-review task prepared for management',
      duration: 'Under 1 second',
      status: 'attention',
    },
    'notify-and-reconcile': {
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
