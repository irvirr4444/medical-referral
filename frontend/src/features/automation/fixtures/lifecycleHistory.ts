import type { FlowOpsPageId } from '../../../data/flowOps'
import type {
  AutomationMicrostep,
  AutomationRunFixture,
  MicrostepExample,
  MicrostepRunStatus,
} from '../types'

export interface LifecycleHistoryEntry {
  id: string
  runId: string
  patientName: string
  occurredAt: string
  status: MicrostepRunStatus
  input: string
  output: string
}

interface HistoryCase {
  runId: string
  patientName: string
  occurredAt: string
  status: MicrostepRunStatus
  values: Record<string, string>
}

interface HistoryMoment {
  input: string
  output: string
}

const SCHEDULING_CASES: HistoryCase[] = [
  {
    runId: 'SCHED-1038',
    patientName: 'Patricia Johnson',
    occurredAt: 'August 9, 2026 at 3:18 PM',
    status: 'completed',
    values: {
      context: 'Provider confirmed; Gardena address; Cole assigned',
      delivery: 'Referral sent to Dr. Nguyen',
      providerResponse: 'Provider responded after 18 minutes',
      availability: 'Fri 11:00 AM; Sat 8:40 AM',
      options: 'Fri 11:00 AM ranked first',
      confirmation: 'Cole confirmed Fri 11:00 AM',
      write: 'Monday and DRK appointment updates prepared',
      reconcile: 'Friday appointment verified',
    },
  },
  {
    runId: 'SCHED-1031',
    patientName: 'James Carter',
    occurredAt: 'August 8, 2026 at 11:42 AM',
    status: 'waiting',
    values: {
      context: 'Provider confirmed; Coastal LA; Carla assigned',
      delivery: 'Referral sent to selected provider',
      providerResponse: 'No provider response after one hour',
      availability: 'Availability not confirmed',
      options: 'No appointment options generated',
      confirmation: 'Scheduling blocker assigned to Carla',
      write: 'No destination write allowed',
      reconcile: 'Exception remains open for human placement',
    },
  },
]

const END_OF_DAY_CASES: HistoryCase[] = [
  {
    runId: 'EOD-0826',
    patientName: 'Maria Alvarez',
    occurredAt: 'August 9, 2026 at 5:00 PM',
    status: 'completed',
    values: {
      health: '5:00 PM cutoff; both readers healthy',
      due: 'Maria due for scheduling review',
      owner: 'Ana assigned; appointment date Aug 13',
      followup: 'No follow-up needed; patient already scheduled',
      tracking: 'Scheduling confirmed',
      escalation: 'No escalation required',
      verification: 'Scheduled Yes; complete Yes; date Aug 13',
      weekly: 'Patient entered the weekly visit cycle',
    },
  },
  {
    runId: 'EOD-0821',
    patientName: 'Linda Nguyen',
    occurredAt: 'August 8, 2026 at 5:00 PM',
    status: 'attention',
    values: {
      health: '5:00 PM cutoff; both readers healthy',
      due: 'Linda due for scheduling review',
      owner: 'Carla assigned; scheduled status blank',
      followup: 'Follow-up sent to Carla and intake lead',
      tracking: 'Blocker remains unresolved',
      escalation: 'Escalated to Nicole with scheduling details',
      verification: 'Appointment date present; scheduled status blank',
      weekly: 'Weekly-cycle entry held until scheduling is verified',
    },
  },
]

const WEEKLY_CASES: HistoryCase[] = [
  {
    runId: 'WEEK-0418',
    patientName: 'Helen Park',
    occurredAt: 'August 9, 2026 at 6:04 PM',
    status: 'completed',
    values: {
      schedule: 'Weekly schedule loaded; Helen due for review',
      progress: 'DRK progress note records Seen',
      outcome: 'Visit marked Seen',
      condition: 'No healing, expiration, or hold condition',
      counter: 'Not Seen count reset to 0',
      review: 'No review required',
      action: 'Continue the weekly visit cycle',
      notification: 'Monday updated; no team alert required',
    },
  },
  {
    runId: 'WEEK-0411',
    patientName: 'Arthur Kim',
    occurredAt: 'August 8, 2026 at 6:07 PM',
    status: 'attention',
    values: {
      schedule: 'Weekly schedule loaded; Arthur due for review',
      progress: 'DRK records hospitalization',
      outcome: 'No completed weekly visit',
      condition: 'Hospitalization hold recorded',
      counter: 'Not Seen count unchanged',
      review: 'Hold tracking required; no discharge action',
      action: 'Hold-team follow-up prepared',
      notification: 'Hold state updated and team notified',
    },
  },
]

