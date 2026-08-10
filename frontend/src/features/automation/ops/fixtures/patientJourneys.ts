import type { FlowOpsPageId } from '../../../../data/flowOps'
import type { PatientOpsJourney, PatientStageOutcome } from '../types'
import { PATIENT_STEP_BREAKDOWNS } from './patientSteps'

const STAGE_ORDER: FlowOpsPageId[] = [
  'intake',
  'handoff',
  'assignment',
  'provider',
  'scheduling',
  'end-of-day',
  'weekly',
]

const STAGE_LABEL: Record<FlowOpsPageId, string> = {
  intake: 'Referral intake',
  handoff: 'Handoff',
  assignment: 'Assignment',
  provider: 'Provider selection',
  scheduling: 'Scheduling',
  'end-of-day': 'End-of-day check',
  weekly: 'Weekly visit cycle',
}

export { STAGE_ORDER, STAGE_LABEL }

function upcoming(stageId: FlowOpsPageId, headline = 'Not started'): PatientStageOutcome {
  return { stageId, status: 'upcoming', headline, outcomes: [] }
}

export const PATIENT_OPS_JOURNEYS: PatientOpsJourney[] = [
  {
    patientId: 'butler-alva',
    patientName: 'Butler, Alva',
    context: 'Chart export PDF · missing home-health agency',
    currentStageId: 'intake',
    stages: [
      {
        stageId: 'intake',
        status: 'current',
        headline: 'Awaiting approval · agency missing',
        outcomes: [
          { occurredAt: 'August 10, 2026 at 9:14 AM', summary: 'Email arrived with BUTLER, ALVA demo.pdf' },
          { occurredAt: 'August 10, 2026 at 9:17 AM', summary: 'Extracted · 6 of 7 fields complete · agency missing' },
          { occurredAt: 'August 10, 2026 at 9:18 AM', summary: 'Review sent · Monday/DRK blocked' },
        ],
      },
      {
        stageId: 'handoff',
        status: 'blocked',
        headline: 'Blocked until intake approval and agency',
        outcomes: [],
      },
      upcoming('assignment', 'Waiting on handoff'),
      upcoming('provider', 'Waiting on assignment'),
      upcoming('scheduling', 'Waiting on provider'),
      upcoming('end-of-day', 'Waiting on scheduling'),
      upcoming('weekly', 'Waiting on active care'),
    ],
  },
  {
    patientId: 'maria-alvarez',
    patientName: 'Maria Alvarez',
    context: 'Provider confirmed · awaiting scheduling reply',
    currentStageId: 'scheduling',
    stages: [
      {
        stageId: 'intake',
        status: 'done',
        headline: 'Approved · destination authorized',
        outcomes: [
          { occurredAt: 'August 8, 2026 at 9:12 AM', summary: 'Referral extracted and approved' },
        ],
      },
      {
        stageId: 'handoff',
        status: 'done',
        headline: 'Monday created · DRK pending assisted entry',
        outcomes: [
          { occurredAt: 'August 10, 2026 at 10:07 AM', summary: 'Master Sheet item created' },
          { occurredAt: 'August 10, 2026 at 10:09 AM', summary: 'DRK draft ready' },
        ],
      },
      {
        stageId: 'assignment',
        status: 'done',
        headline: 'Territory matched · Ana suggested',
        outcomes: [
          { occurredAt: 'August 10, 2026 at 10:16 AM', summary: 'Riverside territory · Ana' },
        ],
      },
      {
        stageId: 'provider',
        status: 'done',
        headline: 'Shortlist ready',
        outcomes: [
          { occurredAt: 'August 10, 2026 at 10:21 AM', summary: '5 providers ranked for Riverside' },
        ],
      },
      {
        stageId: 'scheduling',
        status: 'current',
        headline: 'Windows proposed · awaiting Ana',
        outcomes: [
          { occurredAt: 'August 10, 2026 at 10:06 AM', summary: 'Fri 11:00 AM · Sat 8:40 AM proposed' },
          { occurredAt: 'August 10, 2026 at 10:07 AM', summary: 'Options sent · no reply yet' },
        ],
      },
      upcoming('end-of-day', 'After appointment is written'),
      upcoming('weekly', 'After first visit window'),
    ],
  },
  {
    patientId: 'patricia-johnson',
    patientName: 'Patricia Johnson',
    context: 'Appointment written · in active care',
    currentStageId: 'weekly',
    stages: [
      {
        stageId: 'intake',
        status: 'done',
        headline: 'Approved Aug 9',
        outcomes: [{ occurredAt: 'August 9, 2026 at 11:02 AM', summary: 'Approved and authorized for handoff' }],
      },
      {
        stageId: 'handoff',
        status: 'done',
        headline: 'Monday and DRK linked',
        outcomes: [{ occurredAt: 'August 9, 2026 at 11:20 AM', summary: 'Handoff verified' }],
      },
      {
        stageId: 'assignment',
        status: 'done',
        headline: 'Cole assigned',
        outcomes: [{ occurredAt: 'August 9, 2026 at 12:21 PM', summary: 'Owner written' }],
      },
      {
        stageId: 'provider',
        status: 'done',
        headline: 'Dr. Nguyen confirmed',
        outcomes: [{ occurredAt: 'August 9, 2026 at 1:06 PM', summary: 'Provider written' }],
      },
      {
        stageId: 'scheduling',
        status: 'done',
        headline: 'Fri 11:00 AM written',
        outcomes: [{ occurredAt: 'August 9, 2026 at 3:19 PM', summary: 'Appointment written to Monday and DRK' }],
      },
      {
        stageId: 'end-of-day',
        status: 'done',
        headline: 'Scheduling fields consistent',
        outcomes: [{ occurredAt: 'August 9, 2026 at 5:01 PM', summary: 'No exception required' }],
      },
      {
        stageId: 'weekly',
        status: 'current',
        headline: 'Not Seen count = 1',
        outcomes: [{ occurredAt: 'August 8, 2026 at 6:01 PM', summary: 'First weekly check · not seen once' }],
      },
    ],
  },
  {
    patientId: 'thomas-reed',
    patientName: 'Thomas Reed',
    context: 'Scheduling windows awaiting reply',
    currentStageId: 'scheduling',
    stages: [
      {
        stageId: 'intake',
        status: 'done',
        headline: 'Approved today',
        outcomes: [{ occurredAt: 'August 10, 2026 at 2:40 PM', summary: 'Destination preparation authorized' }],
      },
      {
        stageId: 'handoff',
        status: 'done',
        headline: 'Handoff verified',
        outcomes: [{ occurredAt: 'August 10, 2026 at 2:54 PM', summary: 'Monday and DRK linked' }],
      },
      {
        stageId: 'assignment',
        status: 'done',
        headline: 'Ana assigned',
        outcomes: [{ occurredAt: 'August 10, 2026 at 3:16 PM', summary: 'Assignment written' }],
      },
      {
        stageId: 'provider',
        status: 'done',
        headline: 'Dr. Patel confirmed',
        outcomes: [{ occurredAt: 'August 10, 2026 at 3:41 PM', summary: 'Provider written' }],
      },
      {
        stageId: 'scheduling',
        status: 'current',
        headline: 'Awaiting Ana response',
        outcomes: [
          { occurredAt: 'August 10, 2026 at 3:46 PM', summary: 'Three windows proposed' },
          { occurredAt: 'August 10, 2026 at 3:47 PM', summary: 'Options sent' },
        ],
      },
      upcoming('end-of-day'),
      upcoming('weekly'),
    ],
  },
]

