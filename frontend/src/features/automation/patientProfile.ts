import type { DemoState, ProviderTerritoryResolution } from '../../types'
import {
  patientDisplayName,
  type CanonicalReferral,
} from './canonicalReferral'
import {
  caseManagerSuggestion,
  drkDraftForPatient,
  drkDraftWithAssignedProvider,
  mondayRecordForPatient,
  mondayRecordWithAssignedProvider,
  referralPatientSummary,
  type DrkDraftRecord,
  type MondayRecord,
} from './fixtures/caseManagerAssignments'
import {
  EOD_ESCALATE_HOURS,
  eodSchedulingCheckForPatient,
  eodSchedulingStatusLabel,
} from './fixtures/eodSchedulingCheck'
import {
  INTAKE_DEMO_PATIENTS,
  intakeDemoPatient,
  referralPdfForPatient,
} from './fixtures/intakeDemoPatients'
import {
  PROVIDER_OPTIONS,
  providerPatientLocationDisplay,
  providerSuggestion,
} from './fixtures/providerAssignments'
import { weeklyVisitCheckForPatient } from './fixtures/weeklyVisitCheck'
import {
  PATIENT_OPS_JOURNEYS,
  STAGE_LABEL,
  STAGE_ORDER,
  patientJourneyById,
  patientsForStage,
  stepsForPatient,
} from './ops'
import { overlayIntakeExample } from './overlayIntakeDetail'
import { statusMeaning } from './StagePatientStepDetail'
import { snapshotToExample, type ArtifactSection } from './types'
import type { FlowOpsPageId } from '../../data/flowOps'
import type { PatientOpsJourney, PatientStepStatus } from './ops/types'
import { givenFamilySlug, nameMatchKey, slugifyPatientKey } from './patientRoute'

const BLANK = '—'

export interface PatientRosterEntry {
  patientId: string
  patientName: string
}

export interface PatientProfile {
  patientId: string
  patientName: string
  dateOfBirth: string
  phone: string
  city: string
  address: string
  currentStageId: FlowOpsPageId
  currentStageLabel: string
  currentStepName: string
  status: PatientStepStatus
  statusLabel: string
  nextAction: string
  owner: string
  blocker: string | null
  caseManager: { name: string; email: string; reason: string }
  providerLabel: string
  providerMeta: string | null
  referralSource: string
  sentBy: string
  mondayOps: {
    referralSent: string
    appointment: string
    scheduled: string
    scheduledComplete: string
    visit: string
    patientContacted: string
    pos: string
  }
  extractedSections: ArtifactSection[]
  samplePdf?: string
  mondayRecord: MondayRecord
  drkDraft: DrkDraftRecord
  timeline: Array<{ occurredAt: string; summary: string }>
}

export function patientRoster(): PatientRosterEntry[] {
  const byId = new Map<string, string>()
  for (const patient of INTAKE_DEMO_PATIENTS) {
    byId.set(patient.patientId, patient.patientName)
  }
  for (const journey of PATIENT_OPS_JOURNEYS) {
    byId.set(journey.patientId, journey.patientName)
  }
  for (const stageId of STAGE_ORDER) {
    for (const patient of patientsForStage(stageId)) {
      if (!byId.has(patient.patientId)) {
        byId.set(patient.patientId, patient.patientName)
      }
    }
  }
  return [...byId.entries()]
    .map(([patientId, patientName]) => ({ patientId, patientName }))
    .sort((a, b) => a.patientName.localeCompare(b.patientName))
}

export function resolvePatientKey(key: string): PatientRosterEntry | null {
  const slug = slugifyPatientKey(decodeURIComponent(key))
  if (!slug) return null
  const roster = patientRoster()
  const match = nameMatchKey(slug)
  return (
    roster.find((patient) => patient.patientId === slug) ??
    roster.find((patient) => slugifyPatientKey(patient.patientName) === slug) ??
    roster.find((patient) => givenFamilySlug(patient.patientName) === slug) ??
    roster.find((patient) => slugifyPatientKey(patient.patientId) === slug) ??
    roster.find(
      (patient) =>
        nameMatchKey(patient.patientId) === match ||
        nameMatchKey(patient.patientName) === match,
    ) ??
    null
  )
}

function stageReached(
  journey: PatientOpsJourney,
  stageId: FlowOpsPageId,
): boolean {
  const stage = journey.stages.find((item) => item.stageId === stageId)
  return Boolean(stage && stage.status !== 'upcoming')
}

