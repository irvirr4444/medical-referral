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
    'load-approved-plan',
    'map-monday-fields',
    'resolve-agency',
    'write-monday',
    'prepare-drk',
    'apply-drk',
    'link-destinations',
    'reconcile-handoff',
  ],
  assignment: [
    'load-assignment-context',
    'normalize-location',
    'load-territories',
    'match-owner',
    'classify-assignment',
    'confirm-assignment',
    'write-assignment',
  ],
  provider: [
    'load-provider-context',
    'load-provider-roster',
    'filter-providers',
    'rank-providers',
    'classify-provider-result',
    'confirm-provider',
    'write-provider',
  ],
  scheduling: [
    'load-scheduling-context',
    'read-availability',
    'generate-windows',
    'present-windows',
    'monitor-response',
    'classify-response',
    'write-appointment',
    'reconcile-appointment',
  ],
  'end-of-day': [
    'start-eod-cycle',
    'load-due-referrals',
    'read-eod-sources',
    'normalize-scheduling',
    'dedupe-eod-alerts',
    'create-eod-exceptions',
    'notify-eod',
    'resolve-eod',
  ],
  weekly: [
    'start-weekly-cycle',
    'load-active-links',
    'read-visit-status',
    'normalize-visit-status',
    'detect-visit-change',
    'update-not-seen-counter',
    'classify-weekly-review',
    'create-weekly-exception',
    'notify-and-reconcile',
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
  status?: Extract<PatientStepStatus, 'current' | 'waiting' | 'blocked'>
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
  handoff: {
    'maria-alvarez': progression(
      'handoff',
      [
        { summary: 'Approved plan locked', at: 'August 10, 2026 at 10:05 AM' },
        { summary: 'Monday fields mapped', at: 'August 10, 2026 at 10:06 AM' },
        { summary: 'Agency matched', at: 'August 10, 2026 at 10:06 AM' },
        { summary: 'Master Sheet item created', at: 'August 10, 2026 at 10:07 AM' },
      ],
      {
        summary: 'DRK chart draft ready for assisted entry',
        status: 'current',
        at: 'August 10, 2026 at 10:09 AM',
      },
    ),
    'james-carter': progression(
      'handoff',
      [
        { summary: 'Approved plan locked', at: 'August 10, 2026 at 9:40 AM' },
        { summary: 'Monday fields mapped', at: 'August 10, 2026 at 9:41 AM' },
      ],
      {
        summary: 'Two Accounts matches · relation withheld',
        status: 'blocked',
        at: 'August 10, 2026 at 9:42 AM',
      },
    ),
    'linda-nguyen': progression(
      'handoff',
      [
        { summary: 'Approved plan locked', at: 'August 10, 2026 at 11:15 AM' },
        { summary: 'Monday fields mapped', at: 'August 10, 2026 at 11:16 AM' },
        { summary: 'Agency matched', at: 'August 10, 2026 at 11:16 AM' },
        { summary: 'Master Sheet item created', at: 'August 10, 2026 at 11:17 AM' },
      ],
      {
        summary: 'DRK Create Patient prepared',
        status: 'current',
        at: 'August 10, 2026 at 11:20 AM',
      },
    ),
    'patricia-johnson': allDone('handoff', [
      { summary: 'Handoff verified', at: 'August 9, 2026 at 11:20 AM' },
    ]),
    'thomas-reed': allDone('handoff', [
      { summary: 'Handoff verified', at: 'August 10, 2026 at 2:54 PM' },
    ]),
    'irene-cho': progression(
      'handoff',
      [
        { summary: 'Approved plan locked', at: 'August 8, 2026 at 4:20 PM' },
        { summary: 'Monday fields mapped', at: 'August 8, 2026 at 4:21 PM' },
        { summary: 'Master Sheet created', at: 'August 8, 2026 at 4:22 PM' },
      ],
      {
        summary: 'Zero agency matches · unresolved',
        status: 'blocked',
        at: 'August 8, 2026 at 4:23 PM',
      },
    ),
    'helen-park': allDone('handoff', [
      { summary: 'Handoff verified', at: 'August 9, 2026 at 3:14 PM' },
    ]),
  },
  assignment: {
    'marcus-feldman': progression(
      'assignment',
      [
        { summary: 'Assignment context loaded', at: 'August 10, 2026 at 9:30 AM' },
        { summary: 'Location normalized', at: 'August 10, 2026 at 9:30 AM' },
        { summary: 'Territories loaded', at: 'August 10, 2026 at 9:31 AM' },
        { summary: 'Gardena · Cole suggested', at: 'August 10, 2026 at 9:31 AM' },
      ],
      {
        summary: 'Awaiting marketer confirmation',
        status: 'waiting',
        at: 'August 10, 2026 at 9:32 AM',
      },
    ),
    'david-ruiz': progression(
      'assignment',
      [
        { summary: 'Context loaded', at: 'August 10, 2026 at 11:00 AM' },
        { summary: 'Location normalized', at: 'August 10, 2026 at 11:00 AM' },
        { summary: 'Territories loaded', at: 'August 10, 2026 at 11:01 AM' },
        { summary: 'Coastal LA · Carla suggested', at: 'August 10, 2026 at 11:01 AM' },
      ],
      {
        summary: 'Border territory · dual owner candidates',
        status: 'blocked',
        at: 'August 10, 2026 at 11:02 AM',
      },
    ),
    'patricia-johnson': allDone('assignment', [
      { summary: 'Owner written to Monday and DRK', at: 'August 9, 2026 at 12:21 PM' },
    ]),
    'thomas-reed': allDone('assignment', [
      { summary: 'Assignment written', at: 'August 10, 2026 at 3:16 PM' },
    ]),
    'helen-park': allDone('assignment', [
      { summary: 'Assignment written', at: 'August 9, 2026 at 3:46 PM' },
    ]),
    'betty-hayes': progression(
      'assignment',
      [
        { summary: 'Context loaded', at: 'August 8, 2026 at 1:10 PM' },
        { summary: 'Location normalized', at: 'August 8, 2026 at 1:10 PM' },
        { summary: 'Territories loaded', at: 'August 8, 2026 at 1:11 PM' },
        { summary: 'Unknown ZIP · no territory', at: 'August 8, 2026 at 1:11 PM' },
      ],
      {
        summary: 'Manual owner selection required',
        status: 'blocked',
        at: 'August 8, 2026 at 1:12 PM',
      },
    ),
    'maria-alvarez': progression(
      'assignment',
      [
        { summary: 'Ready after Monday create', at: 'August 10, 2026 at 10:15 AM' },
        { summary: 'Location normalized', at: 'August 10, 2026 at 10:15 AM' },
        { summary: 'Territories loaded', at: 'August 10, 2026 at 10:16 AM' },
        { summary: 'Riverside · Ana suggested', at: 'August 10, 2026 at 10:16 AM' },
      ],
      { summary: 'Awaiting confirmation', status: 'waiting', at: 'August 10, 2026 at 10:16 AM' },
    ),
  },
  provider: {
    'helen-park': progression(
      'provider',
      [
        { summary: 'Provider context loaded', at: 'August 10, 2026 at 8:50 AM' },
        { summary: 'Roster loaded', at: 'August 10, 2026 at 8:50 AM' },
        { summary: 'Providers filtered', at: 'August 10, 2026 at 8:51 AM' },
        { summary: '3 credentialed providers ranked', at: 'August 10, 2026 at 8:51 AM' },
      ],
      { summary: 'Awaiting marketer pick', status: 'waiting', at: 'August 10, 2026 at 8:52 AM' },
    ),
    'irene-cho': progression(
      'provider',
      [
        { summary: 'Context loaded', at: 'August 10, 2026 at 9:20 AM' },
        { summary: 'Roster loaded', at: 'August 10, 2026 at 9:20 AM' },
        { summary: 'Filtered to radius', at: 'August 10, 2026 at 9:21 AM' },
        { summary: '2 providers ranked', at: 'August 10, 2026 at 9:21 AM' },
      ],
      {
        summary: 'Preferred provider at capacity',
        status: 'blocked',
        at: 'August 10, 2026 at 9:22 AM',
      },
    ),
    'betty-hayes': progression(
      'provider',
      [
        { summary: 'Context loaded', at: 'August 9, 2026 at 2:00 PM' },
        { summary: 'Roster loaded', at: 'August 9, 2026 at 2:00 PM' },
        { summary: 'Filter applied', at: 'August 9, 2026 at 2:01 PM' },
        { summary: 'Empty shortlist', at: 'August 9, 2026 at 2:01 PM' },
      ],
      {
        summary: 'No eligible provider · human search',
        status: 'blocked',
        at: 'August 9, 2026 at 2:02 PM',
      },
    ),
    'patricia-johnson': allDone('provider', [
      { summary: 'Provider written to destinations', at: 'August 9, 2026 at 1:06 PM' },
    ]),
    'thomas-reed': allDone('provider', [
      { summary: 'Provider written', at: 'August 10, 2026 at 3:41 PM' },
    ]),
    'maria-alvarez': progression(
      'provider',
      [
        { summary: 'Context loaded', at: 'August 10, 2026 at 10:20 AM' },
        { summary: 'Roster loaded', at: 'August 10, 2026 at 10:20 AM' },
        { summary: 'Filtered', at: 'August 10, 2026 at 10:21 AM' },
        { summary: '5 providers ranked for Riverside', at: 'August 10, 2026 at 10:21 AM' },
      ],
      { summary: 'Shortlist ready · awaiting confirm', status: 'waiting' },
    ),
    'nancy-liu': allDone('provider', [
      { summary: 'Provider written', at: 'August 8, 2026 at 4:31 PM' },
    ]),
  },
  scheduling: {
    'maria-alvarez': progression(
      'scheduling',
      [
        { summary: 'Patient, provider, location ready', at: 'August 10, 2026 at 10:05 AM' },
        { summary: 'Availability windows read', at: 'August 10, 2026 at 10:05 AM' },
        { summary: 'Fri 11:00 AM · Sat 8:40 AM ranked', at: 'August 10, 2026 at 10:06 AM' },
        { summary: 'Options sent to Ana', at: 'August 10, 2026 at 10:07 AM' },
      ],
      { summary: 'No reply yet', status: 'waiting', at: 'August 10, 2026 at 10:07 AM' },
    ),
    'nancy-liu': allDone('scheduling', [
      { summary: 'Appointment written to Monday and DRK', at: 'August 10, 2026 at 9:11 AM' },
    ]),
    'james-carter': progression(
      'scheduling',
      [
        { summary: 'Context loaded', at: 'August 10, 2026 at 9:00 AM' },
        { summary: 'Availability read', at: 'August 10, 2026 at 9:00 AM' },
        { summary: 'Two windows generated', at: 'August 10, 2026 at 9:01 AM' },
        { summary: 'Options sent to Carla', at: 'August 10, 2026 at 9:02 AM' },
        { summary: 'No correlated response after one hour', at: 'August 10, 2026 at 10:05 AM' },
      ],
      {
        summary: 'Scheduling exception for Carla',
        status: 'blocked',
        at: 'August 10, 2026 at 10:05 AM',
      },
    ),
    'patricia-johnson': allDone('scheduling', [
      { summary: 'Appointment written', at: 'August 9, 2026 at 3:19 PM' },
    ]),
    'thomas-reed': progression(
      'scheduling',
      [
        { summary: 'Context loaded', at: 'August 10, 2026 at 3:45 PM' },
        { summary: 'Availability read', at: 'August 10, 2026 at 3:45 PM' },
        { summary: 'Three windows proposed', at: 'August 10, 2026 at 3:46 PM' },
        { summary: 'Options sent to Ana', at: 'August 10, 2026 at 3:47 PM' },
      ],
      { summary: 'Awaiting Ana response', status: 'waiting', at: 'August 10, 2026 at 3:47 PM' },
    ),
    'linda-nguyen': progression(
      'scheduling',
      [
        { summary: 'Context loaded', at: 'August 9, 2026 at 4:00 PM' },
        { summary: 'Availability read', at: 'August 9, 2026 at 4:00 PM' },
        { summary: 'Two windows generated', at: 'August 9, 2026 at 4:01 PM' },
        { summary: 'Options presented', at: 'August 9, 2026 at 4:01 PM' },
        { summary: 'Patient declined both windows', at: 'August 9, 2026 at 5:30 PM' },
      ],
      {
        summary: 'Scheduling exception open',
        status: 'blocked',
        at: 'August 9, 2026 at 5:30 PM',
      },
    ),
    'helen-park': allDone('scheduling', [
      { summary: 'Appointment written', at: 'August 8, 2026 at 5:41 PM' },
    ]),
  },
  'end-of-day': {
    'anita-gomez': allDone('end-of-day', [
      { summary: 'Scheduled & consistent', at: 'August 10, 2026 at 5:01 PM' },
    ]),
    'frank-owens': progression(
      'end-of-day',
      [
        { summary: 'EOD cycle started', at: 'August 10, 2026 at 5:00 PM' },
        { summary: 'Due referrals loaded', at: 'August 10, 2026 at 5:00 PM' },
        { summary: 'Sources read', at: 'August 10, 2026 at 5:01 PM' },
        { summary: 'Appointment date present · scheduled blank', at: 'August 10, 2026 at 5:01 PM' },
        { summary: 'No prior exception today', at: 'August 10, 2026 at 5:01 PM' },
        { summary: 'Inconsistency exception opened', at: 'August 10, 2026 at 5:02 PM' },
        { summary: 'Included in management summary', at: 'August 10, 2026 at 5:03 PM' },
      ],
      { summary: 'Open until fields agree', status: 'waiting', at: 'August 10, 2026 at 5:03 PM' },
    ),
    'susan-park': allDone('end-of-day', [
      { summary: 'All scheduling fields agree', at: 'August 10, 2026 at 5:01 PM' },
    ]),
    'george-chen': progression(
      'end-of-day',
      [
        { summary: 'EOD cycle started', at: 'August 10, 2026 at 5:00 PM' },
        { summary: 'Due referrals loaded', at: 'August 10, 2026 at 5:00 PM' },
        { summary: 'Sources read', at: 'August 10, 2026 at 5:01 PM' },
        { summary: 'Complete flag No · date set', at: 'August 10, 2026 at 5:01 PM' },
        { summary: 'Deduped', at: 'August 10, 2026 at 5:01 PM' },
        { summary: 'Exception opened', at: 'August 10, 2026 at 5:02 PM' },
      ],
      { summary: 'Awaiting resolution', status: 'waiting' },
    ),
    'linda-nguyen': progression(
      'end-of-day',
      [
        { summary: 'EOD cycle started', at: 'August 9, 2026 at 5:00 PM' },
        { summary: 'Due referrals loaded', at: 'August 9, 2026 at 5:00 PM' },
        { summary: 'Sources read', at: 'August 9, 2026 at 5:01 PM' },
        { summary: 'Indeterminate scheduling fields', at: 'August 9, 2026 at 5:01 PM' },
        { summary: 'Deduped', at: 'August 9, 2026 at 5:01 PM' },
        { summary: 'Exception opened Aug 9', at: 'August 9, 2026 at 5:02 PM' },
        { summary: 'Included once in summary', at: 'August 9, 2026 at 5:03 PM' },
      ],
      { summary: 'Still open', status: 'waiting', at: 'August 9, 2026 at 5:03 PM' },
    ),
    'maria-alvarez': allDone('end-of-day', [
      { summary: 'Scheduled · fields agree', at: 'August 9, 2026 at 5:01 PM' },
    ]),
    'nancy-liu': allDone('end-of-day', [
      { summary: 'Consistent · excluded from exception summary', at: 'August 8, 2026 at 5:03 PM' },
    ]),
    'helen-park': allDone('end-of-day', [
      { summary: 'Appointment Aug 12 · fields agree', at: 'August 8, 2026 at 5:05 PM' },
    ]),
    'robert-williams': progression(
      'end-of-day',
      [
        { summary: 'EOD cycle started', at: 'August 10, 2026 at 5:04 PM' },
        { summary: 'Due referrals loaded', at: 'August 10, 2026 at 5:04 PM' },
        { summary: 'Sources read', at: 'August 10, 2026 at 5:05 PM' },
        { summary: 'Scheduled Yes · complete blank', at: 'August 10, 2026 at 5:05 PM' },
        { summary: 'Deduped for today', at: 'August 10, 2026 at 5:05 PM' },
        { summary: 'Inconsistency exception opened', at: 'August 10, 2026 at 5:06 PM' },
        { summary: 'Included in evening management digest', at: 'August 10, 2026 at 5:07 PM' },
      ],
      {
        summary: 'Open until complete flag is set',
        status: 'waiting',
        at: 'August 10, 2026 at 5:07 PM',
      },
    ),
  },
  weekly: {
    'gloria-bennett': allDone('weekly', [
      { summary: 'Visit seen recorded', at: 'August 10, 2026 at 6:01 PM' },
    ]),
    'arthur-kim': progression(
      'weekly',
      [
        { summary: 'Weekly cycle started', at: 'August 10, 2026 at 6:00 PM' },
        { summary: 'Active link loaded', at: 'August 10, 2026 at 6:00 PM' },
        { summary: 'Visit status read', at: 'August 10, 2026 at 6:01 PM' },
        { summary: 'Normalized: patient_on_hold', at: 'August 10, 2026 at 6:01 PM' },
        { summary: 'Hold change detected', at: 'August 10, 2026 at 6:02 PM' },
        { summary: 'Not Seen unchanged', at: 'August 10, 2026 at 6:02 PM' },
        { summary: 'Hold tracking required', at: 'August 10, 2026 at 6:02 PM' },
        { summary: 'Hold-tracking exception opened', at: 'August 10, 2026 at 6:03 PM' },
      ],
      { summary: 'Awaiting human follow-up', status: 'waiting' },
    ),
    'margaret-ellis': progression(
      'weekly',
      [
        { summary: 'Weekly cycle started', at: 'August 10, 2026 at 6:00 PM' },
        { summary: 'Active link loaded', at: 'August 10, 2026 at 6:00 PM' },
        { summary: 'Visit status read', at: 'August 10, 2026 at 6:01 PM' },
        { summary: 'Normalized: not_seen', at: 'August 10, 2026 at 6:01 PM' },
        { summary: 'Change detected', at: 'August 10, 2026 at 6:01 PM' },
        { summary: 'Not Seen count incremented to 2', at: 'August 10, 2026 at 6:01 PM' },
      ],
      {
        summary: 'Approach review threshold',
        status: 'current',
        at: 'August 10, 2026 at 6:02 PM',
      },
    ),
    'walter-grant': progression(
      'weekly',
      [
        { summary: 'Weekly cycle started', at: 'August 10, 2026 at 6:00 PM' },
        { summary: 'Active link loaded', at: 'August 10, 2026 at 6:00 PM' },
        { summary: 'Visit status read', at: 'August 10, 2026 at 6:01 PM' },
        { summary: 'Normalized: not_seen', at: 'August 10, 2026 at 6:01 PM' },
        { summary: 'Change detected', at: 'August 10, 2026 at 6:01 PM' },
        { summary: 'Not Seen count incremented to 3', at: 'August 10, 2026 at 6:01 PM' },
        { summary: 'Review required', at: 'August 10, 2026 at 6:02 PM' },
        { summary: 'Not-seen exception opened', at: 'August 10, 2026 at 6:03 PM' },
      ],
      { summary: 'Awaiting review', status: 'waiting' },
    ),
    'dorothy-lane': allDone('weekly', [
      { summary: 'Visit seen · Not Seen reset to 0', at: 'August 9, 2026 at 6:01 PM' },
    ]),
    'helen-park': allDone('weekly', [
      { summary: 'New visit_seen event', at: 'August 9, 2026 at 6:05 PM' },
    ]),
    'patricia-johnson': progression(
      'weekly',
      [
        { summary: 'Weekly cycle started', at: 'August 8, 2026 at 6:00 PM' },
        { summary: 'Active link loaded', at: 'August 8, 2026 at 6:00 PM' },
        { summary: 'Visit status read', at: 'August 8, 2026 at 6:01 PM' },
        { summary: 'Normalized: not_seen', at: 'August 8, 2026 at 6:01 PM' },
        { summary: 'Change detected', at: 'August 8, 2026 at 6:01 PM' },
        { summary: 'Not Seen count = 1', at: 'August 8, 2026 at 6:01 PM' },
      ],
      { summary: 'Monitoring', status: 'current', at: 'August 8, 2026 at 6:01 PM' },
    ),
    'james-carter': allDone('weekly', [
      { summary: 'Visit seen · counter reset', at: 'August 8, 2026 at 6:03 PM' },
    ]),
    'nancy-liu': allDone('weekly', [
      { summary: 'New Seen visit in DRK', at: 'August 10, 2026 at 6:05 PM' },
    ]),
    'linda-nguyen': progression(
      'weekly',
      [
        { summary: 'Weekly cycle started', at: 'August 9, 2026 at 6:06 PM' },
        { summary: 'Active link loaded', at: 'August 9, 2026 at 6:06 PM' },
        { summary: 'Visit status read', at: 'August 9, 2026 at 6:07 PM' },
        { summary: 'Normalized: patient_on_hold', at: 'August 9, 2026 at 6:07 PM' },
        { summary: 'Facility hold detected', at: 'August 9, 2026 at 6:07 PM' },
        { summary: 'Not Seen unchanged', at: 'August 9, 2026 at 6:07 PM' },
        { summary: 'Hold tracking required', at: 'August 9, 2026 at 6:07 PM' },
        { summary: 'Hold exception remains open', at: 'August 9, 2026 at 6:08 PM' },
      ],
      {
        summary: 'Facility hold · monitoring paused',
        status: 'waiting',
        at: 'August 9, 2026 at 6:08 PM',
      },
    ),
  },
}
