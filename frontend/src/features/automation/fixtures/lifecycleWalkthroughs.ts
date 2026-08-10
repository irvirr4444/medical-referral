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
      input: 'Confirmed provider and Riverside service area',
      output: 'Three open provider windows within 48 hours',
      duration: 'Planned',
      status: 'planned',
    },
    'generate-windows': {
      input: 'Open windows, Braxton route, and travel buffers',
      output: 'Thu 10:20 AM; Thu 2:45 PM; Fri 9:15 AM',
      duration: 'Planned',
      status: 'planned',
    },
    'present-windows': {
      input: 'Three route-compatible appointment options',
      output: 'Options sent to Braxton for confirmation',
      duration: 'Planned',
      status: 'planned',
    },
    'monitor-response': {
      input: 'Scheduling request with a one-hour deadline',
      output: 'Thu 10:20 AM accepted after 18 minutes',
      duration: 'Planned',
      status: 'planned',
    },
    'classify-response': {
      input: 'Correlated acceptance for Thu 10:20 AM',
      output: 'Appointment ready for authorized recording',
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
      'Shows how one overdue unscheduled referral becomes one deduplicated review item.',
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
      output: 'No appointment date or completed schedule recorded',
      duration: '4.8 seconds',
      status: 'attention',
    },
    'normalize-scheduling': {
      input: 'Due today; scheduled No; appointment date blank',
      output: 'Unscheduled after the end-of-day cutoff',
      duration: 'Under 1 second',
      status: 'attention',
    },
    'dedupe-eod-alerts': {
      input: 'Evelyn Brooks; scheduling date August 10',
      output: 'No existing exception for this patient and date',
      duration: 'Under 1 second',
      status: 'completed',
    },
    'create-eod-exceptions': {
      input: 'Unscheduled result and missing phone confirmation',
      output: 'One open scheduling exception assigned to management',
      duration: 'Under 1 second',
      status: 'attention',
    },
    'notify-eod': {
      input: 'Today\'s open scheduling exceptions',
      output: 'One consolidated management email queued',
      duration: 'Under 1 second',
      status: 'waiting',
    },
    'resolve-eod': {
      input: 'Open exception and the next source snapshot',
      output: 'Keep open until a complete appointment is recorded',
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
      output: 'Bounded weekly monitoring cycle started',
      duration: '0.1 seconds',
      status: 'completed',
    },
    'load-active-links': {
      input: 'Active patients linked across Monday and DRK',
      output: 'Gloria Bennett selected for this cycle',
      duration: '0.2 seconds',
      status: 'completed',
    },
    'read-visit-status': {
      input: 'Gloria\'s Monday item and DRK patient ID',
      output: 'New DRK visit recorded as Not Seen',
      duration: '4.6 seconds',
      status: 'attention',
    },
    'normalize-visit-status': {
      input: 'DRK visit outcome: Not Seen',
      output: 'Normalized outcome: visit_not_seen',
      duration: 'Under 1 second',
      status: 'completed',
    },
    'detect-visit-change': {
      input: 'New visit ID compared with the prior snapshot',
      output: 'One new visit_not_seen event',
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
      input: 'Patient link, three visit events, and review reason',
      output: 'One open noncompliance review exception',
      duration: 'Under 1 second',
      status: 'attention',
    },
    'notify-and-reconcile': {
      input: 'Open review exception and approved recipients',
      output: 'Review email queued; no automatic discharge',
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
