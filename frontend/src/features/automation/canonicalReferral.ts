/** Mirrors backend CanonicalReferral v1 from intake_extractor/canonical_referral.py */

export type FieldStatus = 'present' | 'explicitly_none' | 'missing' | 'unclear'
export type Confidence = 'high' | 'medium' | 'low'

export interface CanonicalExtractionAudit {
  primary_model: string
  models_attempted: string[]
  pass_models: string[]
  fallback_used: boolean
}

export interface CanonicalSource {
  email_id: string | null
  attachment_id: string | null
  file_name: string
  pdf_sha256: string
  page_count: number | null
  sent_by: string | null
  extraction: CanonicalExtractionAudit | null
}

export interface CanonicalName {
  first: string | null
  middle: string | null
  last: string | null
  suffix: string | null
  full: string | null
}

export interface CanonicalAddress {
  line_1: string | null
  line_2: string | null
  city: string | null
  state: string | null
  postal_code: string | null
  country: string | null
}

export interface CanonicalPhone {
  number: string
  type: string | null
}

export interface CanonicalEmergencyContact {
  name: CanonicalName
  relationship: string | null
  phone: string | null
}

export interface CanonicalPatient {
  name: CanonicalName
  date_of_birth: string | null
  age: number | null
  sex_or_gender: string | null
  ssn: string | null
  mrn: string | null
  source_patient_id: string | null
  source_patient_id_label: string | null
  phones: CanonicalPhone[]
  email: string | null
  address: CanonicalAddress
  emergency_contact: CanonicalEmergencyContact | null
}

export interface CanonicalOrganization {
  name: string | null
  contact_name: string | null
  phone: string | null
  fax: string | null
  email: string | null
  address: string | null
}

export interface CanonicalReferralSource {
  organization: CanonicalOrganization
  provider_name: string | null
  referral_or_order_date: string | null
}

export interface CanonicalHomeHealthOrHospice {
  organization: CanonicalOrganization
  hospice: boolean | null
  palliative_care: boolean | null
}

export interface CanonicalAdmission {
  admission_date: string | null
  facility: CanonicalOrganization
  place_of_service: string | null
  medicare_admission: boolean | null
}

export interface CanonicalDiagnosis {
  code: string | null
  description: string | null
  added_date: string | null
  is_primary: boolean | null
  status: string | null
}

export interface CanonicalMedication {
  name: string | null
  strength: string | null
  dose_form: string | null
  directions: string | null
  status: string | null
  prescribed_date: string | null
  prescriber: string | null
  days_supply: number | null
  quantity: string | null
  refills: number | null
}

export interface CanonicalAllergy {
  name: string | null
  reaction: string | null
  treatment: string | null
  status: string | null
}

export interface CanonicalClinical {
  summary: string | null
  wound_order_included: boolean | null
  diagnoses: CanonicalDiagnosis[]
  medications: CanonicalMedication[]
  allergies: CanonicalAllergy[]
  diagnoses_section_present: boolean | null
  medications_section_present: boolean | null
  allergies_section_present: boolean | null
  no_known_allergies_explicit: boolean | null
  notes: string[]
}

export interface CanonicalInsurance {
  payer_name: string | null
  policy_number: string | null
  group_number: string | null
  group_name: string | null
  policy_holder_name: string | null
  insurance_type: 'Primary' | 'Secondary' | 'Tertiary' | 'Other' | null
  effective_date: string | null
  expiration_date: string | null
  is_patient_policy_holder: boolean | null
  subscriber_first_name: string | null
  subscriber_last_name: string | null
  subscriber_date_of_birth: string | null
  subscriber_relationship: string | null
}

export interface CanonicalRequestedService {
  service: string | null
  frequency: string | null
  instructions: string | null
}

export interface CanonicalFieldQuality {
  status: FieldStatus
  confidence: Confidence
  evidence_pages: number[]
  evidence_quote: string | null
}

export interface CanonicalReferral {
  schema_version: number
  referral_id: string
  source: CanonicalSource
  document_type: string | null
  patient: CanonicalPatient
  referral_source: CanonicalReferralSource
  home_health_or_hospice: CanonicalHomeHealthOrHospice
  admission: CanonicalAdmission
  clinical: CanonicalClinical
  insurances: CanonicalInsurance[]
  requested_services: CanonicalRequestedService[]
  field_quality: Record<string, CanonicalFieldQuality>
  warnings: string[]
}

export function patientDisplayName(patient: CanonicalPatient): string {
  return (
    patient.name.full ??
    [patient.name.first, patient.name.last].filter(Boolean).join(' ') ??
    'Unknown patient'
  )
}

export function patientAddressLine(patient: CanonicalPatient): string {
  const { address } = patient
  return [
    address.line_1,
    address.line_2,
    [address.city, address.state, address.postal_code].filter(Boolean).join(' '),
  ]
    .filter(Boolean)
    .join(', ')
}

export function formatInsuranceList(insurances: CanonicalInsurance[]): string {
  return insurances
    .map((item) =>
      [item.payer_name, item.policy_number, item.insurance_type]
        .filter(Boolean)
        .join(' · '),
    )
    .join('; ')
}

/** Seven intake gate fields mapped to canonical field_quality paths */
export const REQUIRED_FIELD_PATHS = [
  { key: 'patient_name', label: 'Patient name', path: 'patient.name' },
  { key: 'date_of_birth', label: 'Date of birth', path: 'patient.date_of_birth' },
  { key: 'contact_number', label: 'Contact number', path: 'patient.phones' },
  { key: 'patient_address', label: 'Patient address', path: 'patient.address' },
  {
    key: 'home_health',
    label: 'Home health or hospice agency',
    path: 'home_health_or_hospice',
  },
  { key: 'clinical', label: 'Wound or clinical information', path: 'clinical' },
  { key: 'insurance', label: 'Insurance information', path: 'insurances' },
] as const

export function requiredFieldValue(
  record: CanonicalReferral,
  path: string,
): string {
  const patient = record.patient
  switch (path) {
    case 'patient.name':
      return patientDisplayName(patient)
    case 'patient.date_of_birth':
      return patient.date_of_birth ?? '—'
    case 'patient.phones':
      return patient.phones[0]?.number ?? '—'
    case 'patient.address':
      return patientAddressLine(patient)
    case 'home_health_or_hospice':
      return record.home_health_or_hospice.organization.name ?? 'Not documented'
    case 'clinical':
      return record.clinical.summary ?? '—'
    case 'insurances':
      return formatInsuranceList(record.insurances) || '—'
    default:
      return '—'
  }
}