function schedulingMoment(historyCase: HistoryCase, stepId: string): HistoryMoment {
  const value = historyCase.values
  switch (stepId) {
    case 'load-scheduling-context':
      return { input: historyCase.patientName, output: value.context }
    case 'read-availability':
      return { input: value.context, output: value.delivery }
    case 'generate-windows':
      return { input: value.delivery, output: value.providerResponse }
    case 'present-windows':
      return { input: value.providerResponse, output: value.availability }
    case 'monitor-response':
      return { input: value.availability, output: value.options }
    case 'classify-response':
      return { input: value.options, output: value.confirmation }
    case 'write-appointment':
      return { input: value.confirmation, output: value.write }
    default:
      return { input: value.write, output: value.reconcile }
  }
}

function endOfDayMoment(historyCase: HistoryCase, stepId: string): HistoryMoment {
  const value = historyCase.values
  switch (stepId) {
    case 'start-eod-cycle':
      return { input: 'Cutoff configuration and reader health', output: value.health }
    case 'load-due-referrals':
      return { input: 'Active referrals due by cutoff', output: value.due }
    case 'read-eod-sources':
      return { input: value.due, output: value.owner }
    case 'normalize-scheduling':
      return { input: value.owner, output: value.followup }
    case 'dedupe-eod-alerts':
      return { input: value.followup, output: value.tracking }
    case 'create-eod-exceptions':
      return { input: value.tracking, output: value.escalation }
    case 'notify-eod':
      return { input: value.escalation, output: value.verification }
    default:
      return { input: value.verification, output: value.weekly }
  }
}

function weeklyMoment(historyCase: HistoryCase, stepId: string): HistoryMoment {
  const value = historyCase.values
  switch (stepId) {
    case 'start-weekly-cycle':
      return { input: 'Reader health and weekly schedule date', output: value.schedule }
    case 'read-visit-status':
      return { input: value.schedule, output: value.progress }
    case 'normalize-visit-status':
      return { input: value.progress, output: value.outcome }
    case 'detect-visit-change':
      return { input: value.outcome, output: value.condition }
    case 'update-not-seen-counter':
      return { input: value.condition, output: value.counter }
    case 'classify-weekly-review':
      return { input: value.counter, output: value.review }
    case 'create-weekly-exception':
      return { input: value.review, output: value.action }
    default:
      return { input: value.action, output: value.notification }
  }
}

function priorEntries(
  stageId: FlowOpsPageId,
  stepId: string,
): LifecycleHistoryEntry[] {
  const cases =
    stageId === 'scheduling'
      ? SCHEDULING_CASES
      : stageId === 'end-of-day'
        ? END_OF_DAY_CASES
        : stageId === 'weekly'
          ? WEEKLY_CASES
          : []
  const momentFor =
    stageId === 'scheduling'
      ? schedulingMoment
      : stageId === 'end-of-day'
        ? endOfDayMoment
        : weeklyMoment

  return cases.map((historyCase) => {
    const moment = momentFor(historyCase, stepId)
    return {
      id: `${historyCase.runId}-${stepId}`,
      runId: historyCase.runId,
      patientName: historyCase.patientName,
      occurredAt: historyCase.occurredAt,
      status: historyCase.status,
      input: moment.input,
      output: moment.output,
    }
  })
}

export function lifecycleHistoryForStep(
  stageId: FlowOpsPageId,
  step: AutomationMicrostep,
  run: AutomationRunFixture,
  example: MicrostepExample,
): LifecycleHistoryEntry[] {
  if (stageId === 'intake') {
    const snapshot = run.intakeSnapshots?.[step.id]
    if (!snapshot) return []

    return [
      {
        id: `${run.id}-${step.id}`,
        runId: run.id.toUpperCase(),
        patientName: run.patientName ?? 'Walkthrough patient',
        occurredAt: snapshot.executedAt,
        status: snapshot.status,
        input: snapshot.input,
        output: snapshot.output,
      },
    ]
  }

  if (!['scheduling', 'end-of-day', 'weekly'].includes(stageId)) return []

  const latest: LifecycleHistoryEntry = {
    id: `${run.id}-${step.id}`,
    runId: run.id.toUpperCase(),
    patientName: run.patientName ?? 'Walkthrough patient',
    occurredAt: run.startedAt,
    status: example.status,
    input: example.inputs[0]?.value ?? 'No input recorded',
    output: example.outputs[0]?.value ?? 'No output recorded',
  }

  return [latest, ...priorEntries(stageId, step.id)]
}
