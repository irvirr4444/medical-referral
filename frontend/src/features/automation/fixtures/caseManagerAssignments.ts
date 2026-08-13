import {
  formatInsuranceList,
  patientAddressLine,
  type CanonicalReferral,
} from '../canonicalReferral'
import { providerPatientLocationDisplay } from './providerAssignments'

export interface CaseManagerOption {
  name: string
  email: string
}

export interface CaseManagerSuggestion extends CaseManagerOption {
  reason: string
}

export interface CaseManagerNotification {
  managerName: string
  managerEmail: string
  subject: string
  message: string
  patientFields: Array<{ label: string; value: string }>
}

export interface ReferralSourceNotification {
  to: string
  ccName: string
  ccEmail: string
  subject: string
  body: string
}

export interface AssignedProviderRecord {
  name: string
  npi?: string
  city?: string
}

export interface MondayRecord {
  itemId: string
  board: string
  data: {
    patient_name: string
    date_of_birth: string
    contact_number: string
    patient_address: string
    home_health_or_hospice_agency: string
    wound_or_clinical_information: string
    insurance_information: string
    case_manager: CaseManagerOption
    sent_by: string
    referral_status: string
    assigned_provider?: string
    provider_npi?: string
    provider_city?: string
  }
}

export interface DrkDraftRecord {
  demographics: Array<{ label: string; value: string }>
  primaryAddress: Array<{ label: string; value: string }>
  contact: Array<{ label: string; value: string }>
  admission: Array<{ label: string; value: string }>
  referral: Array<{ label: string; value: string }>
  insurance: Array<{ label: string; value: string }>
  readyForFill: boolean
  blockers: string[]
  warnings: string[]
}

/** Active assignees sourced from case_managers.json. */
export const CASE_MANAGER_OPTIONS: CaseManagerOption[] = [
  { name: 'Braxton Rickert', email: 'brickert@westcoastwound.com' },
  { name: 'Carl Leo Biaoco', email: 'cbiaoco@westcoastwound.com' },
  { name: 'Carla Bustillo', email: 'cbustillo@westcoastwound.com' },
  { name: 'Charlie Catado', email: 'ccatado@westcoastwound.com' },
  { name: 'Cole Winfield', email: 'cwinfield@westcoastwound.com' },
  { name: 'Daisy Trujillo', email: 'dtrujillo@westcoastwound.com' },
  { name: 'Donessa Ruiz', email: 'druiz@westcoastwound.com' },
  { name: 'Erika Rentoy', email: 'erentoy@westcoastwound.com' },
  { name: 'Farrah Go', email: 'fgo@westcoastwound.com' },
  { name: 'Gin Peniel Lozano', email: 'glozano@westcoastwound.com' },
  { name: 'Hannah Angelique Casiño', email: 'hcasino@westcoastwound.com' },
  { name: 'Jaidyn Lopez', email: 'jalopez@westcoastwound.com' },
  { name: 'Jazores', email: 'jazores@westcoastwound.com' },
  { name: 'Jessah Torres', email: 'jtorres@westcoastwound.com' },
  { name: 'Joanne Calumpang', email: 'jcalumpang@westcoastwound.com' },
  { name: 'John Lloyd Gerasmia', email: 'jgerasmia@westcoastwound.com' },
  { name: 'Jucelle Sayson', email: 'jsayson@westcoastwound.com' },
  { name: 'Kim Lopez', email: 'klopez@westcoastwound.com' },
  { name: 'Kyle Manapol', email: 'kmanapol@westcoastwound.com' },
  { name: 'Louise Jill Pongpong', email: 'lpongpong@westcoastwound.com' },
  { name: 'Michelle Lagahit', email: 'mlagahit@westcoastwound.com' },
  { name: 'Nadine Pelicano', email: 'ndelpelicano@westcoastwound.com' },
  { name: 'Nicole Chorvat', email: 'nchorvat@westcoastwound.com' },
  { name: 'Noel Susas Padohinog', email: 'npadohinog@westcoastwound.com' },
  { name: 'Rona Jane Gumbao', email: 'rjgumbao@westcoastwound.com' },
]