const FALLBACK_JOURNEY_CACHE = new Map<string, PatientOpsJourney>()

function inferCurrentStageId(patientId: string): FlowOpsPageId {
  for (const stageId of STAGE_ORDER) {
    const steps = PATIENT_STEP_BREAKDOWNS[stageId]?.[patientId]
    if (!steps) continue
    if (
      steps.some(
        (step) =>
          step.status === 'current' ||
          step.status === 'waiting' ||
          step.status === 'blocked',
      )
    ) {
      return stageId
    }
  }

  for (const stageId of [...STAGE_ORDER].reverse()) {
    if (PATIENT_STEP_BREAKDOWNS[stageId]?.[patientId]) return stageId
  }

  return 'intake'
}

/** Build a thin spine for patients that appear in stage fixtures but lack a hero journey. */
export function patientJourneyById(
  patientId: string,
  patientName?: string,
): PatientOpsJourney | null {
  const known = PATIENT_OPS_JOURNEYS.find((item) => item.patientId === patientId)
  if (known) return known

  if (!patientName) return null
  const cached = FALLBACK_JOURNEY_CACHE.get(patientId)
  if (cached) return cached

  const currentStageId = inferCurrentStageId(patientId)
  const fallback: PatientOpsJourney = {
    patientId,
    patientName,
    context: 'Live operations fixture',
    currentStageId,
    stages: STAGE_ORDER.map((stageId) => {
      const steps = PATIENT_STEP_BREAKDOWNS[stageId]?.[patientId]
      if (!steps) {
        const order = STAGE_ORDER.indexOf(stageId)
        const currentOrder = STAGE_ORDER.indexOf(currentStageId)
        return {
          stageId,
          status: order < currentOrder ? 'done' : 'upcoming',
          headline:
            order < currentOrder
              ? 'Completed earlier in the path'
              : 'Not started',
          outcomes: [],
        } satisfies PatientStageOutcome
      }

      const active = steps.find(
        (step) =>
          step.status === 'current' ||
          step.status === 'waiting' ||
          step.status === 'blocked',
      )
      const allComplete = steps.every((step) => step.status === 'done')
      const status = allComplete
        ? 'done'
        : active
          ? active.status === 'blocked'
            ? 'blocked'
            : 'current'
          : stageId === currentStageId
            ? 'current'
            : 'upcoming'

      return {
        stageId,
        status,
        headline: active?.summary ?? (allComplete ? 'Stage complete' : 'In progress'),
        outcomes: steps
          .filter((step) => step.occurredAt && step.status !== 'upcoming')
          .slice(-2)
          .map((step) => ({
            occurredAt: step.occurredAt!,
            summary: step.summary,
          })),
      } satisfies PatientStageOutcome
    }),
  }
  FALLBACK_JOURNEY_CACHE.set(patientId, fallback)
  return fallback
}
