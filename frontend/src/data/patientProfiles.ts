import {
  patientAddressLine,
  patientDisplayName,
  type CanonicalReferral,
} from '../features/automation/canonicalReferral'
import butlerCanonicalReferral from '../features/automation/fixtures/butlerCanonicalReferral.json'
import { AUTOMATION_STAGES } from '../features/automation/stages'
import type { FlowOpsPageId } from './flowOps'

export const BUTLER_PROFILE_ID = 'butler-alva'

export type ProfileDataSource =
  | 'canonical_referral'
  | 'drk'
  | 'monday'
  | 'outlook'
  | 'automation'
  | 'unavailable'

export interface ProfileFieldProvenance {
  source: ProfileDataSource
  label: string
  lastUpdated?: string | null
}

export interface PatientProfileIdentity {
  displayName: string
  legalName: string
  dateOfBirth: string | null
  age: number | null
  sexOrGender: string | null
  phone: string | null
  email: string | null
  address: string | null
  sourcePatientId: string | null
  sourcePatientIdLabel: string | null
  mrn: string | null
}

export interface PatientProfileReferralSource {
  providerName: string | null
  organizationName: string | null
  phone: string | null
  referralOrOrderDate: string | null
  documentType: string | null
  fileName: string | null
  pageCount: number | null
}

export interface PatientProfileDiagnosis {
  code: string | null
  description: string | null
  isPrimary: boolean
  status: string | null
}

export interface PatientProfileInsurance {
  payerName: string | null
  policyNumber: string | null
  groupNumber: string | null
  insuranceType: string | null
}

export interface PatientProfileRequestedService {
  service: string | null
  frequency: string | null
  instructions: string | null
}

export interface PatientProfileFieldQuality {
  path: string
  label: string
  status: string
  confidence: string
}

export interface PatientProfileSectionAvailability {
  available: boolean
  reason?: string
}

export interface PatientPlatformRecord {
  present: boolean
  recordId: string | null
  label: string
}

export interface PatientWorkflowStageProgress {
  stageId: string
  stageTitle: string
  shortTitle: string
  status: 'completed' | 'current' | 'upcoming'
  stepCount: number
  currentStepId: string | null
  currentStepName: string | null
  currentStepNumber: number | null
}

export interface PatientWorkflowStatus {
  summary: string
  currentStageId: string
  currentStageTitle: string
  currentStepId: string
  currentStepName: string
  currentStepNumber: number
  currentStepCount: number
  monday: PatientPlatformRecord
  drk: PatientPlatformRecord
  stages: PatientWorkflowStageProgress[]
}

export interface PatientProfileViewModel {
  profileId: string
  referralId: string
  identity: PatientProfileIdentity
  referralSource: PatientProfileReferralSource
  clinicalSummary: string | null
  clinicalNotes: string[]
  diagnoses: PatientProfileDiagnosis[]
  insurances: PatientProfileInsurance[]
  requestedServices: PatientProfileRequestedService[]
  warnings: string[]
  fieldQuality: PatientProfileFieldQuality[]
  workflow: PatientWorkflowStatus | null
  provenance: {
    identity: ProfileFieldProvenance
    referral: ProfileFieldProvenance
    clinical: ProfileFieldProvenance
    insurance: ProfileFieldProvenance
  }
  unavailableSections: {
    careTeam: PatientProfileSectionAvailability
    appointment: PatientProfileSectionAvailability
    recentActivity: PatientProfileSectionAvailability
  }
}

const FIELD_QUALITY_LABELS: Record<string, string> = {
  'patient.name': 'Patient name',
  'patient.date_of_birth': 'Date of birth',
  'patient.phones': 'Contact number',
  'patient.address': 'Patient address',
  home_health_or_hospice: 'Home health or hospice agency',
  clinical: 'Clinical information',
  insurances: 'Insurance information',
}

function formatDisplayDob(isoDate: string | null): string | null {
  if (!isoDate) return null
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate)
  if (!match) return isoDate
  const [, year, month, day] = match
  return `${month}/${day}/${year}`
}

function friendlyDisplayName(record: CanonicalReferral): string {
  const { first, last } = record.patient.name
  if (first && last) return `${first} ${last}`
  return patientDisplayName(record.patient)
}

