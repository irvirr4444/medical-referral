import type { CanonicalReferral } from '../canonicalReferral'
import {
  REQUIRED_FIELD_PATHS,
  patientAddressLine,
  patientDisplayName,
  requiredFieldValue,
} from '../canonicalReferral'
import type {
  ArtifactSection,
  MicrostepExecutionSnapshot,
} from '../types'

import butlerCanonical from './butlerCanonicalReferral.json'

export const BUTLER_CANONICAL = butlerCanonical as unknown as CanonicalReferral

const REFERRAL_ID = BUTLER_CANONICAL.referral_id
const RUN_PREFIX = 'butler-alva'

function snap(
  stepId: string,
  partial: Omit<
    MicrostepExecutionSnapshot,
    'executionId' | 'stepId' | 'artifactId' | 'referralId'
  > & { artifactSuffix?: string },
): MicrostepExecutionSnapshot {
  const artifactSuffix = partial.artifactSuffix ?? stepId
  return {
    executionId: `${RUN_PREFIX}-${stepId}-exec`,
    stepId,
    referralId: REFERRAL_ID,
    artifactId: `${RUN_PREFIX}-${artifactSuffix}-artifact`,
    ...partial,
  }
}

function identityKnown(record: CanonicalReferral) {
  return [
    { label: 'Patient', value: patientDisplayName(record.patient) },
    { label: 'Referral ID', value: record.referral_id },
  ]
}

function identityAndContact(record: CanonicalReferral) {
  return [
    ...identityKnown(record),
    { label: 'Date of birth', value: record.patient.date_of_birth ?? '—' },
    { label: 'Phone', value: record.patient.phones[0]?.number ?? '—' },
    { label: 'Address', value: patientAddressLine(record.patient) },
  ]
}

function buildRequiredFieldSections(record: CanonicalReferral): ArtifactSection[] {
  return [
    {
      id: 'required-fields',
      title: 'Seven required fields',
      defaultExpanded: true,
      fields: REQUIRED_FIELD_PATHS.map(({ label, path }) => {
        const quality = record.field_quality[path]
        const evidence =
          quality?.evidence_quote ??
          (quality?.evidence_pages?.length
            ? `Page ${quality.evidence_pages.join(', ')}`
            : 'No evidence recorded')
        return {
          label,
          value: requiredFieldValue(record, path),
          fieldPath: path,
          meta: evidence,
        }
      }),
    },
  ]
}

function buildExtractionSections(record: CanonicalReferral): ArtifactSection[] {
  const patient = record.patient
  return [
    {
      id: 'demographics',
      title: 'Demographics',
      defaultExpanded: true,
      fields: [
        { label: 'Name', value: patientDisplayName(patient), fieldPath: 'patient.name' },
        { label: 'DOB', value: patient.date_of_birth ?? '—', fieldPath: 'patient.date_of_birth' },
        { label: 'Sex', value: patient.sex_or_gender ?? '—' },
        { label: 'Source patient ID', value: patient.source_patient_id ?? '—', fieldPath: 'patient.source_patient_id' },
        { label: 'MRN', value: patient.mrn ?? 'Not documented (not inferred from source ID)' },
        { label: 'Phone', value: patient.phones[0]?.number ?? '—', fieldPath: 'patient.phones' },
        { label: 'Email', value: patient.email ?? '—' },
        { label: 'Address', value: patientAddressLine(patient), fieldPath: 'patient.address' },
      ],
    },
    {
      id: 'referral-source',
      title: 'Referral source',
      fields: [
        {
          label: 'Provider',
          value: record.referral_source.provider_name ?? '—',
          fieldPath: 'referral_source.provider_name',
        },
        {
          label: 'Organization phone',
          value: record.referral_source.organization.phone ?? '—',
        },
        {
          label: 'Facility',
          value: record.referral_source.organization.name ?? 'Not documented',
        },
      ],
    },
    {
      id: 'clinical',
      title: 'Clinical',
      defaultExpanded: false,
      fields: [
        { label: 'Summary', value: record.clinical.summary ?? '—', fieldPath: 'clinical.summary' },
        {
          label: 'Diagnoses',
          value: `${record.clinical.diagnoses.length} ICD-10 codes extracted`,
          fieldPath: 'clinical.diagnoses',
        },
        {
          label: 'No known allergies',
          value: record.clinical.no_known_allergies_explicit ? 'Explicitly documented' : '—',
        },
      ],
    },
    {
      id: 'insurance',
      title: 'Insurance policies',
      defaultExpanded: false,
      fields: record.insurances.map((item, index) => ({
        label: item.insurance_type ?? `Policy ${index + 1}`,
        value: [item.payer_name, item.policy_number].filter(Boolean).join(' · '),
        fieldPath: `insurances.${index}`,
      })),
    },
    {
      id: 'quality',
      title: 'Warnings',
      defaultExpanded: false,
      fields: record.warnings.map((warning, index) => ({
        label: `Warning ${index + 1}`,
        value: warning,
      })),
    },
  ]
}

