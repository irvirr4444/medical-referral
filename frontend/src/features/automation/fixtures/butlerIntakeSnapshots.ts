import type { CanonicalReferral } from '../canonicalReferral'
import {
  REQUIRED_FIELD_PATHS,
  patientAddressLine,
  patientDisplayName,
  requiredFieldValue,
} from '../canonicalReferral'
import {
  admissionFields,
  allergyFields,
  allergyFlagFields,
  diagnosisFields,
  emergencyContactFields,
  insuranceFields,
  medicationFields,
  noteFields,
  organizationFields,
  phoneFields,
  serviceFields,
  warningFields,
} from '../intakeRecords'
import type {
  ArtifactSection,
  MicrostepExecutionSnapshot,
} from '../types'

import butlerCanonical from './butlerCanonicalReferral.json'

export const BUTLER_CANONICAL = butlerCanonical as unknown as CanonicalReferral

function identityKnown(record: CanonicalReferral) {
  return [
    { label: 'Patient', value: patientDisplayName(record.patient) },
    { label: 'Referral ID', value: record.referral_id },
  ]
}

/** Outlook-style From line for feed proof. */
function senderDisplay(record: CanonicalReferral) {
  if (record.source.sent_by?.trim()) return record.source.sent_by.trim()
  const contact = record.referral_source?.organization?.contact_name?.trim()
  const org = record.referral_source?.organization?.name?.trim()
  const email = record.referral_source?.organization?.email?.trim()
  if (contact && email) return `${contact} <${email}>`
  if (contact && org) return `${contact} · ${org}`
  if (org && email) return `${org} <${email}>`
  if (email) return email
  if (org) return org
  return '—'
}

function referralPartnerDetails(record: CanonicalReferral) {
  const provider = record.referral_source.provider_name?.trim()
  const contact = record.referral_source.organization.contact_name?.trim()
  const orgEmail = record.referral_source.organization.email?.trim()
  const sentBy = record.source.sent_by?.trim() ?? ''
  const sentMatch = sentBy.match(/^(.+?)\s*<([^>]+)>$/)

  const rawName =
    provider ||
    contact ||
    sentMatch?.[1]?.trim() ||
    record.referral_source.organization.name?.trim() ||
    '—'
  const name = rawName.replace(/\s*\([^)]*\)\s*/g, ' ').replace(/\s{2,}/g, ' ').trim()
  const email = orgEmail || sentMatch?.[2]?.trim()

  return { name, email }
}