function posLabel(place: string | null | undefined): string {
  if (!place) return BLANK
  const upper = place.toUpperCase()
  if (/\bSNF\b/.test(upper) || /skilled nursing/i.test(place)) return 'SNF'
  if (/\bALF\b/.test(upper) || /assisted living/i.test(place)) return 'ALF'
  if (/\bHOME\b/.test(upper) || /\bhome\b/i.test(place)) return 'HOME'
  const short = place.split(/[;(]/)[0]?.trim() ?? ''
  return short.slice(0, 28) || BLANK
}

function cityFromProfile(
  canonical: CanonicalReferral | undefined,
  address: string,
  patientId: string,
): string {
  const canonicalCity = canonical?.patient.address.city
  if (canonicalCity) return canonicalCity
  const location = providerPatientLocationDisplay(patientId)
  if (location !== 'Location unavailable') {
    return location.split(',')[0]?.trim() || location
  }
  const parts = address.split(',').map((part) => part.trim()).filter(Boolean)
  if (parts.length >= 2) return parts[parts.length - 2] ?? address
  return address && address !== 'Not documented' ? address : BLANK
}

export function patientProfile(
  patientId: string,
  state: DemoState,
): PatientProfile | null {
  const roster = patientRoster().find((item) => item.patientId === patientId)
  const demo = intakeDemoPatient(patientId)
  const patientName =
    roster?.patientName ??
    (demo ? patientDisplayName(demo.canonical.patient) : null)
  if (!patientName) return null

  const journey =
    patientJourneyById(patientId, patientName) ??
    patientJourneyById(patientId)
  if (!journey) return null

  const canonical = demo?.canonical
  const summary = referralPatientSummary(patientId, patientName, canonical)
  const caseManager = caseManagerSuggestion(patientId)
  const currentStageId = journey.currentStageId
  const currentStage = journey.stages.find(
    (item) => item.stageId === currentStageId,
  )
  const steps = stepsForPatient(currentStageId, patientId)
  const currentStep =
    steps.find(
      (step) =>
        step.status === 'current' ||
        step.status === 'waiting' ||
        step.status === 'blocked',
    ) ?? steps.find((step) => step.status !== 'done' && step.status !== 'upcoming')
  const status: PatientStepStatus = currentStep?.status ?? 'current'
  const territory = state.providerTerritoryResolutions[patientId]
  const selectedProvider =
    PROVIDER_OPTIONS.find(
      (provider) => provider.id === state.providerSelectedIds[patientId],
    ) ?? null
  const suggestedProvider = providerSuggestion(patientId)
  const eod = eodSchedulingCheckForPatient(
    patientId,
    state.patientSchedules[patientId],
  )
  const weekly = weeklyVisitCheckForPatient(patientId)
  const schedulingHandoff = state.schedulingHandoffs.find(
    (item) => item.patientId === patientId,
  )
  const providerReached = stageReached(journey, 'provider')
  const schedulingReached = stageReached(journey, 'scheduling')
  const eodReached = stageReached(journey, 'end-of-day')
  const weeklyReached = stageReached(journey, 'weekly')

  const assignedProvider =
    territory === 'discharged'
      ? null
      : selectedProvider ??
        (providerReached || eodReached || weeklyReached
          ? {
              id: suggestedProvider.id,
              name: weeklyReached ? weekly.providerName : eodReached ? eod.providerName : suggestedProvider.name,
              npi: suggestedProvider.npi,
              city: suggestedProvider.city,
              phone: suggestedProvider.phone,
              email: suggestedProvider.email,
            }
          : null)

  let mondayRecord = mondayRecordForPatient(patientId, patientName, canonical)
  let drkDraft = drkDraftForPatient(patientId, patientName, canonical)
  if (assignedProvider && (state.providerConfirmed[patientId] || eodReached || weeklyReached)) {
    mondayRecord = mondayRecordWithAssignedProvider(mondayRecord, assignedProvider)
    drkDraft = drkDraftWithAssignedProvider(drkDraft, assignedProvider)
  }

  const extractSnapshot = demo?.snapshots['extract-and-verify']
  const extractExample = extractSnapshot
    ? overlayIntakeExample(
        snapshotToExample(extractSnapshot, patientName),
        state.intakeFieldEdits[patientId],
        state.intakeSectionRows[patientId],
      )
    : undefined
  const extractedSections = (extractExample?.artifactSections ?? [])
    .filter((section) => section.id !== 'gate')
    .map((section) => ({
      ...section,
      defaultExpanded: section.id === 'required-fields',
    }))

  const intakeSteps = stepsForPatient('intake', patientId)
  const contactStep = intakeSteps.find(
    (step) => step.stepId === 'confirm-referral-contacted',
  )
  const patientContacted =
    contactStep?.status === 'done'
      ? 'Yes'
      : contactStep
        ? 'No'
        : BLANK

  const sendStep = stepsForPatient('scheduling', patientId).find(
    (step) => step.stepId === 'send-referral-provider',
  )
  const liveSchedule = state.patientSchedules[patientId]
  const referralSent = !schedulingReached
    ? BLANK
    : sendStep?.status === 'done' ||
        schedulingHandoff ||
        liveSchedule?.referralSent
      ? 'Yes'
      : 'No'

  const scheduleReady = schedulingReached || eodReached || weeklyReached
  const visitReady = weeklyReached

  const missing = [
    ...(extractExample?.feedDecision?.missingLabels ?? []),
    ...(extractExample?.feedDecision?.unclearLabels ?? []),
  ]
  const blocker = profileBlocker({
    territory,
    stageStatus: currentStage?.status,
    headline: currentStage?.headline,
    stepStatus: currentStep?.status,
    stepSummary: currentStep?.summary,
    missing,
    eodReached,
    eodOverdue: eod.overdue && eod.hoursSinceProviderSelected >= EOD_ESCALATE_HOURS,
    weeklyReached,
    consecutiveNotSeen: weekly.consecutiveNotSeen,
  })

  const owner =
    territory === 'discharged'
      ? 'Nicole Chorvat'
      : currentStageId === 'intake'
        ? 'Intake'
        : caseManager.name

  const providerLabel =
    territory === 'discharged'
      ? 'Discharged · no provider'
      : assignedProvider
        ? assignedProvider.name
        : 'Not selected'
  const providerMeta = assignedProvider
    ? [assignedProvider.city, assignedProvider.npi ? `NPI ${assignedProvider.npi}` : null]
        .filter(Boolean)
        .join(' · ') || null
    : null

  const timeline = journey.stages.flatMap((stage) =>
    stage.outcomes.map((outcome) => ({
      occurredAt: outcome.occurredAt,
      summary: outcome.summary,
    })),
  )

  return {
    patientId,
    patientName,
    dateOfBirth: summary.dateOfBirth,
    phone: summary.phone,
    city: cityFromProfile(canonical, summary.location, patientId),
    address: summary.location,
    currentStageId,
    currentStageLabel: STAGE_LABEL[currentStageId],
    currentStepName: currentStep?.stepName ?? currentStage?.headline ?? 'In progress',
    status,
    statusLabel: statusMeaning(status),
    nextAction: currentStep?.stepName ?? currentStage?.headline ?? 'Continue',
    owner,
    blocker,
    caseManager,
    providerLabel,
    providerMeta,
    referralSource:
      canonical?.referral_source.organization.name ??
      mondayRecord.data.home_health_or_hospice_agency,
    sentBy: mondayRecord.data.sent_by,
    mondayOps: {
      referralSent,
      appointment: scheduleReady && eod.appointmentDate ? eod.appointmentDate : BLANK,
      scheduled: scheduleReady ? eodSchedulingStatusLabel(eod) : BLANK,
      scheduledComplete: scheduleReady ? eod.scheduledComplete || 'No' : BLANK,
      visit: visitReady ? weekly.visitStatusLabel : BLANK,
      patientContacted,
      pos: posLabel(canonical?.admission.place_of_service),
    },
    extractedSections,
    samplePdf: referralPdfForPatient(patientId),
    mondayRecord,
    drkDraft,
    timeline,
  }
}

function profileBlocker({
  territory,
  stageStatus,
  headline,
  stepStatus,
  stepSummary,
  missing,
  eodReached,
  eodOverdue,
  weeklyReached,
  consecutiveNotSeen,
}: {
  territory?: ProviderTerritoryResolution
  stageStatus?: PatientOpsJourney['stages'][number]['status']
  headline?: string
  stepStatus?: PatientStepStatus
  stepSummary?: string
  missing: string[]
  eodReached: boolean
  eodOverdue: boolean
  weeklyReached: boolean
  consecutiveNotSeen: number
}): string | null {
  if (territory === 'discharged') return 'No eligible provider · discharged'
  if (stageStatus === 'blocked' && headline) return headline
  if (stepStatus === 'blocked' && stepSummary) return stepSummary
  if (missing.length) return missing.join(' · ')
  if (eodReached && eodOverdue) return 'Not scheduled after 48h'
  if (weeklyReached && consecutiveNotSeen >= 3) {
    return 'Three consecutive not-seen visits'
  }
  return null
}