export function buildButlerIntakeSnapshots(
  record: CanonicalReferral = BUTLER_CANONICAL,
): Record<string, MicrostepExecutionSnapshot> {
  const pdfName = record.source.file_name
  const sha = record.source.pdf_sha256
  const emailId = record.source.email_id ?? 'unknown'
  const patientName = patientDisplayName(record.patient)
  const dob = record.patient.date_of_birth ?? '—'
  const completeCount = REQUIRED_FIELD_PATHS.filter(
    ({ path }) => {
      const status = record.field_quality[path]?.status
      return status === 'present' || status === 'explicitly_none'
    },
  ).length

  return {
    'receive-referral': snap('receive-referral', {
      status: 'completed',
      duration: 'Under 1 second',
      executedAt: 'August 10, 2026 at 9:14 AM',
      artifactTitle: 'Discovered referral email',
      validation:
        'The message has a stable Microsoft message ID and received timestamp.',
      input: 'Unread Outlook message in info@westcostwound.com',
      output: `Referral email identified · attachment ${pdfName}`,
      knownAtThisPoint: [
        { label: 'Inbox', value: 'info@westcostwound.com' },
        { label: 'Subject', value: 'Chart export — wound care referral' },
      ],
      artifactSections: [
        {
          id: 'email',
          title: 'Email metadata',
          defaultExpanded: true,
          fields: [
            { label: 'Message ID', value: emailId },
            { label: 'Sender', value: record.source.sent_by ?? '—' },
            { label: 'Received', value: 'August 10, 2026 at 9:14 AM' },
            { label: 'Attachment', value: pdfName },
            { label: 'Attachment ID', value: record.source.attachment_id ?? '—' },
          ],
        },
      ],
    }),
    'validate-pdf': snap('validate-pdf', {
      status: 'completed',
      duration: 'Under 1 second',
      executedAt: 'August 10, 2026 at 9:14 AM',
      artifactTitle: 'PDF validation result',
      validation:
        'Filename ends in .pdf and content starts with the PDF file signature.',
      input: `${pdfName} · application/pdf`,
      output: 'Valid PDF accepted for intake processing',
      knownAtThisPoint: identityKnown(record),
      artifactSections: [
        {
          id: 'validation',
          title: 'Attachment validation',
          defaultExpanded: true,
          fields: [
            { label: 'Filename', value: pdfName },
            { label: 'MIME type', value: 'application/pdf' },
            { label: 'Signature', value: '%PDF-1.4 accepted' },
            { label: 'Page count', value: String(record.source.page_count ?? '—') },
            { label: 'Result', value: 'Accepted for intake processing' },
          ],
        },
      ],
    }),
    'extract-details': snap('extract-details', {
      status: 'completed',
      duration: '2m 41s',
      executedAt: 'August 10, 2026 at 9:17 AM',
      artifactTitle: 'Patient and referral details extracted',
      validation:
        'The response must satisfy the referral schema before it is accepted.',
      input: `Valid PDF · ${pdfName}`,
      output: `Patient and referral details extracted for ${patientName}`,
      knownAtThisPoint: identityAndContact(record),
      artifactSections: [
        ...buildExtractionSections(record),
        {
          id: 'processing-guard',
          title: 'Processing guardrail',
          defaultExpanded: false,
          fields: [
            { label: 'SHA-256 fingerprint', value: sha },
            { label: 'Duplicate completion check', value: 'Not previously completed' },
          ],
        },
      ],
    }),
    'verify-required-fields': snap('verify-required-fields', {
      status: 'attention',
      duration: 'Under 1 second',
      executedAt: 'August 10, 2026 at 9:17 AM',
      artifactTitle: 'Seven-field completeness review',
      validation:
        'Name, DOB, phone, address, agency, wound information, and insurance are evaluated separately.',
      input: 'Canonical referral JSON',
      output: `${completeCount} of 7 required fields complete · home-health agency missing`,
      knownAtThisPoint: identityAndContact(record),
      artifactSections: buildRequiredFieldSections(record),
    }),
    'check-threshold': snap('check-threshold', {
      status: 'attention',
      duration: 'Under 1 second',
      executedAt: 'August 10, 2026 at 9:17 AM',
      artifactTitle: 'Seven-field handoff gate',
      validation:
        'All seven required fields must be complete or explicitly none before handoff.',
      input: `${completeCount} of 7 fields complete · agency missing`,
      output: 'Handoff blocked · missing home-health or hospice agency',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: [
        {
          id: 'gate',
          title: 'Handoff eligibility',
          defaultExpanded: true,
          fields: [
            {
              label: 'Fields complete',
              value: `${completeCount} of 7`,
            },
            {
              label: 'Missing fields',
              value: 'Home health or hospice agency',
              fieldPath: 'home_health_or_hospice',
            },
            {
              label: 'Decision',
              value: 'Needs information — blocked for handoff',
            },
            {
              label: 'Next action',
              value: 'Call referral partner or escalate to marketer',
            },
          ],
        },
      ],
    }),
    'check-monday': snap('check-monday', {
      status: 'completed',
      duration: '1.2s',
      executedAt: 'August 10, 2026 at 9:17 AM',
      artifactTitle: 'Monday.com duplicate search',
      validation:
        'Name-only matches never authorize patient creation or blocking.',
      input: `${patientName} · DOB ${dob}`,
      output: 'No matching Monday.com candidate found',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: [
        {
          id: 'monday-search',
          title: 'Search query and results',
          defaultExpanded: true,
          fields: [
            {
              label: 'Query identity',
              value: `${patientName} · ${dob}`,
            },
            { label: 'Candidates found', value: '0' },
            { label: 'Result', value: 'No matching Monday.com candidate found' },
          ],
        },
      ],
    }),
    'check-drk': snap('check-drk', {
      status: 'completed',
      duration: '1.8s',
      executedAt: 'August 10, 2026 at 9:17 AM',
      artifactTitle: 'DRK chart search',
      validation:
        'Any candidate requires DOB confirmation before it can be treated as the same patient.',
      input: `${patientName} · DOB ${dob}`,
      output: 'No exact DRK chart match found',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: [
        {
          id: 'drk-search',
          title: 'Search query and results',
          defaultExpanded: true,
          fields: [
            {
              label: 'Query identity',
              value: `${patientName} · ${dob}`,
            },
            {
              label: 'Source patient ID',
              value: record.patient.source_patient_id ?? '—',
              fieldPath: 'patient.source_patient_id',
            },
            { label: 'MRN used', value: 'None — MRN not inferred from source ID' },
            { label: 'Exact chart match', value: 'No exact DRK chart match found' },
          ],
        },
      ],
    }),
    'confirm-referral-contacted': snap('confirm-referral-contacted', {
      status: 'waiting',
      duration: 'Under 1 second',
      executedAt: 'August 10, 2026 at 9:18 AM',
      artifactTitle: 'Referral partner contact confirmation',
      validation:
        'Intake cannot complete until referral partner contact is explicitly confirmed.',
      input: 'Outreach note and intake review context',
      output: 'Referral partner contact confirmation pending',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: [
        {
          id: 'contact-confirmation',
          title: 'Contact confirmation checklist',
          defaultExpanded: true,
          fields: [
            { label: 'Referral partner contacted', value: 'Pending confirmation' },
            { label: 'Outreach owner', value: 'DRK intake screen watcher' },
            { label: 'Expected note', value: 'Call or callback outcome logged' },
            { label: 'Escalation path', value: 'Marketer follow-up if unreachable' },
            { label: 'Review queue', value: 'Braxton Rickert · info-box queue' },
            { label: 'Message ID', value: 'AAMkAGButlerReview001' },
            { label: 'Thread', value: emailId },
          ],
        },
      ],
    }),
    'confirm-information-complete': snap('confirm-information-complete', {
      status: 'waiting',
      duration: 'Awaiting human confirmation',
      executedAt: 'August 10, 2026 at 9:18 AM',
      artifactTitle: 'Referral Intake completion confirmation',
      validation:
        'A DRK team member must confirm accuracy before intake is complete.',
      input: 'Extracted referral details + Monday/DRK checks + contact confirmation',
      output: 'Waiting for DRK confirmation that information is correct',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: [
        {
          id: 'completion-confirmation',
          title: 'Intake completion gate',
          defaultExpanded: true,
          fields: [
            { label: 'Information verified as correct', value: 'Pending confirmation' },
            { label: 'Seven required fields', value: `${completeCount} of 7 complete` },
            { label: 'Monday check', value: 'No existing patient found' },
            { label: 'DRK check', value: 'No existing chart found' },
            { label: 'Missing field', value: 'Home health or hospice agency' },
            { label: 'Decision', value: 'Intake remains open until confirmation is recorded' },
          ],
        },
      ],
    }),
  }
}

export const BUTLER_INTAKE_SNAPSHOTS = buildButlerIntakeSnapshots()

export const BUTLER_INTAKE_STEP_IDS = [
  'receive-referral',
  'validate-pdf',
  'extract-details',
  'verify-required-fields',
  'check-threshold',
  'check-monday',
  'check-drk',
  'confirm-referral-contacted',
  'confirm-information-complete',
] as const
