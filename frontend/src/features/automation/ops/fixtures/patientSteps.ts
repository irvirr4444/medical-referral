import type { FlowOpsPageId } from '../../../../data/flowOps'
import { INTAKE_DEMO_BY_ID, INTAKE_DEMO_PATIENTS } from '../../fixtures/intakeDemoPatients'
import type { PatientStepProgress, PatientStepStatus } from '../types'

export const STAGE_STEP_IDS: Record<FlowOpsPageId, string[]> = {
  intake: [
    'receive-referral',
    'extract-and-verify',
    'check-monday',
    'check-drk',
    'confirm-referral-contacted',
  ],
  handoff: [
    'notify-referral-source',
    'create-monday-record',
    'create-update-drk',
  ],
  assignment: [
    'determine-owner',
    'assign-owner',
  ],
  provider: [
    'select-provider',
    'confirm-provider-availability',
    'update-monday-drk',
  ],
  scheduling: [
    'send-referral-provider',
    'schedule-patient',
  ],
  'end-of-day': [
    'check-scheduling-status',
    'follow-up-case-manager',
    'escalate-unresolved-cases',
  ],
  weekly: [
    'patient-seen',
    'wound-healed',
    'patient-expired',
    'patient-on-hold',
  ],
}

type DoneStep = {
  summary: string
  at: string
  detail?: PatientStepProgress['detail']
}
type TailStep = {
  summary: string
  at?: string
  status?: Extract<PatientStepStatus, 'done' | 'current' | 'waiting' | 'blocked'>
  detail?: PatientStepProgress['detail']
}

/** Build ordered step rows: completed prefix, one active tail, remainder upcoming. */
export function progression(
  stageId: FlowOpsPageId,
  done: DoneStep[],
  tail?: TailStep,
): PatientStepProgress[] {
  const ids = STAGE_STEP_IDS[stageId]
  return ids.map((stepId, index) => {
    if (index < done.length) {
      const row = done[index]
      return {
        stepId,
        status: 'done' as const,
        summary: row.summary,
        occurredAt: row.at,
        detail:
          row.detail ??
          autoDetail(row.summary, 'done', row.at),
      }
    }
    if (tail && index === done.length) {
      return {
        stepId,
        status: tail.status ?? 'current',
        summary: tail.summary,
        occurredAt: tail.at,
        detail:
          tail.detail ??
          autoDetail(tail.summary, tail.status ?? 'current', tail.at),
      }
    }
    return {
      stepId,
      status: 'upcoming' as const,
      summary: 'Not started',
      detail: {
        artifactTitle: 'Queued step',
        duration: 'Not started',
        validation: 'This step runs only after earlier gates clear for the patient.',
        fields: [
          { label: 'Outcome', value: 'Not started' },
          { label: 'Gate', value: 'Waiting on prior steps' },
        ],
      },
    }
  })
}

function autoDetail(
  summary: string,
  status: PatientStepStatus,
  at?: string,
): PatientStepProgress['detail'] {
  const statusLine =
    status === 'done'
      ? 'Completed for this patient'
      : status === 'blocked'
        ? 'Blocked pending confirmation'
        : status === 'waiting'
          ? 'Awaiting human confirmation'
          : 'In progress for this patient'

  return {
    artifactTitle: 'Patient step receipt',
    duration:
      status === 'done'
        ? 'Under 2 seconds'
        : status === 'waiting'
          ? 'Awaiting confirmation'
          : status === 'blocked'
            ? 'Blocked pending confirmation'
            : 'In progress',
    validation: statusLine,
    fields: [
      { label: 'Outcome', value: summary },
      { label: 'Status', value: statusLine },
      ...(at ? [{ label: 'Timestamp', value: at }] : []),
      {
        label: 'Operator note',
        value:
          status === 'done'
            ? 'Safe to inspect · no write-back required'
            : status === 'blocked'
              ? 'Resolve the blocker before destination writes'
              : 'Automation is holding for the next human confirmation',
      },
    ],
  }
}

function allDone(stageId: FlowOpsPageId, rows: DoneStep[]): PatientStepProgress[] {
  const ids = STAGE_STEP_IDS[stageId]
  return ids.map((stepId, index) => {
    const row = rows[Math.min(index, rows.length - 1)]
    return {
      stepId,
      status: 'done' as const,
      summary: row.summary,
      occurredAt: row.at,
      detail: row.detail ?? autoDetail(row.summary, 'done', row.at),
    }
  })
}