const SUGGESTIONS: Record<string, CaseManagerSuggestion> = {
  'marcus-feldman': {
    name: 'Cole Winfield',
    email: 'cwinfield@westcoastwound.com',
    reason: 'Demo routing match for the Gardena / South Bay service area',
  },
  'david-ruiz': {
    name: 'Carla Bustillo',
    email: 'cbustillo@westcoastwound.com',
    reason: 'Demo routing match for the Coastal Los Angeles service area',
  },
  'patricia-johnson': {
    name: 'Cole Winfield',
    email: 'cwinfield@westcoastwound.com',
    reason: 'Demo routing match for the Gardena / South Bay service area',
  },
  'gloria-bennett': {
    name: 'Donessa Ruiz',
    email: 'druiz@westcoastwound.com',
    reason: 'Demo routing match for the Riverside service area',
  },
  'dorothy-lane': {
    name: 'Carla Bustillo',
    email: 'cbustillo@westcoastwound.com',
    reason: 'Demo routing match for the Coastal Los Angeles service area',
  },
  'margaret-ellis': {
    name: 'Cole Winfield',
    email: 'cwinfield@westcoastwound.com',
    reason: 'Demo routing match for the Gardena / South Bay service area',
  },
  'walter-grant': {
    name: 'Nicole Chorvat',
    email: 'nchorvat@westcoastwound.com',
    reason: 'Demo routing match for the South Bay service area',
  },
  'arthur-kim': {
    name: 'Braxton Rickert',
    email: 'brickert@westcoastwound.com',
    reason: 'Demo routing match for hold-tracking follow-up',
  },
  'thomas-reed': {
    name: 'Donessa Ruiz',
    email: 'druiz@westcoastwound.com',
    reason: 'Demo routing match for the Riverside service area',
  },
  'helen-park': {
    name: 'Cole Winfield',
    email: 'cwinfield@westcoastwound.com',
    reason: 'Demo routing match for the South Bay service area',
  },
  'betty-hayes': {
    name: 'Nicole Chorvat',
    email: 'nchorvat@westcoastwound.com',
    reason: 'Address is incomplete, so the demo routes this case for manual review',
  },
  'maria-alvarez': {
    name: 'Donessa Ruiz',
    email: 'druiz@westcoastwound.com',
    reason: 'Demo routing match for the Riverside service area',
  },
  'james-carter': {
    name: 'Carla Bustillo',
    email: 'cbustillo@westcoastwound.com',
    reason: 'Demo routing match for the South Bay service area',
  },
  'george-chen': {
    name: 'Carla Bustillo',
    email: 'cbustillo@westcoastwound.com',
    reason: 'Demo routing match for the Coastal Los Angeles service area',
  },
  'linda-nguyen': {
    name: 'Nicole Chorvat',
    email: 'nchorvat@westcoastwound.com',
    reason: 'Demo routing match for the Coastal Los Angeles service area',
  },
  'irene-cho': {
    name: 'Michelle Lagahit',
    email: 'mlagahit@westcoastwound.com',
    reason: 'Demo routing match for hospice follow-up',
  },
  'gonzalez-eric': {
    name: 'Carla Bustillo',
    email: 'cbustillo@westcoastwound.com',
    reason: 'Demo routing match',
  },
  'rodriguez-anita': {
    name: 'Carla Bustillo',
    email: 'cbustillo@westcoastwound.com',
    reason: 'Demo routing match',
  },
  'sardina-frank': {
    name: 'Donessa Ruiz',
    email: 'druiz@westcoastwound.com',
    reason: 'Demo routing match',
  },
  'fay-william': {
    name: 'Cole Winfield',
    email: 'cwinfield@westcoastwound.com',
    reason: 'Demo routing match',
  },
  'eliut-cruz-pagan': {
    name: 'Nicole Chorvat',
    email: 'nchorvat@westcoastwound.com',
    reason: 'Demo routing match',
  },
  'zadran-khojagul': {
    name: 'Braxton Rickert',
    email: 'brickert@westcoastwound.com',
    reason: 'Demo routing match',
  },
}

