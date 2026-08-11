import type { FlowOpsPageId } from '../../../data/flowOps'
import { STAGE_OPS_RECIPES } from './recipes'
import type {
  ActivityFeedMessage,
  OpsEvent,
  PatientStepProgress,
  StageOpsFixture,
  StageOpsRecipe,
  StagePatientRef,
} from './types'
import { INTAKE_OPS_FIXTURE } from './fixtures/intake'
import { HANDOFF_OPS_FIXTURE } from './fixtures/handoff'
import { ASSIGNMENT_OPS_FIXTURE } from './fixtures/assignment'
import { PROVIDER_OPS_FIXTURE } from './fixtures/provider'
import { SCHEDULING_OPS_FIXTURE } from './fixtures/scheduling'
import { END_OF_DAY_OPS_FIXTURE } from './fixtures/endOfDay'
import { WEEKLY_OPS_FIXTURE } from './fixtures/weekly'
import {
  patientJourneyById,
  PATIENT_OPS_JOURNEYS,
  STAGE_LABEL,
  STAGE_ORDER,
} from './fixtures/patientJourneys'
import { PATIENT_STEP_BREAKDOWNS } from './fixtures/patientSteps'
import { automationStage } from '../stages'
import { BUTLER_INTAKE_SNAPSHOTS } from '../fixtures/butlerIntakeSnapshots'
import {
  snapshotToExample,
  type MicrostepExample,
  type MicrostepRunStatus,
} from '../types'

const FIXTURES: Record<FlowOpsPageId, StageOpsFixture> = {
  intake: INTAKE_OPS_FIXTURE,
  handoff: HANDOFF_OPS_FIXTURE,
  assignment: ASSIGNMENT_OPS_FIXTURE,
  provider: PROVIDER_OPS_FIXTURE,
  scheduling: SCHEDULING_OPS_FIXTURE,
  'end-of-day': END_OF_DAY_OPS_FIXTURE,
  weekly: WEEKLY_OPS_FIXTURE,
}

export function opsRecipeForStage(stageId: FlowOpsPageId): StageOpsRecipe {
  return STAGE_OPS_RECIPES[stageId]
}

export function opsFixtureForStage(stageId: FlowOpsPageId): StageOpsFixture {
  return FIXTURES[stageId]
}

export function openEventsForSection(
  stageId: FlowOpsPageId,
  eventType: string,
): OpsEvent[] {
  return FIXTURES[stageId].events
    .filter((event) => event.eventType === eventType && event.status === 'open')
    .sort(preferButlerThenTime)
}

export function allEventsForSection(
  stageId: FlowOpsPageId,
  eventType: string,
): OpsEvent[] {
  return FIXTURES[stageId].events
    .filter((event) => event.eventType === eventType)
    .sort(preferButlerThenTime)
}

export function patientsForStage(stageId: FlowOpsPageId): StagePatientRef[] {
  const seen = new Map<string, StagePatientRef>()
  for (const event of FIXTURES[stageId].events) {
    if (!seen.has(event.patientId)) {
      seen.set(event.patientId, {
        patientId: event.patientId,
        patientName: event.patientName,
      })
    }
  }
  const patients = [...seen.values()]
  patients.sort((a, b) => {
    if (a.patientId === 'butler-alva') return -1
    if (b.patientId === 'butler-alva') return 1
    return a.patientName.localeCompare(b.patientName)
  })
  return patients
}

export function defaultPatientIdForStage(stageId: FlowOpsPageId): string {
  const patients = patientsForStage(stageId)
  if (stageId === 'intake') {
    return (
      patients.find((patient) => patient.patientId === 'butler-alva')
        ?.patientId ??
      patients[0]?.patientId ??
      ''
    )
  }
  return patients[0]?.patientId ?? ''
}

export function stepsForPatient(
  stageId: FlowOpsPageId,
  patientId: string,
): Array<PatientStepProgress & { stepName: string; description: string }> {
  const stage = automationStage(stageId)
  const rows = PATIENT_STEP_BREAKDOWNS[stageId][patientId] ?? []
  return rows.map((row) => {
    const step = stage.microsteps.find((item) => item.id === row.stepId)
    return {
      ...row,
      stepName: step?.name ?? row.stepId,
      description: step?.description ?? '',
    }
  })
}

