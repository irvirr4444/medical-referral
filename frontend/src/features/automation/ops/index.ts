import type { FlowOpsPageId } from '../../../data/flowOps'
import { STAGE_OPS_RECIPES } from './recipes'
import type {
  ActivityFeedMessage,
  OpsEvent,
  PatientStepProgress,
  PatientStepStatus,
  StageOpsFixture,
  StageOpsRecipe,
  StagePatientRef,
  StepFeedDay,
  StepFeedRow,
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
import {
  heroArtifactSections,
  heroPatientIdForStage,
} from './fixtures/heroPatientArtifacts'
import { automationStage } from '../stages'
import { BUTLER_INTAKE_SNAPSHOTS } from '../fixtures/butlerIntakeSnapshots'
import { intakeDemoPatient } from '../fixtures/intakeDemoPatients'
import {
  snapshotToExample,
  type MicrostepExample,
  type MicrostepRunStatus,
} from '../types'
import { humanGateForStep } from './humanGates'
import { actionProgressForStage } from './actionSteps'
import {
  COMBINED_ASSIGNMENT_PAGE_ID,
  isCombinedAssignmentStage,
} from '../combinedAssignment'

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
  if (stageId === COMBINED_ASSIGNMENT_PAGE_ID) {
    return {
      stageId,
      events: [...ASSIGNMENT_OPS_FIXTURE.events, ...HANDOFF_OPS_FIXTURE.events],
    }
  }
  return FIXTURES[stageId]
}

export function openEventsForSection(
  stageId: FlowOpsPageId,
  eventType: string,
): OpsEvent[] {
  return opsFixtureForStage(stageId).events
    .filter((event) => event.eventType === eventType && event.status === 'open')
    .sort(preferButlerThenTime)
}

export function allEventsForSection(
  stageId: FlowOpsPageId,
  eventType: string,
): OpsEvent[] {
  return opsFixtureForStage(stageId).events
    .filter((event) => event.eventType === eventType)
    .sort(preferButlerThenTime)
}