export function caseManagerSuggestion(
  patientId: string,
): CaseManagerSuggestion {
  return SUGGESTIONS[patientId] ?? {
    ...CASE_MANAGER_OPTIONS[0],
    reason: 'Demo default because no verified territory mapping is available',
  }
}

const PATIENT_DETAILS: Record<
  string,
  {
    dob: string
    phone: string
    address: string
    agency: string
    clinical: string
    insurance: string
  }
> = {
  'marcus-feldman': {
    dob: '1961-02-14',
    phone: '(310) 555-0184',
    address: '1428 W 162nd St, Gardena, CA 90247',
    agency: 'South Bay Home Health',
    clinical: 'Lower-extremity wound requiring skilled wound-care evaluation',
    insurance: 'Medicare · member information verified',
  },
  'david-ruiz': {
    dob: '1958-09-22',
    phone: '(424) 555-0127',
    address: '8912 S Sepulveda Blvd, Los Angeles, CA 90045',
    agency: 'Coastal Care Home Health',
    clinical: 'Chronic lower-leg wound requiring provider review',
    insurance: 'Medicare Advantage · eligibility verified',
  },
  'patricia-johnson': {
    dob: '1949-06-08',
    phone: '(310) 555-0162',
    address: '1704 W 147th St, Gardena, CA 90247',
    agency: 'Healing Hands Home Health',
    clinical: 'Pressure injury requiring continued skilled wound care',
    insurance: 'Medicare · policy verified',
  },
  'thomas-reed': {
    dob: '1955-11-30',
    phone: '(951) 555-0143',
    address: '4185 Market St, Riverside, CA 92501',
    agency: 'Riverside Community Home Health',
    clinical: 'Diabetic foot wound requiring initial evaluation',
    insurance: 'Medicare · policy verified',
  },
  'helen-park': {
    dob: '1947-03-19',
    phone: '(310) 555-0196',
    address: '22925 S Vermont Ave, Torrance, CA 90502',
    agency: 'South Bay Home Health',
    clinical: 'Post-surgical wound requiring follow-up care',
    insurance: 'Medicare Advantage · eligibility verified',
  },
  'betty-hayes': {
    dob: '1952-07-11',
    phone: '(323) 555-0135',
    address: 'Address incomplete — confirmation required',
    agency: 'Golden State Hospice',
    clinical: 'Sacral wound requiring hospice-aligned wound-care review',
    insurance: 'Medicare · policy verified',
  },
  'maria-alvarez': {
    dob: '1954-04-18',
    phone: '(951) 555-0178',
    address: '6721 Magnolia Ave, Riverside, CA 92506',
    agency: 'Riverside Community Home Health',
    clinical: 'Lower-extremity wound requiring skilled evaluation',
    insurance: 'Medicare · policy verified',
  },
  'james-carter': {
    dob: '1963-01-27',
    phone: '(310) 555-0118',
    address: '1942 W 156th St, Gardena, CA 90249',
    agency: 'South Bay Home Health',
    clinical: 'Lower-leg wound requiring skilled wound-care evaluation',
    insurance: 'Medicare Advantage · eligibility verified',
  },
  'linda-nguyen': {
    dob: '1950-08-05',
    phone: '(424) 555-0189',
    address: '7320 W Manchester Ave, Los Angeles, CA 90045',
    agency: 'Coastal Care Home Health',
    clinical: 'Post-surgical wound requiring continued skilled care',
    insurance: 'Medicare · policy verified',
  },
  'irene-cho': {
    dob: '1946-12-09',
    phone: '(323) 555-0151',
    address: '421 S Kingsley Dr, Los Angeles, CA 90020',
    agency: 'Golden State Hospice',
    clinical: 'Pressure injury requiring hospice-aligned wound-care review',
    insurance: 'Medicare · policy verified',
  },
}

