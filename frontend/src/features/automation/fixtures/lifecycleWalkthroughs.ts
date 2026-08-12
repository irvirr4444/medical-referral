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
      'Shows how one overdue unscheduled referral moves from Monday review to Teams follow-up and management escalation.',
    patientName: 'Evelyn Brooks',
  },
  steps: {
    'check-scheduling-status': {
      input: 'Evelyn Brooks due at the 5:00 PM cutoff',
      output: 'Unscheduled · appointment date and scheduled status blank on Monday.com',
      duration: '4.8 seconds',
      status: 'attention',
    },
    'follow-up-case-manager': {
      input: 'Unscheduled referral and assigned case manager',
      output: 'Lead sent a Teams follow-up asking why the patient is not scheduled',
      duration: 'Under 1 second',
      status: 'waiting',
    },
    'escalate-unresolved-cases': {
      input: 'No resolution after the Teams follow-up',
      output: 'Patient queued for Nicole and upper-management email plus spreadsheet',
      duration: 'Under 1 second',
      status: 'waiting',
    },
  },
}

const WEEKLY_WALKTHROUGH: LifecycleWalkthrough = {
  run: {
    id: 'walter-weekly',
    label: 'Walter Grant - weekly visit walkthrough',
    source: 'Illustrative Monday and DRK visit snapshots',
    startedAt: 'August 10, 2026 at 6:00 PM',
    summary:
      'Shows how three consecutive Not Seen visits create a human discharge-review request without automatic discharge.',
    patientName: 'Walter Grant',
  },
  steps: {
    'patient-seen': {
      input: 'Walter Grant due in this weekly monitoring cycle',
      output: 'Not Seen · consecutive miss count updated to 3 · queued for DC review',
      duration: '4.6 seconds',
      status: 'attention',
    },
    'wound-healed': {
      input: 'No healed status for this patient',
      output: 'No healed discharge path',
      duration: 'Under 1 second',
      status: 'waiting',
    },
    'patient-expired': {
      input: 'No expired status for this patient',
      output: 'No expired discharge path',
      duration: 'Under 1 second',
      status: 'waiting',
    },
    'patient-on-hold': {
      input: 'No hold status for this patient',
      output:
        'No hold action; patient remains in the seen/not-seen path with no automatic discharge',
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