function referralPartnerLine(record: CanonicalReferral) {
  const { name, email } = referralPartnerDetails(record)
  if (name !== '—' && email) return `${name} · ${email}`
  if (email) return email
  return name
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
        {
          label: 'Name',
          value: patientDisplayName(patient),
          fieldPath: 'patient.name',
          required: true,
        },
        {
          label: 'DOB',
          value: patient.date_of_birth ?? '—',
          fieldPath: 'patient.date_of_birth',
          required: true,
        },
        {
          label: 'Age',
          value: patient.age == null ? '—' : String(patient.age),
          fieldPath: 'patient.age',
        },
        {
          label: 'Sex',
          value: patient.sex_or_gender ?? '—',
          fieldPath: 'patient.sex_or_gender',
        },
        {
          label: 'SSN',
          value: patient.ssn ?? '—',
          fieldPath: 'patient.ssn',
        },
        {
          label: 'Source patient ID',
          value: patient.source_patient_id ?? '—',
          fieldPath: 'patient.source_patient_id',
        },
        {
          label: 'Source patient ID label',
          value: patient.source_patient_id_label ?? '—',
          fieldPath: 'patient.source_patient_id_label',
        },
        {
          label: 'MRN',
          value: patient.mrn ?? 'Not documented (not inferred from source ID)',
          fieldPath: 'patient.mrn',
        },
        {
          label: 'Email',
          value: patient.email ?? '—',
          fieldPath: 'patient.email',
        },
        {
          label: 'Address',
          value: patientAddressLine(patient),
          fieldPath: 'patient.address',
          required: true,
        },
      ],
    },
    {
      id: 'phones',
      title: 'Phones',
      defaultExpanded: false,
      repeatable: true,
      addKind: 'phone',
      fields: patient.phones.flatMap((item, index) => phoneFields(item, index)),
    },
    {
      id: 'emergency-contact',
      title: 'Emergency contact',
      defaultExpanded: false,
      fields: emergencyContactFields(patient.emergency_contact),
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
          label: 'Order date',
          value: record.referral_source.referral_or_order_date ?? '—',
          fieldPath: 'referral_source.referral_or_order_date',
        },
        ...organizationFields(
          record.referral_source.organization,
          'referral_source.organization',
        ),
      ],
    },
    {
      id: 'home-health',
      title: 'Home health or hospice',
      fields: [
        ...organizationFields(
          record.home_health_or_hospice.organization,
          'home_health_or_hospice.organization',
          { nameRequired: true },
        ),
        {
          label: 'Hospice',
          value:
            record.home_health_or_hospice.hospice == null
              ? '—'
              : record.home_health_or_hospice.hospice
                ? 'Yes'
                : 'No',
          fieldPath: 'home_health_or_hospice.hospice',
          choice: 'yesno',
        },
        {
          label: 'Palliative care',
          value:
            record.home_health_or_hospice.palliative_care == null
              ? '—'
              : record.home_health_or_hospice.palliative_care
                ? 'Yes'
                : 'No',
          fieldPath: 'home_health_or_hospice.palliative_care',
          choice: 'yesno',
        },
      ],
    },
    {
      id: 'admission',
      title: 'Admission',
      defaultExpanded: false,
      fields: admissionFields(record.admission),
    },
    {
      id: 'clinical',
      title: 'Clinical',
      defaultExpanded: false,
      fields: [
        {
          label: 'Summary',
          value: record.clinical.summary ?? '—',
          fieldPath: 'clinical.summary',
          required: true,
        },
        {
          label: 'Wound order included',
          value:
            record.clinical.wound_order_included == null
              ? '—'
              : record.clinical.wound_order_included
                ? 'Yes'
                : 'No',
          fieldPath: 'clinical.wound_order_included',
          choice: 'yesno',
        },
      ],
    },
    {
      id: 'diagnoses',
      title: 'Diagnoses',
      defaultExpanded: false,
      repeatable: true,
      addKind: 'diagnosis',
      fields: record.clinical.diagnoses.flatMap((item, index) =>
        diagnosisFields(item, index),
      ),
    },
    {
      id: 'medications',
      title: 'Medications',
      defaultExpanded: false,
      repeatable: true,
      addKind: 'medication',
      fields: record.clinical.medications.flatMap((item, index) =>
        medicationFields(item, index),
      ),
    },
    {
      id: 'allergies',
      title: 'Allergies',
      defaultExpanded: false,
      repeatable: true,
      addKind: 'allergy',
      fields: [
        ...allergyFlagFields(record),
        ...record.clinical.allergies.flatMap((item, index) =>
          allergyFields(item, index),
        ),
      ],
    },
    {
      id: 'notes',
      title: 'Clinical notes',
      defaultExpanded: false,
      repeatable: true,
      addKind: 'note',
      fields: record.clinical.notes.flatMap((note, index) =>
        noteFields(note, index),
      ),
    },
    {
      id: 'insurance',
      title: 'Insurance policies',
      defaultExpanded: false,
      repeatable: true,
      addKind: 'insurance',
      fields: record.insurances.flatMap((item, index) =>
        insuranceFields(item, index),
      ),
    },
    {
      id: 'services',
      title: 'Requested services',
      defaultExpanded: false,
      repeatable: true,
      addKind: 'service',
      fields: record.requested_services.flatMap((item, index) =>
        serviceFields(item, index),
      ),
    },
    {
      id: 'quality',
      title: 'Warnings',
      defaultExpanded: false,
      repeatable: true,
      addKind: 'warning',
      fields: record.warnings.flatMap((warning, index) =>
        warningFields(warning, index),
      ),
    },
  ]
}

