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
  const completeCount = REQUIRED_FIELD_PATHS.filter(
    ({ path }) => {
      const status = record.field_quality[path]?.status
      return status === 'present' || status === 'explicitly_none'
    },
  ).length

  return {
    'discover-email': snap('discover-email', {
      status: 'completed',
      duration: 'Under 1 second',
      executedAt: 'August 10, 2026 at 9:14 AM',
      artifactTitle: 'Discovered referral email',
      validation:
        'The message has a stable Microsoft message ID and received timestamp.',
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
    'fingerprint-attachment': snap('fingerprint-attachment', {
      status: 'completed',
      duration: 'Under 1 second',
      executedAt: 'August 10, 2026 at 9:14 AM',
      artifactTitle: 'Document fingerprint',
      validation:
        'A completed fingerprint is skipped; failed work may be retried safely.',
      knownAtThisPoint: identityKnown(record),
      artifactSections: [
        {
          id: 'fingerprint',
          title: 'Fingerprint record',
          defaultExpanded: true,
          fields: [
            { label: 'SHA-256', value: sha },
            { label: 'Referral ID', value: record.referral_id },
            { label: 'Prior completion', value: 'Not previously completed' },
            { label: 'Retry policy', value: 'Safe to process' },
          ],
        },
      ],
    }),
    'extract-referral': snap('extract-referral', {
      status: 'completed',
      duration: '2m 41s',
      executedAt: 'August 10, 2026 at 9:17 AM',
      artifactTitle: 'Canonical referral extraction',
      validation:
        'The response must satisfy the referral schema before it is accepted.',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: buildExtractionSections(record),
    }),
    'verify-required-fields': snap('verify-required-fields', {
      status: 'attention',
      duration: 'Under 1 second',
      executedAt: 'August 10, 2026 at 9:17 AM',
      artifactTitle: 'Seven-field completeness review',
      validation:
        'Name, DOB, phone, address, agency, wound information, and insurance are evaluated separately.',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: buildRequiredFieldSections(record),
    }),
    'apply-threshold': snap('apply-threshold', {
      status: 'attention',
      duration: 'Under 1 second',
      executedAt: 'August 10, 2026 at 9:17 AM',
      artifactTitle: 'Seven-field handoff gate',
      validation:
        'All seven required fields must be complete or explicitly none before handoff.',
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
    'search-monday': snap('search-monday', {
      status: 'completed',
      duration: '1.2s',
      executedAt: 'August 10, 2026 at 9:17 AM',
      artifactTitle: 'Monday.com duplicate search',
      validation:
        'Name-only matches never authorize patient creation or blocking.',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: [
        {
          id: 'monday-search',
          title: 'Search query and results',
          defaultExpanded: true,
          fields: [
            {
              label: 'Query identity',
              value: `${patientDisplayName(record.patient)} · ${record.patient.date_of_birth}`,
            },
            { label: 'Candidates found', value: '0' },
            { label: 'Result', value: 'No matching Monday.com candidate found' },
          ],
        },
      ],
    }),
    'search-drk': snap('search-drk', {
      status: 'completed',
      duration: '1.8s',
      executedAt: 'August 10, 2026 at 9:17 AM',
      artifactTitle: 'DRK chart search',
      validation:
        'Any candidate requires DOB confirmation before it can be treated as the same patient.',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: [
        {
          id: 'drk-search',
          title: 'Search query and results',
          defaultExpanded: true,
          fields: [
            {
              label: 'Query identity',
              value: `${patientDisplayName(record.patient)} · ${record.patient.date_of_birth}`,
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
    'classify-duplicate': snap('classify-duplicate', {
      status: 'completed',
      duration: 'Under 1 second',
      executedAt: 'August 10, 2026 at 9:17 AM',
      artifactTitle: 'Duplicate classification',
      validation: 'Probable and exact matches are blocked for human review.',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: [
        {
          id: 'duplicate',
          title: 'Combined duplicate result',
          defaultExpanded: true,
          fields: [
            { label: 'Monday candidates', value: '0' },
            { label: 'DRK candidates', value: '0 exact matches' },
            { label: 'Classification', value: 'Distinct patient' },
            {
              label: 'Creation eligibility',
              value: 'Eligible after human approval (subject to field completeness)',
            },
          ],
        },
      ],
    }),
    'build-review-email': snap('build-review-email', {
      status: 'attention',
      duration: 'Under 1 second',
      executedAt: 'August 10, 2026 at 9:18 AM',
      artifactTitle: 'Human review email draft',
      validation:
        'The message states what is missing and never claims a write already occurred.',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: [
        {
          id: 'review-draft',
          title: 'Review summary',
          defaultExpanded: true,
          fields: [
            { label: 'Patient', value: patientDisplayName(record.patient) },
            { label: 'Referral ID', value: record.referral_id },
            {
              label: 'Completeness',
              value: `${completeCount} of 7 required fields complete`,
            },
            {
              label: 'Missing',
              value: 'Home health or hospice agency',
              fieldPath: 'home_health_or_hospice',
            },
            { label: 'Duplicate status', value: 'Distinct patient' },
            {
              label: 'Draft excerpt',
              value:
                'Missing home-health/hospice agency. Duplicate search clear. Approval required before destination writes.',
            },
          ],
        },
      ],
    }),
    'send-review-email': snap('send-review-email', {
      status: 'completed',
      duration: 'Under 1 second',
      executedAt: 'August 10, 2026 at 9:18 AM',
      artifactTitle: 'Review request delivery',
      validation:
        'The outbound message is linked to one referral and one review request.',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: [
        {
          id: 'delivery',
          title: 'Delivery receipt',
          defaultExpanded: true,
          fields: [
            { label: 'Destination', value: 'Braxton Rickert · info-box review queue' },
            { label: 'Message ID', value: 'AAMkAGButlerReview001' },
            { label: 'Thread', value: emailId },
            { label: 'Sent at', value: 'August 10, 2026 at 9:18 AM' },
            { label: 'Linked referral', value: record.referral_id },
          ],
        },
      ],
    }),
    'interpret-reply': snap('interpret-reply', {
      status: 'waiting',
      duration: 'Pending',
      executedAt: 'Awaiting reviewer reply',
      artifactTitle: 'Reviewer reply classification',
      validation:
        'Ambiguous replies remain pending and cannot trigger external writes.',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: [
        {
          id: 'reply',
          title: 'Reply interpretation',
          defaultExpanded: true,
          fields: [
            { label: 'Status', value: 'Awaiting human reply' },
            { label: 'Expected intent', value: 'approve · reject · correct · unclear' },
            {
              label: 'Blockers visible to reviewer',
              value: 'Missing home-health/hospice agency',
              fieldPath: 'home_health_or_hospice',
            },
          ],
        },
      ],
    }),
    'gate-destinations': snap('gate-destinations', {
      status: 'waiting',
      duration: 'Not authorized',
      executedAt: 'Blocked pending approval and completeness',
      artifactTitle: 'Destination authorization gate',
      validation: 'The gate is atomic and idempotent.',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: [
        {
          id: 'gate-receipt',
          title: 'Authorization receipt',
          defaultExpanded: true,
          fields: [
            { label: 'Seven-field gate', value: 'Blocked — 1 field missing' },
            { label: 'Duplicate gate', value: 'Clear' },
            { label: 'Human approval', value: 'Pending' },
            { label: 'Canonical version', value: 'v1 · schema_version 1' },
            { label: 'Decision', value: 'Destination actions denied' },
          ],
        },
      ],
    }),
  }
}

export const BUTLER_INTAKE_SNAPSHOTS = buildButlerIntakeSnapshots()

export const BUTLER_INTAKE_STEP_IDS = [
  'discover-email',
  'validate-pdf',
  'fingerprint-attachment',
  'extract-referral',
  'verify-required-fields',
  'apply-threshold',
  'search-monday',
  'search-drk',
  'classify-duplicate',
  'build-review-email',
  'send-review-email',
  'interpret-reply',
  'gate-destinations',
] as const