function intakeStoryKind(patientId: string): 'complete' | 'waiting' | 'threshold' {
  const demo = INTAKE_DEMO_BY_ID[patientId]
  const fq = demo.canonical.field_quality
  const phone = fq['patient.phones']?.status
  const address = fq['patient.address']?.status
  const thresholdOk =
    (fq['patient.name']?.status === 'present' ||
      fq['patient.name']?.status === 'explicitly_none') &&
    (fq['patient.date_of_birth']?.status === 'present' ||
      fq['patient.date_of_birth']?.status === 'explicitly_none') &&
    (phone === 'present' || phone === 'explicitly_none') &&
    (address === 'present' || address === 'explicitly_none')
  if (!thresholdOk) return 'threshold'
  const agency = fq['home_health_or_hospice']?.status
  if (agency === 'present' || agency === 'explicitly_none') return 'complete'
  return 'waiting'
}

const intakeFromDemo = (patientId: string): PatientStepProgress[] => {
  const demo = INTAKE_DEMO_BY_ID[patientId]
  const story = intakeStoryKind(patientId)
  const order = STAGE_STEP_IDS.intake

  if (story === 'complete') {
    return order.map((stepId) => {
      const snap = demo.snapshots[stepId]
      return {
        stepId,
        status: 'done' as const,
        summary:
          stepId === 'confirm-referral-contacted'
            ? 'Partner contact confirmed'
            : snap.output,
        occurredAt: snap.executedAt,
      }
    })
  }

  if (story === 'threshold') {
    return progression(
      'intake',
      order.slice(0, 1).map((stepId) => ({
        summary: demo.snapshots[stepId].output,
        at: demo.snapshots[stepId].executedAt,
      })),
      {
        summary: demo.snapshots['extract-and-verify'].output,
        status: 'blocked',
        at: demo.receivedAt,
      },
    )
  }

  // waiting on confirmation after clear duplicate checks
  return order.map((stepId) => {
    const snap = demo.snapshots[stepId]
    const pending = stepId === 'confirm-referral-contacted'
    return {
      stepId,
      status: pending ? ('waiting' as const) : ('done' as const),
      summary: snap.output,
      occurredAt: snap.executedAt,
    }
  })
}

/** Explicit per-stage patient step breakdowns. */
export const PATIENT_STEP_BREAKDOWNS: Record<
  FlowOpsPageId,
  Record<string, PatientStepProgress[]>