export interface ReferralPatientSummary {
  name: string
  dateOfBirth: string
  location: string
  phone: string
}

export function referralPatientSummary(
  patientId: string,
  patientName: string,
  canonical?: CanonicalReferral,
): ReferralPatientSummary {
  const fallbackLocation = providerPatientLocationDisplay(patientId)
  const locationFromDisplay =
    fallbackLocation !== 'Location unavailable' ? fallbackLocation : undefined

  if (canonical) {
    return {
      name: patientName,
      dateOfBirth: canonical.patient.date_of_birth ?? 'Not documented',
      location:
        locationFromDisplay ??
        (patientAddressLine(canonical.patient) || 'Not documented'),
      phone: canonical.patient.phones[0]?.number ?? 'Not documented',
    }
  }

  const details = PATIENT_DETAILS[patientId] ?? {
    dob: 'Not documented',
    phone: 'Not documented',
    address: 'Not documented',
    agency: 'Not documented',
    clinical: 'Review referral in the secure platform',
    insurance: 'Not documented',
  }

  return {
    name: patientName,
    dateOfBirth: details.dob,
    location: locationFromDisplay ?? details.address,
    phone: details.phone,
  }
}

export function caseManagerNotification(
  patientId: string,
  patientName: string,
  manager: CaseManagerOption,
): CaseManagerNotification {
  const details = PATIENT_DETAILS[patientId] ?? {
    dob: 'Not documented',
    phone: 'Not documented',
    address: 'Not documented',
    agency: 'Not documented',
    clinical: 'Review referral in the secure platform',
    insurance: 'Not documented',
  }

  return {
    managerName: manager.name,
    managerEmail: manager.email,
    subject: `New case assigned — ${patientName}`,
    message: `A new referral for ${patientName} has been assigned to you. Review the referral and clinical documents in the secure platform, then confirm receipt.`,
    patientFields: [
      { label: 'Patient name', value: patientName },
      { label: 'Date of birth', value: details.dob },
      { label: 'Contact number', value: details.phone },
      { label: 'Patient address', value: details.address },
      { label: 'Home health or hospice agency', value: details.agency },
      { label: 'Wound or clinical information', value: details.clinical },
      { label: 'Insurance information', value: details.insurance },
    ],
  }
}

const REFERRAL_SOURCE_EMAILS: Record<string, string> = {
  'maria-alvarez': 'referrals@riversidecommunityhh.com',
  'james-carter': 'intake@southbayhomehealth.com',
  'linda-nguyen': 'referrals@coastalcarehh.com',
  'patricia-johnson': 'referrals@healinghandshh.com',
  'thomas-reed': 'intake@riversidecommunityhh.com',
  'irene-cho': 'referrals@goldenstatehospice.org',
  'helen-park': 'referrals@southbayhomehealth.com',
}

export function referralSourceNotification(
  patientId: string,
  patientName: string,
  canonical?: CanonicalReferral,
): ReferralSourceNotification {
  const manager = caseManagerSuggestion(patientId)
  return {
    to:
      canonical?.referral_source.organization.email ??
      canonical?.source.sent_by ??
      REFERRAL_SOURCE_EMAILS[patientId] ??
      'Not documented',
    ccName: manager.name,
    ccEmail: manager.email,
    subject: `Case manager assigned — ${patientName}`,
    body: `Hello, this confirms that ${patientName} has been assigned to ${manager.name} at West Coast Wound. The assigned case manager is copied on this email and will coordinate the next steps for the referral.`,
  }
}