export function buildIntakeSnapshots(
  record: CanonicalReferral,
  options: { runPrefix: string; executedAt: string },
): Record<string, MicrostepExecutionSnapshot> {
  const { runPrefix, executedAt } = options
  const snap = (
    stepId: string,
    partial: Omit<
      MicrostepExecutionSnapshot,
      'executionId' | 'stepId' | 'artifactId' | 'referralId'
    > & { artifactSuffix?: string },
  ): MicrostepExecutionSnapshot => {
    const artifactSuffix = partial.artifactSuffix ?? stepId
    return {
      executionId: `${runPrefix}-${stepId}-exec`,
      stepId,
      referralId: record.referral_id,
      artifactId: `${runPrefix}-${artifactSuffix}-artifact`,
      ...partial,
    }
  }

  const pdfName = record.source.file_name
  const sha = record.source.pdf_sha256
  const emailId = record.source.email_id ?? 'unknown'
  const patientName = patientDisplayName(record.patient)
  const dob = record.patient.date_of_birth ?? '—'
  const completeCount = REQUIRED_FIELD_PATHS.filter(({ path }) => {
    const status = record.field_quality[path]?.status
    return status === 'present' || status === 'explicitly_none'
  }).length
  const missingPaths = REQUIRED_FIELD_PATHS.filter(({ path }) => {
    return record.field_quality[path]?.status === 'missing'
  }).map(({ label }) => label)
  const unclearPaths = REQUIRED_FIELD_PATHS.filter(({ path }) => {
    return record.field_quality[path]?.status === 'unclear'
  }).map(({ label }) => label)
  const gapLabel = [...missingPaths, ...unclearPaths].join(', ') || 'None'
  const verifyStatus =
    missingPaths.length > 0 || unclearPaths.length > 0
      ? ('attention' as const)
      : ('completed' as const)
  const minFields = [
    'patient.name',
    'patient.date_of_birth',
    'patient.phones',
    'patient.address',
  ] as const
  const thresholdMet = minFields.every((path) => {
    const status = record.field_quality[path]?.status
    return status === 'present' || status === 'explicitly_none'
  })

  return {
    'receive-referral': snap('receive-referral', {
      status: 'completed',
      duration: 'Under 1 second',
      executedAt,
      artifactTitle: 'Discovered referral email',
      validation:
        'The message has a stable Microsoft message ID and received timestamp.',
      input: 'Unread Outlook message in info@westcostwound.com',
      output: 'Referral email identified',
      knownAtThisPoint: [
        { label: 'Inbox', value: 'info@westcostwound.com' },
        { label: 'Attachment', value: pdfName },
      ],
      artifactSections: [
        {
          id: 'email',
          title: 'Email metadata',
          defaultExpanded: true,
          fields: [
            { label: 'Message ID', value: emailId },
            { label: 'Sender', value: senderDisplay(record) },
            { label: 'Received', value: executedAt },
            { label: 'Attachment', value: pdfName },
            { label: 'Attachment ID', value: record.source.attachment_id ?? '—' },
          ],
        },
      ],
    }),
    'extract-and-verify': snap('extract-and-verify', {
      status: thresholdMet ? verifyStatus : 'attention',
      duration: '2m 41s',
      executedAt,
      artifactTitle: 'Referral details extracted and verified',
      validation:
        'Name, DOB, phone, and address must clear the threshold before duplicate checks continue.',
      input: `Valid PDF · ${pdfName}`,
      output: !thresholdMet
        ? 'Details extracted · identity/contact incomplete'
        : missingPaths.length > 0 || unclearPaths.length > 0
          ? `Details extracted · ${completeCount} of 7 fields complete · ${gapLabel} incomplete`
          : 'Details extracted · 7 of 7 fields complete',
      knownAtThisPoint: identityAndContact(record),
      feedDecision: {
        thresholdMet,
        completeCount,
        totalRequired: 7,
        missingLabels: missingPaths,
        unclearLabels: unclearPaths,
        identityLine: [
          patientName,
          dob,
          record.patient.phones[0]?.number ?? '—',
        ].join(' · '),
      },
      artifactSections: [
        {
          id: 'gate',
          title: 'Minimum identity and contact gate',
          defaultExpanded: true,
          fields: [
            { label: 'Name', value: patientName },
            { label: 'Date of birth', value: dob },
            {
              label: 'Phone',
              value: record.patient.phones[0]?.number ?? '—',
            },
            {
              label: 'Address',
              value: patientAddressLine(record.patient),
            },
            {
              label: 'Decision',
              value: thresholdMet
                ? 'Threshold met — Monday and DRK checks allowed'
                : 'Threshold not met — destination writes blocked',
            },
          ],
        },
        ...buildRequiredFieldSections(record),
        ...buildExtractionSections(record).map((section) =>
          section.id === 'demographics' || section.id === 'referral-source'
            ? { ...section, defaultExpanded: false }
            : section,
        ),
        {
          id: 'processing-guard',
          title: 'Processing guardrail',
          defaultExpanded: false,
          repeatable: true,
          addKind: 'guard',
          fields: [
            {
              label: 'SHA-256 fingerprint',
              value: sha,
              rowId: 'processing-guard.sha',
            },
            {
              label: 'Duplicate completion check',
              value: 'Not previously completed',
              rowId: 'processing-guard.duplicate',
            },
          ],
        },
      ],
    }),
    'check-monday': snap('check-monday', {
      status: 'completed',
      duration: '1.2s',
      executedAt,
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
      executedAt,
      artifactTitle: 'DRK chart search',
      validation:
        'Any candidate requires DOB confirmation before it can be treated as the same patient.',
      input: `${patientName} · DOB ${dob}`,
      output: 'No exact DRK chart match found',
      knownAtThisPoint: identityAndContact(record),
      artifactSections: [
        {
          id: 'drk-search',
          title: 'DRK search query and results',
          defaultExpanded: true,
          fields: [
            {
              label: 'Query identity',
              value: `${patientName} · ${dob}`,
            },
            { label: 'Candidates found', value: '0' },
          ],
        },
      ],
    }),
    'confirm-referral-contacted': snap('confirm-referral-contacted', {
      status: 'waiting',
      duration: 'Under 1 second',
      executedAt,
      artifactTitle: 'Referral partner contact confirmation',
      validation:
        'Intake cannot complete until referral partner contact is explicitly confirmed.',
      input: 'Outreach note and intake review context',
      output: 'Awaiting partner confirmation',
      knownAtThisPoint: identityAndContact(record),
      feedContactConfirmation: (() => {
        const partner = referralPartnerDetails(record)
        return {
          partnerName: partner.name,
          partnerEmail: partner.email,
          contactedBack: false,
        }
      })(),
      artifactSections: [
        {
          id: 'contact-confirmation',
          title: 'Contact confirmation checklist',
          defaultExpanded: true,
          fields: [
            {
              label: 'Referral partner',
              value: referralPartnerLine(record),
            },
            {
              label: 'Partner replied?',
              value: 'Not yet',
            },
          ],
        },
      ],
    }),
  }
}

export function buildButlerIntakeSnapshots(
  record: CanonicalReferral = BUTLER_CANONICAL,
): Record<string, MicrostepExecutionSnapshot> {
  return buildIntakeSnapshots(record, {
    runPrefix: 'butler-alva',
    executedAt: 'August 10, 2026 at 9:14 AM',
  })
}

export const BUTLER_INTAKE_SNAPSHOTS = buildButlerIntakeSnapshots()

export const BUTLER_INTAKE_STEP_IDS = [
  'receive-referral',
  'extract-and-verify',
  'check-monday',
  'check-drk',
  'confirm-referral-contacted',
] as const
