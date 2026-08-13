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
      status: 'Scheduled Yes; complete Yes; appointment date Aug 13',
      followUp: 'Not required · patient already scheduled',
      escalation: 'Not required',
    },
  },
  {
    runId: 'EOD-0821',
    patientName: 'Linda Nguyen',
    occurredAt: 'August 8, 2026 at 5:00 PM',
    status: 'attention',
    values: {
      status: 'Appointment date present; scheduled status blank',
      followUp: 'Lead followed up with CM on Teams',
      escalation: 'Escalated to Nicole via email and spreadsheet',
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
      seen: 'Patient seen',
      healed: 'Wound not healed',
      expired: 'Patient not expired',
      hold: 'Not on hold',
    },
  },
  {
    runId: 'WEEK-0411',
    patientName: 'Arthur Kim',
    occurredAt: 'August 8, 2026 at 6:07 PM',
    status: 'attention',
    values: {
      seen: 'Visit status checked · on hold',
      healed: 'Wound not healed',
      expired: 'Patient not expired',
      hold: 'Moved to holds team · Hospitalization',
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
    case 'check-scheduling-status':
      return {
        input: 'Due referrals at the end-of-day cutoff',
        output: value.status,
      }
    case 'follow-up-case-manager':
      return { input: value.status, output: value.followUp }
    case 'escalate-unresolved-cases':
      return { input: value.followUp, output: value.escalation }
    default:
      return { input: value.followUp, output: value.escalation }
  }
}

function weeklyMoment(historyCase: HistoryCase, stepId: string): HistoryMoment {
  const value = historyCase.values
  switch (stepId) {
    case 'patient-seen':
      return {
        input: 'Active linked patient in this weekly cycle',
        output: value.seen,
      }
    case 'wound-healed':
      return { input: value.seen, output: value.healed }
    case 'patient-expired':
      return { input: value.healed, output: value.expired }
    case 'patient-on-hold':
      return { input: value.expired, output: value.hold }
    default:
      return { input: value.expired, output: value.hold }
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
