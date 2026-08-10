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
      windows: 'Fri 11:00 AM; Sat 8:40 AM',
      ranked: 'Fri 11:00 AM ranked first',
      proposal: 'Two options sent to Cole',
      response: 'Fri 11:00 AM accepted after 18 minutes',
      classification: 'Confirmed appointment',
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
      windows: 'Fri 11:00 AM; Sat 8:40 AM',
      ranked: 'Two route-compatible windows',
      proposal: 'Options sent to Carla',
      response: 'No correlated response after one hour',
      classification: 'Scheduling exception for Carla',
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
      source: 'Scheduled Yes; complete Yes; date Aug 13',
      classification: 'Scheduled; all three fields agree',
      dedupe: 'No exception key required',
      exception: 'No exception created',
      notification: 'Excluded from the exception summary',
      resolution: 'Scheduling state remains verified',
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
      source: 'Appointment date present; scheduled status blank',
      classification: 'Indeterminate; scheduling fields conflict',
      dedupe: 'No existing exception for Linda today',
      exception: 'One inconsistency exception opened',
      notification: 'Included once in the management summary',
      resolution: 'Open until all scheduling fields agree',
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
      health: 'Readers healthy; weekly cursor loaded',
      links: 'Helen linked across Monday and DRK',
      source: 'New DRK visit recorded as Seen',
      normalized: 'Normalized outcome: visit_seen',
      change: 'One new visit_seen event',
      counter: 'Not Seen count reset to 0',
      review: 'No review required',
      exception: 'No exception created',
      notification: 'Seen event stored; weekly cycle continues',
    },
  },
  {
    runId: 'WEEK-0411',
    patientName: 'Arthur Kim',
    occurredAt: 'August 8, 2026 at 6:07 PM',
    status: 'attention',
    values: {
      health: 'Readers healthy; weekly cursor loaded',
      links: 'Arthur linked across Monday and DRK',
      source: 'New hospitalization hold recorded',
      normalized: 'Normalized state: patient_on_hold',
      change: 'One new patient_on_hold event',
      counter: 'Not Seen count unchanged',
      review: 'Hold tracking required; no discharge action',
      exception: 'One hold-tracking record opened',
      notification: 'Hold state recorded for human follow-up',
    },
  },
]

function schedulingMoment(historyCase: HistoryCase, stepId: string): HistoryMoment {
  const value = historyCase.values
  switch (stepId) {
    case 'load-scheduling-context':
      return { input: historyCase.patientName, output: value.context }
    case 'read-availability':
      return { input: value.context, output: value.windows }
    case 'generate-windows':
      return { input: value.windows, output: value.ranked }
    case 'present-windows':
      return { input: value.ranked, output: value.proposal }
    case 'monitor-response':
      return { input: value.proposal, output: value.response }
    case 'classify-response':
      return { input: value.response, output: value.classification }
    case 'write-appointment':
      return { input: value.classification, output: value.write }
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
      return { input: value.due, output: value.source }
    case 'normalize-scheduling':
      return { input: value.source, output: value.classification }
    case 'dedupe-eod-alerts':
      return { input: value.classification, output: value.dedupe }
    case 'create-eod-exceptions':
      return { input: value.dedupe, output: value.exception }
    case 'notify-eod':
      return { input: value.exception, output: value.notification }
    default:
      return { input: value.notification, output: value.resolution }
  }
}

function weeklyMoment(historyCase: HistoryCase, stepId: string): HistoryMoment {
  const value = historyCase.values
  switch (stepId) {
    case 'start-weekly-cycle':
      return { input: 'Reader health and last successful cursor', output: value.health }
    case 'load-active-links':
      return { input: 'Active linked patients', output: value.links }
    case 'read-visit-status':
      return { input: value.links, output: value.source }
    case 'normalize-visit-status':
      return { input: value.source, output: value.normalized }
    case 'detect-visit-change':
      return { input: value.normalized, output: value.change }
    case 'update-not-seen-counter':
      return { input: value.change, output: value.counter }
    case 'classify-weekly-review':
      return { input: value.counter, output: value.review }
    case 'create-weekly-exception':
      return { input: value.review, output: value.exception }
    default:
      return { input: value.exception, output: value.notification }
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