function buildWorkflowStatus({
  currentStageId,
  currentStepId,
  summary,
  monday,
  drk,
}: {
  currentStageId: FlowOpsPageId
  currentStepId: string
  summary: string
  monday: PatientPlatformRecord
  drk: PatientPlatformRecord
}): PatientWorkflowStatus {
  const currentStageIndex = AUTOMATION_STAGES.findIndex(
    (stage) => stage.id === currentStageId,
  )
  if (currentStageIndex < 0) {
    throw new Error(`Unknown automation stage: ${currentStageId}`)
  }

  const currentStage = AUTOMATION_STAGES[currentStageIndex]
  const currentStepIndex = currentStage.microsteps.findIndex(
    (step) => step.id === currentStepId,
  )
  if (currentStepIndex < 0) {
    throw new Error(`Unknown step ${currentStepId} in stage ${currentStageId}`)
  }

  const currentStep = currentStage.microsteps[currentStepIndex]

  return {
    summary,
    currentStageId: currentStage.id,
    currentStageTitle: currentStage.title,
    currentStepId: currentStep.id,
    currentStepName: currentStep.name,
    currentStepNumber: currentStepIndex + 1,
    currentStepCount: currentStage.microsteps.length,
    monday,
    drk,
    stages: AUTOMATION_STAGES.map((stage, index) => {
      const isCurrent = index === currentStageIndex
      return {
        stageId: stage.id,
        stageTitle: stage.title,
        shortTitle: stage.shortTitle,
        status:
          index < currentStageIndex
            ? 'completed'
            : isCurrent
              ? 'current'
              : 'upcoming',
        stepCount: stage.microsteps.length,
        currentStepId: isCurrent ? currentStep.id : null,
        currentStepName: isCurrent ? currentStep.name : null,
        currentStepNumber: isCurrent ? currentStepIndex + 1 : null,
      }
    }),
  }
}

const BUTLER_WORKFLOW = buildWorkflowStatus({
  currentStageId: 'intake',
  currentStepId: 'interpret-reply',
  summary:
    'Awaiting reviewer approval before Monday.com and DRK destination actions can proceed.',
  monday: {
    present: false,
    recordId: null,
    label: 'Not in Monday.com yet',
  },
  drk: {
    present: false,
    recordId: null,
    label: 'Not in DRK yet',
  },
})

export function mapCanonicalReferralToProfile(
  profileId: string,
  record: CanonicalReferral,
  workflow: PatientWorkflowStatus | null = null,
): PatientProfileViewModel {
  const provenance: ProfileFieldProvenance = {
    source: 'canonical_referral',
    label: 'Canonical referral',
    lastUpdated: null,
  }

  return {
    profileId,
    referralId: record.referral_id,
    identity: {
      displayName: friendlyDisplayName(record),
      legalName: patientDisplayName(record.patient),
      dateOfBirth: formatDisplayDob(record.patient.date_of_birth),
      age: record.patient.age,
      sexOrGender: record.patient.sex_or_gender,
      phone: record.patient.phones[0]?.number ?? null,
      email: record.patient.email,
      address: patientAddressLine(record.patient) || null,
      sourcePatientId: record.patient.source_patient_id,
      sourcePatientIdLabel: record.patient.source_patient_id_label,
      mrn: record.patient.mrn,
    },
    referralSource: {
      providerName: record.referral_source.provider_name,
      organizationName: record.referral_source.organization.name,
      phone: record.referral_source.organization.phone,
      referralOrOrderDate: record.referral_source.referral_or_order_date,
      documentType: record.document_type,
      fileName: record.source.file_name,
      pageCount: record.source.page_count,
    },
    clinicalSummary: record.clinical.summary,
    clinicalNotes: record.clinical.notes,
    diagnoses: record.clinical.diagnoses.map((diagnosis) => ({
      code: diagnosis.code,
      description: diagnosis.description,
      isPrimary: Boolean(diagnosis.is_primary),
      status: diagnosis.status,
    })),
    insurances: record.insurances.map((insurance) => ({
      payerName: insurance.payer_name,
      policyNumber: insurance.policy_number,
      groupNumber: insurance.group_number,
      insuranceType: insurance.insurance_type,
    })),
    requestedServices: (
      record.requested_services as Array<{
        service?: string | null
        frequency?: string | null
        instructions?: string | null
      }>
    ).map((service) => ({
      service: service.service ?? null,
      frequency: service.frequency ?? null,
      instructions: service.instructions ?? null,
    })),
    warnings: record.warnings,
    fieldQuality: Object.entries(record.field_quality).map(([path, quality]) => ({
      path,
      label: FIELD_QUALITY_LABELS[path] ?? path,
      status: quality.status,
      confidence: quality.confidence,
    })),
    workflow,
    provenance: {
      identity: provenance,
      referral: provenance,
      clinical: provenance,
      insurance: provenance,
    },
    unavailableSections: {
      careTeam: {
        available: false,
        reason: 'Case manager and provider assignment are not in the canonical referral.',
      },
      appointment: {
        available: false,
        reason: 'Appointment details will appear after scheduling sync.',
      },
      recentActivity: {
        available: false,
        reason: 'Activity history will appear after automation events are recorded.',
      },
    },
  }
}

const BUTLER_RECORD = butlerCanonicalReferral as unknown as CanonicalReferral

export const PATIENT_PROFILES: Record<string, PatientProfileViewModel> = {
  [BUTLER_PROFILE_ID]: mapCanonicalReferralToProfile(
    BUTLER_PROFILE_ID,
    BUTLER_RECORD,
    BUTLER_WORKFLOW,
  ),
}

export function getPatientProfile(
  profileId: string | null | undefined,
): PatientProfileViewModel | null {
  if (!profileId) return null
  return PATIENT_PROFILES[profileId] ?? null
}