export function patientsForStage(stageId: FlowOpsPageId): StagePatientRef[] {
  const seen = new Map<string, StagePatientRef>()
  for (const event of opsFixtureForStage(stageId).events) {
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
  const heroPatientId = heroPatientIdForStage(stageId)
  if (heroPatientId && patients.some((patient) => patient.patientId === heroPatientId)) {
    return heroPatientId
  }
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

function upcomingFixtureRow(stepId: string): PatientStepProgress {
  return { stepId, status: 'upcoming', summary: 'Not started' }
}

function composeCombinedAssignmentRows(patientId: string): PatientStepProgress[] {
  const assignmentRows = PATIENT_STEP_BREAKDOWNS.assignment[patientId] ?? []
  const handoffRows = PATIENT_STEP_BREAKDOWNS.handoff[patientId] ?? []
  const assignmentGate =
    assignmentRows.find((row) => row.stepId === 'determine-owner') ??
    assignmentRows.find((row) => row.stepId === 'assign-owner')
  const assignOwner: PatientStepProgress = assignmentGate
    ? { ...assignmentGate, stepId: 'assign-owner' }
    : handoffRows.length > 0
      ? {
          stepId: 'assign-owner',
          status: 'done',
          summary: 'Case manager confirmed',
          occurredAt: handoffRows[0]?.occurredAt,
        }
      : upcomingFixtureRow('assign-owner')
  const handoffById = new Map(handoffRows.map((row) => [row.stepId, row]))
  return [
    assignOwner,
    handoffById.get('notify-referral-source') ??
      upcomingFixtureRow('notify-referral-source'),
    handoffById.get('create-monday-record') ??
      upcomingFixtureRow('create-monday-record'),
    handoffById.get('create-update-drk') ??
      upcomingFixtureRow('create-update-drk'),
  ]
}

function fixtureRowsForPatient(
  stageId: FlowOpsPageId,
  patientId: string,
): PatientStepProgress[] {
  if (isCombinedAssignmentStage(stageId)) {
    return composeCombinedAssignmentRows(patientId)
  }
  return PATIENT_STEP_BREAKDOWNS[stageId][patientId] ?? []
}

export function stepsForPatient(
  stageId: FlowOpsPageId,
  patientId: string,
): Array<PatientStepProgress & { stepName: string; description: string }> {
  const stage = automationStage(stageId)
  const fixtureRows = fixtureRowsForPatient(stageId, patientId)
  const rows = actionProgressForStage(
    stageId === 'handoff' ? COMBINED_ASSIGNMENT_PAGE_ID : stageId,
    fixtureRows,
    stage.microsteps.map((step) => step.id),
  )
  return rows.map((row) => {
    const step = stage.microsteps.find((item) => item.id === row.stepId)
    return {
      ...row,
      stepName: step?.name ?? row.stepId,
      description: step?.description ?? '',
    }
  })
}

const DEFAULT_FEED_STATUSES: PatientStepStatus[] = [
  'done',
  'current',
  'waiting',
  'blocked',
]

export function feedForStep(
  stageId: FlowOpsPageId,
  stepId: string,
  filters?: {
    patientQuery?: string
    statuses?: PatientStepStatus[]
  },
): StepFeedDay[] {
  const allowedStatuses: PatientStepStatus[] = (
    filters?.statuses?.length ? filters.statuses : DEFAULT_FEED_STATUSES
  ).filter((status) => status !== 'upcoming')
  const query = filters?.patientQuery?.trim().toLowerCase() ?? ''

  const rows: StepFeedRow[] = []
  for (const patient of patientsForStage(stageId)) {
    if (query && !patient.patientName.toLowerCase().includes(query)) continue
    const progress = stepsForPatient(stageId, patient.patientId).find(
      (row) => row.stepId === stepId,
    )
    if (!progress || !allowedStatuses.includes(progress.status)) continue

    rows.push({
      patientId: patient.patientId,
      patientName: patient.patientName,
      stepId,
      status: progress.status,
      summary: progress.summary,
      occurredAt: progress.occurredAt ?? '',
    })
  }

  rows.sort((a, b) => {
    const aMs = a.occurredAt ? parseOpsDate(a.occurredAt).timeMs : 0
    const bMs = b.occurredAt ? parseOpsDate(b.occurredAt).timeMs : 0
    return bMs - aMs
  })

  const byDay = new Map<string, StepFeedRow[]>()
  for (const row of rows) {
    const key = row.occurredAt ? dayKey(row.occurredAt) : 'undated'
    const list = byDay.get(key) ?? []
    list.push(row)
    byDay.set(key, list)
  }

  return [...byDay.entries()]
    .sort((a, b) => {
      if (a[0] === 'undated') return 1
      if (b[0] === 'undated') return -1
      return a[0] < b[0] ? 1 : -1
    })
    .map(([key, dayRows]) => {
      if (key === 'undated') {
        return {
          key,
          label: 'Undated',
          month: '—',
          day: '—',
          rows: dayRows,
        }
      }
      const parsed = parseOpsDate(dayRows[0].occurredAt)
      return {
        key: parsed.key,
        label: parsed.label,
        month: parsed.month,
        day: parsed.day,
        rows: dayRows,
      }
    })
}

export function detailForPatientStep(
  stageId: FlowOpsPageId,
  patientId: string,
  stepId: string,
  progressOverride?: PatientStepProgress & {
    stepName: string
    description: string
  },
) {
  const stage = automationStage(stageId)
  const microstep = stage.microsteps.find((item) => item.id === stepId)
  const progress = progressOverride ??
    stepsForPatient(stageId, patientId).find((row) => row.stepId === stepId) ??
    null
  const patientName =
    patientsForStage(stageId).find((patient) => patient.patientId === patientId)
      ?.patientName ?? patientId

  if (stageId === 'intake') {
    const demo = intakeDemoPatient(patientId)
    const snapshot = demo?.snapshots[stepId] ?? (
      patientId === 'butler-alva' ? BUTLER_INTAKE_SNAPSHOTS[stepId] : undefined
    )
    const example = snapshot
      ? {
          ...snapshotToExample(snapshot, patientName),
          samplePdf:
            stepId === 'receive-referral' ? demo?.samplePdf : undefined,
        }
      : undefined
    return {
      microstep: microstep ?? null,
      progress,
      snapshot,
      example,
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
  const heroSections = heroArtifactSections(stageId, patientId, progress.stepId)
  const humanGate = humanGateForStep(stageId, progress.stepId)
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
            ? humanGate
              ? 'Awaiting human confirmation'
              : 'Waiting on workflow input'
            : progress.status === 'blocked'
              ? humanGate
                ? 'Blocked pending human decision'
                : 'Blocked by an unresolved workflow condition'
              : 'Confirmed or not required'
    },
    {
      label: 'Next expected',
      value:
        progress.status === 'upcoming'
          ? 'Not reached yet'
          : progress.status === 'waiting' || progress.status === 'blocked'
            ? `${humanGate ? 'After the human decision' : 'After this condition clears'}: ${microstep.next}`
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
    artifactSections:
      heroSections ??
      [
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

export function activityFeedForStage(
  stageId: FlowOpsPageId,
  supplementalEvents: OpsEvent[] = [],
): Array<{
  key: string
  label: string
  month: string
  day: string
  messages: ActivityFeedMessage[]
}> {
  const events = [...opsFixtureForStage(stageId).events, ...supplementalEvents].sort(
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

  for (const event of opsFixtureForStage(stageId).events) {
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
  PatientStepStatus,
  StageOpsFixture,
  StageOpsRecipe,
  StagePatientRef,
  StepFeedDay,
  StepFeedRow,
} from './types'