export function mondayRecordForPatient(
  patientId: string,
  patientName: string,
  canonical?: CanonicalReferral,
): MondayRecord {
  const details = PATIENT_DETAILS[patientId] ?? {
    dob: 'Not documented',
    phone: 'Not documented',
    address: 'Not documented',
    agency: 'Not documented',
    clinical: 'Review referral in the secure platform',
    insurance: 'Not documented',
  }
  const manager = caseManagerSuggestion(patientId)
  const sourceEmail =
    canonical?.referral_source.organization.email ??
    canonical?.source.sent_by ??
    REFERRAL_SOURCE_EMAILS[patientId] ??
    'Not documented'

  if (canonical) {
    return {
      itemId: canonical.referral_id,
      board: 'Monday.com Master Sheet',
      data: {
        patient_name: patientName,
        date_of_birth: canonical.patient.date_of_birth ?? 'Not documented',
        contact_number:
          canonical.patient.phones[0]?.number ?? 'Not documented',
        patient_address:
          patientAddressLine(canonical.patient) || 'Not documented',
        home_health_or_hospice_agency:
          canonical.home_health_or_hospice.organization.name ??
          'Not documented',
        wound_or_clinical_information:
          canonical.clinical.summary ?? 'Not documented',
        insurance_information:
          formatInsuranceList(canonical.insurances) || 'Not documented',
        case_manager: {
          name: manager.name,
          email: manager.email,
        },
        sent_by: sourceEmail,
        referral_status: 'Assigned',
      },
    }
  }

  return {
    itemId: `WCW-${patientId.toUpperCase()}`,
    board: 'Monday.com Master Sheet',
    data: {
      patient_name: patientName,
      date_of_birth: details.dob,
      contact_number: details.phone,
      patient_address: details.address,
      home_health_or_hospice_agency: details.agency,
      wound_or_clinical_information: details.clinical,
      insurance_information: details.insurance,
      case_manager: {
        name: manager.name,
        email: manager.email,
      },
      sent_by:
        REFERRAL_SOURCE_EMAILS[patientId] ??
        'referrals@partner-organization.org',
      referral_status: 'Assigned',
    },
  }
}

const DRK_BLOCKED_PATIENTS = new Set(['james-carter', 'irene-cho'])