> = {
  intake: Object.fromEntries(
    INTAKE_DEMO_PATIENTS.map((patient) => [
      patient.patientId,
      intakeFromDemo(patient.patientId),
    ]),
  ),
  handoff: Object.fromEntries(
    INTAKE_DEMO_PATIENTS.slice(1).map((patient) => [
      patient.patientId,
      progression(
        'handoff',
        [
          {
            summary: 'Referral source notified and case manager CCd',
            at: patient.receivedAt,
          },
          {
            summary: 'Monday.com record created from canonical referral',
            at: patient.receivedAt,
          },
        ],
        {
          summary: 'DRK chart created from approved intake data',
          status: 'done',
          at: patient.receivedAt,
        },
      ),
    ]),
  ),
  assignment: {
    'marcus-feldman': progression(
      'assignment',
      [
        { summary: 'AI suggests Cole Winfield · Gardena territory', at: 'August 10, 2026 at 9:31 AM' },
      ],
      {
        summary: 'Case manager notification sent',
        status: 'done',
        at: 'August 10, 2026 at 9:32 AM',
      },
    ),
    'david-ruiz': progression(
      'assignment',
      [
        { summary: 'AI found two possible owners · Coastal LA border', at: 'August 10, 2026 at 11:01 AM' },
      ],
      {
        summary: 'Case manager notification sent',
        status: 'done',
        at: 'August 10, 2026 at 11:02 AM',
      },
    ),
    'patricia-johnson': allDone('assignment', [
      { summary: 'Cole Winfield confirmed as case manager', at: 'August 9, 2026 at 12:21 PM' },
    ]),
    'thomas-reed': allDone('assignment', [
      { summary: 'Ana Torres confirmed as case manager', at: 'August 10, 2026 at 3:16 PM' },
    ]),
    'helen-park': allDone('assignment', [
      { summary: 'Cole Winfield confirmed as case manager', at: 'August 9, 2026 at 3:46 PM' },
    ]),
    'betty-hayes': progression(
      'assignment',
      [
        { summary: 'AI suggests manual-review owner · address incomplete', at: 'August 8, 2026 at 1:11 PM' },
      ],
      {
        summary: 'Case manager notification sent',
        status: 'done',
        at: 'August 8, 2026 at 1:12 PM',
      },
    ),
    'maria-alvarez': progression(
      'assignment',
      [
        { summary: 'AI suggests Donessa Ruiz · Riverside territory', at: 'August 10, 2026 at 10:16 AM' },
      ],
      { summary: 'Case manager notification sent', status: 'done', at: 'August 10, 2026 at 10:16 AM' },
    ),
  },
  provider: {
    'helen-park': progression(
      'provider',
      [
        { summary: '3 eligible providers found for the service area', at: 'August 10, 2026 at 8:51 AM' },
      ],
      { summary: 'AI recommendation ready · awaiting case-manager selection', status: 'waiting', at: 'August 10, 2026 at 8:52 AM' },
    ),
    'irene-cho': progression(
      'provider',
      [
        { summary: '2 eligible providers found for the service area', at: 'August 10, 2026 at 9:21 AM' },
      ],
      {
        summary: 'Provider availability not confirmed within one hour',
        status: 'blocked',
        at: 'August 10, 2026 at 9:22 AM',
      },
    ),
    'betty-hayes': progression(
      'provider',
      [
        { summary: '1 eligible provider found after expanded search', at: 'August 9, 2026 at 2:01 PM' },
      ],
      {
        summary: 'Provider availability requires Nicole review',
        status: 'blocked',
        at: 'August 9, 2026 at 2:02 PM',
      },
    ),
    'patricia-johnson': allDone('provider', [
      { summary: 'Provider selected', at: 'August 9, 2026 at 1:05 PM' },
      { summary: 'Provider availability confirmed', at: 'August 9, 2026 at 1:06 PM' },
      { summary: 'Monday.com and DRK updated with assigned provider', at: 'August 9, 2026 at 1:07 PM' },
    ]),
    'thomas-reed': allDone('provider', [
      { summary: 'Provider selected', at: 'August 10, 2026 at 3:40 PM' },
      { summary: 'Provider availability confirmed', at: 'August 10, 2026 at 3:41 PM' },
      { summary: 'Monday.com and DRK updated with assigned provider', at: 'August 10, 2026 at 3:42 PM' },
    ]),
    'maria-alvarez': progression(
      'provider',
      [
        { summary: '5 eligible providers found for Riverside', at: 'August 10, 2026 at 10:21 AM' },
      ],
      { summary: 'AI recommendation ready · awaiting case-manager selection', status: 'waiting' },
    ),
    'nancy-liu': allDone('provider', [
      { summary: 'Provider selected', at: 'August 8, 2026 at 4:30 PM' },
      { summary: 'Provider availability confirmed', at: 'August 8, 2026 at 4:31 PM' },
      { summary: 'Monday.com and DRK updated with assigned provider', at: 'August 8, 2026 at 4:32 PM' },
    ]),
  },
  scheduling: {
    'maria-alvarez': progression(
      'scheduling',
      [
        { summary: 'Referral sent to provider', at: 'August 10, 2026 at 10:05 AM' },
      ],
      { summary: 'Awaiting appointment placement within provider availability', status: 'waiting', at: 'August 10, 2026 at 10:07 AM' },
    ),
    'nancy-liu': allDone('scheduling', [
      { summary: 'Referral sent to provider', at: 'August 10, 2026 at 8:31 AM' },
      { summary: 'Patient scheduled within 24–48 hours', at: 'August 10, 2026 at 9:11 AM' },
    ]),
    'james-carter': progression(
      'scheduling',
      [
        { summary: 'Referral sent to provider', at: 'August 10, 2026 at 9:02 AM' },
      ],
      {
        summary: 'Case manager must place patient using known provider availability',
        status: 'blocked',
        at: 'August 10, 2026 at 10:05 AM',
      },
    ),
    'patricia-johnson': allDone('scheduling', [
      { summary: 'Referral sent to provider', at: 'August 9, 2026 at 2:01 PM' },
      { summary: 'Patient scheduled within 24–48 hours', at: 'August 9, 2026 at 3:19 PM' },
    ]),
    'thomas-reed': progression(
      'scheduling',
      [
        { summary: 'Referral sent to provider', at: 'August 10, 2026 at 3:45 PM' },
      ],
      { summary: 'Awaiting appointment placement', status: 'waiting', at: 'August 10, 2026 at 3:47 PM' },
    ),
    'linda-nguyen': progression(
      'scheduling',
      [
        { summary: 'Referral sent to provider', at: 'August 9, 2026 at 4:00 PM' },
      ],
      {
        summary: 'Patient declined available appointment windows',
        status: 'blocked',
        at: 'August 9, 2026 at 5:30 PM',
      },
    ),
    'helen-park': allDone('scheduling', [
      { summary: 'Referral sent to provider', at: 'August 8, 2026 at 5:00 PM' },
      { summary: 'Patient scheduled within 24–48 hours', at: 'August 8, 2026 at 5:41 PM' },
    ]),
  },
  'end-of-day': {
    'anita-gomez': allDone('end-of-day', [
      { summary: 'Scheduled · Monday fields agree', at: 'August 12, 2026 at 5:01 PM' },
      { summary: 'No follow-up required', at: 'August 12, 2026 at 5:01 PM' },
      { summary: 'No escalation required', at: 'August 12, 2026 at 5:01 PM' },
    ]),
    'susan-park': allDone('end-of-day', [
      { summary: 'Scheduled · Monday fields agree', at: 'August 12, 2026 at 5:01 PM' },
      { summary: 'No follow-up required', at: 'August 12, 2026 at 5:01 PM' },
      { summary: 'No escalation required', at: 'August 12, 2026 at 5:01 PM' },
    ]),
    'nancy-liu': allDone('end-of-day', [
      { summary: 'Scheduled · Monday fields agree', at: 'August 12, 2026 at 5:01 PM' },
      { summary: 'No follow-up required', at: 'August 12, 2026 at 5:01 PM' },
      { summary: 'No escalation required', at: 'August 12, 2026 at 5:01 PM' },
    ]),
    'helen-park': allDone('end-of-day', [
      { summary: 'Scheduled · Monday fields agree', at: 'August 12, 2026 at 5:01 PM' },
      { summary: 'No follow-up required', at: 'August 12, 2026 at 5:01 PM' },
      { summary: 'No escalation required', at: 'August 12, 2026 at 5:01 PM' },
    ]),
    'maria-alvarez': progression(
      'end-of-day',
      [{ summary: 'Not scheduled · 36 hours', at: 'August 12, 2026 at 5:01 PM' }],
      {
        summary: 'Donessa Ruiz notified on Teams automatically',
        status: 'done',
        at: 'August 12, 2026 at 5:02 PM',
      },
    ),
    'thomas-reed': progression('end-of-day', [], {
      summary: 'Not scheduled · 18 hours',
      status: 'waiting',
      at: 'August 12, 2026 at 5:01 PM',
    }),
    'james-carter': progression(
      'end-of-day',
      [{ summary: 'Not scheduled · 56 hours', at: 'August 12, 2026 at 5:01 PM' }],
      {
        summary: 'Carla Bustillo notified on Teams automatically',
        status: 'done',
        at: 'August 12, 2026 at 5:02 PM',
      },
    ),
    'frank-owens': progression(
      'end-of-day',
      [{ summary: 'Not scheduled · 51 hours', at: 'August 12, 2026 at 5:01 PM' }],
      {
        summary: 'Braxton Rickert notified on Teams automatically',
        status: 'done',
        at: 'August 12, 2026 at 5:02 PM',
      },
    ),
    'george-chen': progression(
      'end-of-day',
      [{ summary: 'Not scheduled · 54 hours', at: 'August 12, 2026 at 5:01 PM' }],
      {
        summary: 'Carla Bustillo notified on Teams automatically',
        status: 'done',
        at: 'August 12, 2026 at 5:02 PM',
      },
    ),
    'linda-nguyen': progression(
      'end-of-day',
      [
        {
          summary: 'Not scheduled · 73 hours',
          at: 'August 12, 2026 at 5:01 PM',
        },
        {
          summary: 'Nicole Chorvat notified on Teams automatically',
          at: 'August 12, 2026 at 5:02 PM',
        },
      ],
      {
        summary: 'Escalated to management · still unresolved',
        status: 'blocked',
        at: 'August 12, 2026 at 5:03 PM',
      },
    ),
  },
  weekly: {
    'gloria-bennett': allDone('weekly', [
      { summary: 'Patient seen', at: 'August 10, 2026 at 6:01 PM' },
      { summary: 'Wound not healed', at: 'August 10, 2026 at 6:01 PM' },
      { summary: 'Patient not expired', at: 'August 10, 2026 at 6:01 PM' },
      { summary: 'Not on hold', at: 'August 10, 2026 at 6:01 PM' },
    ]),
    'dorothy-lane': allDone('weekly', [
      { summary: 'Patient seen', at: 'August 9, 2026 at 6:01 PM' },
      { summary: 'Wound not healed', at: 'August 9, 2026 at 6:01 PM' },
      { summary: 'Patient not expired', at: 'August 9, 2026 at 6:01 PM' },
      { summary: 'Not on hold', at: 'August 9, 2026 at 6:01 PM' },
    ]),
    'helen-park': allDone('weekly', [
      { summary: 'Patient seen', at: 'August 9, 2026 at 6:05 PM' },
      { summary: 'Wound not healed', at: 'August 9, 2026 at 6:05 PM' },
      { summary: 'Patient not expired', at: 'August 9, 2026 at 6:05 PM' },
      { summary: 'Not on hold', at: 'August 9, 2026 at 6:05 PM' },
    ]),
    'james-carter': progression(
      'weekly',
      [
        { summary: 'Visit status checked', at: 'August 8, 2026 at 6:03 PM' },
        { summary: 'Wound not healed', at: 'August 8, 2026 at 6:03 PM' },
      ],
      {
        summary: 'Patient expired',
        status: 'waiting',
        at: 'August 8, 2026 at 6:04 PM',
      },
    ),
    'nancy-liu': progression(
      'weekly',
      [{ summary: 'Visit status checked', at: 'August 10, 2026 at 6:05 PM' }],
      {
        summary: 'Wound healed',
        status: 'waiting',
        at: 'August 10, 2026 at 6:06 PM',
      },
    ),
    'patricia-johnson': progression('weekly', [], {
      summary: 'Not seen · 1 consecutive week',
      status: 'waiting',
      at: 'August 8, 2026 at 6:01 PM',
    }),
    'margaret-ellis': progression('weekly', [], {
      summary: 'Not seen · 2 consecutive weeks',
      status: 'waiting',
      at: 'August 10, 2026 at 6:01 PM',
    }),
    'walter-grant': progression('weekly', [], {
      summary: 'Not seen · 3 consecutive weeks',
      status: 'waiting',
      at: 'August 10, 2026 at 6:01 PM',
    }),
    'arthur-kim': progression(
      'weekly',
      [
        { summary: 'Visit status checked', at: 'August 10, 2026 at 6:02 PM' },
        { summary: 'Wound not healed', at: 'August 10, 2026 at 6:02 PM' },
        { summary: 'Patient not expired', at: 'August 10, 2026 at 6:02 PM' },
      ],
      {
        summary: 'On hold · Hospitalization',
        status: 'waiting',
        at: 'August 10, 2026 at 6:03 PM',
      },
    ),
    'linda-nguyen': progression(
      'weekly',
      [
        { summary: 'Visit status checked', at: 'August 9, 2026 at 6:07 PM' },
        { summary: 'Wound not healed', at: 'August 9, 2026 at 6:07 PM' },
        { summary: 'Patient not expired', at: 'August 9, 2026 at 6:07 PM' },
      ],
      {
        summary: 'On hold · Facility hold',
        status: 'waiting',
        at: 'August 9, 2026 at 6:08 PM',
      },
    ),
  },
}