export function detailForPatientStep(
  stageId: FlowOpsPageId,
  patientId: string,
  stepId: string,
) {
  const stage = automationStage(stageId)
  const microstep = stage.microsteps.find((item) => item.id === stepId)
  const progress =
    stepsForPatient(stageId, patientId).find((row) => row.stepId === stepId) ??
    null
  const patientName =
    patientsForStage(stageId).find((patient) => patient.patientId === patientId)
      ?.patientName ?? patientId

  if (stageId === 'intake' && patientId === 'butler-alva') {
    const snapshot = BUTLER_INTAKE_SNAPSHOTS[stepId]
    return {
      microstep: microstep ?? null,
      progress,
      snapshot,
      example: snapshot ? snapshotToExample(snapshot, patientName) : undefined,
    }
  }

  const example =
    microstep && progress
      ? synthesizeStepExample({
          stageId,
          patientId,
          patientName,
          microstep,
          progress,
        })
      : undefined

  return {
    microstep: microstep ?? null,
    progress,
    snapshot: undefined,
    example,
  }
}

function synthesizeStepExample({
  stageId,
  patientId,
  patientName,
  microstep,
  progress,
}: {
  stageId: FlowOpsPageId
  patientId: string
  patientName: string
  microstep: NonNullable<ReturnType<typeof automationStage>['microsteps'][number]>
  progress: PatientStepProgress & { stepName: string; description: string }
}): MicrostepExample {
  const facts = progress.detail
  const runStatus = toRunStatus(progress.status)
  const knownAtThisPoint = facts?.knownAtThisPoint ?? [
    { label: 'Patient', value: patientName },
    { label: 'Stage', value: STAGE_LABEL[stageId] },
    { label: 'Step status', value: progressStatusLabel(progress.status) },
    ...(progress.occurredAt
      ? [{ label: 'Recorded', value: progress.occurredAt }]
      : []),
  ]

  const fields = facts?.fields ?? [
    { label: 'Outcome summary', value: progress.summary },
    { label: 'System', value: microstep.system },
    {
      label: 'Confirmation state',
      value:
        progress.status === 'upcoming'
          ? 'Not in scope yet'
          : progress.status === 'waiting'
            ? 'Awaiting confirmation'
            : progress.status === 'blocked'
              ? 'Blocked pending confirmation'
              : 'Confirmed or not required'
    },
    {
      label: 'Next expected',
      value:
        progress.status === 'upcoming'
          ? 'Not reached yet'
          : progress.status === 'waiting' || progress.status === 'blocked'
            ? `After confirmation: ${microstep.next}`
            : microstep.next,
    },
    {
      label: 'Implementation',
      value:
        microstep.implementationStatus === 'working'
          ? 'Live automation'
          : microstep.implementationStatus === 'partial'
            ? 'Assisted automation'
            : 'Planned automation',
    },
  ]

  return {
    status: runStatus,
    duration:
      facts?.duration ??
      (progress.status === 'upcoming'
        ? 'Not started'
        : progress.status === 'waiting'
          ? 'Awaiting confirmation'
          : progress.status === 'blocked'
            ? 'Blocked pending confirmation'
            : 'Under 2 seconds'),
    validation:
      facts?.validation ??
      microstep.example.validation ??
      'Outcome matches the stage gate for this patient.',
    patientName,
    executedAt: progress.occurredAt,
    artifactTitle: facts?.artifactTitle ?? `${microstep.name} · ${patientName}`,
    executionId: `${patientId}-${progress.stepId}`,
    artifactId: `${patientId}-${progress.stepId}-artifact`,
    knownAtThisPoint,
    artifactSections: [
      {
        id: 'outcome',
        title:
          progress.status === 'upcoming'
            ? 'Queued for this patient'
            : 'What happened for this patient',
        defaultExpanded: true,
        fields,
      },
    ],
    inputs: [
      {
        label: 'Patient context',
        value: `${patientName} · ${STAGE_LABEL[stageId]}`,
      },
    ],
    outputs: [{ label: 'Result', value: progress.summary }],
  }
}

function toRunStatus(status: PatientStepProgress['status']): MicrostepRunStatus {
  switch (status) {
    case 'done':
      return 'completed'
    case 'blocked':
      return 'attention'
    case 'waiting':
    case 'current':
      return 'waiting'
    default:
      return 'planned'
  }
}

function progressStatusLabel(status: PatientStepProgress['status']) {
  switch (status) {
    case 'done':
      return 'Completed'
    case 'current':
      return 'In progress'
    case 'waiting':
      return 'Awaiting confirmation'
    case 'blocked':
      return 'Blocked pending confirmation'
    default:
      return 'Upcoming'
  }
}