export function drkDraftForPatient(
  patientId: string,
  patientName: string,
  canonical?: CanonicalReferral,
): DrkDraftRecord {
  const details = PATIENT_DETAILS[patientId] ?? {
    dob: 'Not documented',
    phone: 'Not documented',
    address: 'Not documented',
    agency: 'Not documented',
    clinical: 'Review referral in the secure platform',
    insurance: 'Not documented',
  }
  const [firstName = patientName, ...lastNameParts] = patientName.split(' ')
  const blocked = DRK_BLOCKED_PATIENTS.has(patientId)

  if (canonical) {
    const admission = canonical.admission as {
      admission_date?: string | null
      place_of_service?: string | null
      facility?: { name?: string | null } | null
    } | null
    const primaryInsurance = canonical.insurances[0]
    const source =
      canonical.referral_source.organization.email ??
      canonical.referral_source.organization.name ??
      canonical.source.sent_by ??
      'Not documented'

    return {
      demographics: [
        {
          label: 'First name',
          value: canonical.patient.name.first ?? 'Not documented',
        },
        {
          label: 'Last name',
          value: canonical.patient.name.last ?? 'Not documented',
        },
        {
          label: 'Date of birth',
          value: canonical.patient.date_of_birth ?? 'Not documented',
        },
        {
          label: 'Gender',
          value: canonical.patient.sex_or_gender ?? 'Not documented',
        },
      ],
      primaryAddress: [
        {
          label: 'Address',
          value: patientAddressLine(canonical.patient) || 'Not documented',
        },
        {
          label: 'Country',
          value: canonical.patient.address.country ?? 'United States',
        },
      ],
      contact: [
        {
          label: 'Primary phone',
          value: canonical.patient.phones[0]?.number ?? 'Not documented',
        },
        {
          label: 'Email',
          value: canonical.patient.email ?? 'Not documented',
        },
      ],
      admission: [
        {
          label: 'Admission date',
          value: admission?.admission_date ?? 'Not documented',
        },
        {
          label: 'Place of service query',
          value: admission?.place_of_service ?? 'Not documented',
        },
        {
          label: 'Facility query',
          value: admission?.facility?.name ?? 'Not documented',
        },
        {
          label: 'Home health query',
          value:
            canonical.home_health_or_hospice.organization.name ??
            'Not documented',
        },
      ],
      referral: [
        { label: 'Referral source', value: source },
        {
          label: 'Referral date',
          value:
            canonical.referral_source.referral_or_order_date ??
            'Not documented',
        },
        {
          label: 'Referring provider',
          value:
            canonical.referral_source.provider_name ?? 'Not documented',
        },
        {
          label: 'Clinical information',
          value: canonical.clinical.summary ?? 'Not documented',
        },
      ],
      insurance: [
        {
          label: 'Payer query',
          value: primaryInsurance?.payer_name ?? 'Not documented',
        },
        {
          label: 'Insurance type',
          value: primaryInsurance?.insurance_type ?? 'Not documented',
        },
        {
          label: 'Policy number',
          value: primaryInsurance?.policy_number ?? 'Not documented',
        },
      ],
      readyForFill: true,
      blockers: [],
      warnings: canonical.warnings,
    }
  }

  return {
    demographics: [
      { label: 'First name', value: firstName.toUpperCase() },
      {
        label: 'Last name',
        value: (lastNameParts.join(' ') || 'Not documented').toUpperCase(),
      },
      { label: 'Date of birth', value: details.dob },
      { label: 'Gender', value: 'Not documented' },
    ],
    primaryAddress: [
      { label: 'Address', value: details.address },
      { label: 'Country', value: 'United States' },
    ],
    contact: [
      { label: 'Primary phone', value: details.phone },
      { label: 'Email', value: 'Not documented' },
    ],
    admission: [
      { label: 'Admission date', value: 'Not documented' },
      {
        label: 'Facility query',
        value: blocked ? 'Exact DRK facility match required' : details.agency,
      },
      { label: 'Home health query', value: details.agency },
      { label: 'Provider query', value: 'Pending provider selection' },
    ],
    referral: [
      {
        label: 'Referral source',
        value:
          REFERRAL_SOURCE_EMAILS[patientId] ??
          'referrals@partner-organization.org',
      },
      { label: 'Referral date', value: '2026-08-10' },
      { label: 'Clinical information', value: details.clinical },
    ],
    insurance: [
      {
        label: 'Payer query',
        value: details.insurance.split(' · ')[0] ?? details.insurance,
      },
      { label: 'Insurance type', value: 'Primary' },
      {
        label: 'Verification',
        value: details.insurance.includes('verified')
          ? 'Verified from referral'
          : 'Pending verification',
      },
    ],
    readyForFill: !blocked,
    blockers: blocked
      ? [
          'Admission facility requires an exact DRK catalog match',
          'Possible patient identity match requires review',
        ]
      : [],
    warnings: [
      'Provider remains pending until the Provider Selection stage.',
    ],
  }
}

export function mondayRecordWithAssignedProvider(
  record: MondayRecord,
  provider: AssignedProviderRecord,
  referralStatus = 'Provider confirmed',
): MondayRecord {
  return {
    ...record,
    data: {
      ...record.data,
      assigned_provider: provider.name,
      provider_npi: provider.npi ?? 'Not documented',
      provider_city: provider.city ?? 'Not documented',
      referral_status: referralStatus,
    },
  }
}

function upsertLabeledValue(
  fields: Array<{ label: string; value: string }>,
  label: string,
  value: string,
) {
  const next = fields.filter((field) => field.label !== label)
  next.push({ label, value })
  return next
}

export function drkDraftWithAssignedProvider(
  draft: DrkDraftRecord,
  provider: AssignedProviderRecord,
): DrkDraftRecord {
  return {
    ...draft,
    admission: upsertLabeledValue(
      draft.admission,
      'Provider query',
      provider.name,
    ),
    referral: [
      ...draft.referral.filter(
        (field) =>
          field.label !== 'Assigned provider' && field.label !== 'Provider NPI',
      ),
      { label: 'Assigned provider', value: provider.name },
      { label: 'Provider NPI', value: provider.npi ?? 'Not documented' },
    ],
    warnings: draft.warnings.filter(
      (warning) => !/provider remains pending/i.test(warning),
    ),
  }
}