export function activityFeedForStage(stageId: FlowOpsPageId): Array<{
  key: string
  label: string
  month: string
  day: string
  messages: ActivityFeedMessage[]
}> {
  const events = [...FIXTURES[stageId].events].sort(
    (a, b) =>
      parseOpsDate(b.occurredAt).timeMs - parseOpsDate(a.occurredAt).timeMs,
  )
  const byDay = new Map<string, OpsEvent[]>()
  for (const event of events) {
    const key = dayKey(event.occurredAt)
    const list = byDay.get(key) ?? []
    list.push(event)
    byDay.set(key, list)
  }

  return [...byDay.entries()]
    .sort((a, b) => (a[0] < b[0] ? 1 : -1))
    .map(([, dayEvents]) => {
      const parsed = parseOpsDate(dayEvents[0].occurredAt)
      return {
        key: parsed.key,
        label: parsed.label,
        month: parsed.month,
        day: parsed.day,
        messages: dayEvents
          .sort(
            (a, b) =>
              parseOpsDate(b.occurredAt).timeMs -
              parseOpsDate(a.occurredAt).timeMs,
          )
          .map((event) => ({
            id: event.id,
            patientId: event.patientId,
            patientName: event.patientName,
            occurredAt: event.occurredAt,
            summary: event.summary,
            eventType: event.eventType,
            status: event.status,
          })),
      }
    })
}

export function historyDaysForStage(stageId: FlowOpsPageId): Array<{
  key: string
  label: string
  month: string
  day: string
  sections: Array<{ eventType: string; label: string; events: OpsEvent[] }>
}> {
  const recipe = STAGE_OPS_RECIPES[stageId]
  const byDay = new Map<string, OpsEvent[]>()

  for (const event of FIXTURES[stageId].events) {
    const key = dayKey(event.occurredAt)
    const list = byDay.get(key) ?? []
    list.push(event)
    byDay.set(key, list)
  }

  return [...byDay.entries()]
    .sort((a, b) => (a[0] < b[0] ? 1 : -1))
    .map(([key, events]) => {
      const sample = events[0]
      const parsed = parseOpsDate(sample.occurredAt)
      const sections = recipe.sections
        .map((section) => ({
          eventType: section.id,
          label: section.label,
          events: events
            .filter((event) => event.eventType === section.id)
            .sort(preferButlerThenTime),
        }))
        .filter((section) => section.events.length > 0)

      return {
        key,
        label: parsed.label,
        month: parsed.month,
        day: parsed.day,
        sections,
      }
    })
}

function preferButlerThenTime(a: OpsEvent, b: OpsEvent) {
  if (a.patientId === 'butler-alva' && b.patientId !== 'butler-alva') return -1
  if (b.patientId === 'butler-alva' && a.patientId !== 'butler-alva') return 1
  return parseOpsDate(b.occurredAt).timeMs - parseOpsDate(a.occurredAt).timeMs
}

export function parseOpsDate(value: string) {
  const parsed = new Date(value.replace(' at ', ' '))
  if (Number.isNaN(parsed.getTime())) {
    return {
      label: value,
      month: 'DATE',
      day: '--',
      time: value,
      timeMs: 0,
      key: value,
    }
  }
  return {
    label: new Intl.DateTimeFormat('en-US', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }).format(parsed),
    month: new Intl.DateTimeFormat('en-US', { month: 'short' })
      .format(parsed)
      .toUpperCase(),
    day: String(parsed.getDate()).padStart(2, '0'),
    time: new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    }).format(parsed),
    timeMs: parsed.getTime(),
    key: parsed.toISOString().slice(0, 10),
  }
}

function dayKey(value: string) {
  return parseOpsDate(value).key
}

export function defaultNowSectionId(stageId: FlowOpsPageId): string {
  const recipe = STAGE_OPS_RECIPES[stageId]
  const withOpen = recipe.sections.find(
    (section) =>
      section.openByDefault &&
      openEventsForSection(stageId, section.id).length > 0,
  )
  if (withOpen) return withOpen.id
  const anyOpen = recipe.sections.find(
    (section) => openEventsForSection(stageId, section.id).length > 0,
  )
  return anyOpen?.id ?? recipe.sections[0].id
}

export {
  patientJourneyById,
  PATIENT_OPS_JOURNEYS,
  STAGE_LABEL,
  STAGE_ORDER,
  STAGE_OPS_RECIPES,
}

export type {
  ActivityFeedMessage,
  OpsEvent,
  PatientOpsJourney,
  PatientStepProgress,
  StageOpsFixture,
  StageOpsRecipe,
  StagePatientRef,
} from './types'
