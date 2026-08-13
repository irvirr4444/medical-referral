import type {
  CanonicalAdmission,
  CanonicalAllergy,
  CanonicalDiagnosis,
  CanonicalEmergencyContact,
  CanonicalInsurance,
  CanonicalMedication,
  CanonicalName,
  CanonicalOrganization,
  CanonicalPhone,
  CanonicalReferral,
  CanonicalRequestedService,
} from './canonicalReferral'
import type { ArtifactAddKind, ArtifactField, ArtifactSection } from './types'

export const INSURANCE_TYPES = [
  'Primary',
  'Secondary',
  'Tertiary',
  'Other',
] as const

export const YES_NO_OPTIONS = ['Yes', 'No'] as const

export function displayCanonicalValue(value: unknown): string {
  if (value === true) return 'Yes'
  if (value === false) return 'No'
  if (value === null || value === undefined) return '—'
  return String(value)
}

export function nextInsuranceType(existingTypes: string[]): string {
  const used = new Set(existingTypes.filter(Boolean))
  return INSURANCE_TYPES.find((type) => !used.has(type)) ?? 'Other'
}

function nextNumberedLabel(prefix: string, labels: string[]): string {
  const used = new Set(
    labels.flatMap((label) => {
      const match = label.match(new RegExp(`^${prefix} (\\d+)$`, 'i'))
      return match ? [Number(match[1])] : []
    }),
  )
  let n = labels.length + 1
  while (used.has(n)) n += 1
  return `${prefix} ${n}`
}

function newRowId(sectionId: string): string {
  return `${sectionId}.new-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

function field(
  rowId: string,
  label: string,
  value: unknown,
  extra: Partial<ArtifactField> = {},
): ArtifactField {
  return {
    label,
    value: displayCanonicalValue(value),
    rowId,
    ...extra,
  }
}

export function groupRepeatableFields(fields: ArtifactField[]): {
  fixed: ArtifactField[]
  records: ArtifactField[][]
} {
  const fixed = fields.filter((item) => item.fixed)
  const order: string[] = []
  const grouped = new Map<string, ArtifactField[]>()
  fields
    .filter((item) => !item.fixed)
    .forEach((item, index) => {
      const id = item.rowId ?? `solo-${item.label}-${index}`
      if (!grouped.has(id)) {
        order.push(id)
        grouped.set(id, [])
      }
      grouped.get(id)!.push(item)
    })
  return { fixed, records: order.map((id) => grouped.get(id)!) }
}

export function repeatableItemCount(section: ArtifactSection): number {
  return groupRepeatableFields(section.fields).records.length
}

export function sectionCountLabel(section: ArtifactSection): string {
  if (!section.repeatable) return `${section.fields.length} fields`
  const count = repeatableItemCount(section)
  return count === 1 ? '1 item' : `${count} items`
}

export function listRecordsFilled(rows: ArtifactField[]): boolean {
  const { fixed, records } = groupRepeatableFields(rows)
  if (
    fixed.some(
      (item) =>
        item.presence &&
        item.value === 'Yes',
    )
  ) {
    return true
  }
  return records.some((record) =>
    record.some((item) => item.presence && item.value.trim() !== '' && item.value !== '—'),
  )
}

export function organizationFields(
  org: CanonicalOrganization,
  pathPrefix: string,
  options: { nameRequired?: boolean } = {},
): ArtifactField[] {
  return [
    {
      label: 'Name',
      value: displayCanonicalValue(org.name),
      fieldPath: `${pathPrefix}.name`,
      required: options.nameRequired,
    },
    {
      label: 'Contact',
      value: displayCanonicalValue(org.contact_name),
      fieldPath: `${pathPrefix}.contact_name`,
    },
    {
      label: 'Phone',
      value: displayCanonicalValue(org.phone),
      fieldPath: `${pathPrefix}.phone`,
    },
    {
      label: 'Fax',
      value: displayCanonicalValue(org.fax),
      fieldPath: `${pathPrefix}.fax`,
    },
    {
      label: 'Email',
      value: displayCanonicalValue(org.email),
      fieldPath: `${pathPrefix}.email`,
    },
    {
      label: 'Address',
      value: displayCanonicalValue(org.address),
      fieldPath: `${pathPrefix}.address`,
    },
  ]
}

function contactName(name: CanonicalName | undefined): string {
  if (!name) return '—'
  return (
    name.full ??
    [name.first, name.middle, name.last, name.suffix].filter(Boolean).join(' ') ??
    '—'
  )
}

export function emergencyContactFields(
  contact: CanonicalEmergencyContact | null,
): ArtifactField[] {
  return [
    {
      label: 'Name',
      value: contactName(contact?.name),
      fieldPath: 'patient.emergency_contact.name',
    },
    {
      label: 'Relationship',
      value: displayCanonicalValue(contact?.relationship ?? null),
      fieldPath: 'patient.emergency_contact.relationship',
    },
    {
      label: 'Phone',
      value: displayCanonicalValue(contact?.phone ?? null),
      fieldPath: 'patient.emergency_contact.phone',
    },
  ]
}

export function admissionFields(admission: CanonicalAdmission): ArtifactField[] {
  return [
    {
      label: 'Admission date',
      value: displayCanonicalValue(admission.admission_date),
      fieldPath: 'admission.admission_date',
    },
    ...organizationFields(admission.facility, 'admission.facility'),
    {
      label: 'Place of service',
      value: displayCanonicalValue(admission.place_of_service),
      fieldPath: 'admission.place_of_service',
    },
    {
      label: 'Medicare admission',
      value: displayCanonicalValue(admission.medicare_admission),
      fieldPath: 'admission.medicare_admission',
      choice: 'yesno',
    },
  ]
}

export function phoneFields(item: CanonicalPhone, index: number): ArtifactField[] {
  const rowId = `phones.${index}`
  return [
    field(rowId, 'Number', item.number, {
      fieldPath: `patient.phones.${index}.number`,
      presence: true,
      required: true,
    }),
    field(rowId, 'Type', item.type, {
      fieldPath: `patient.phones.${index}.type`,
    }),
  ]
}

export function diagnosisFields(
  item: CanonicalDiagnosis,
  index: number,
): ArtifactField[] {
  const rowId = `diagnoses.${index}`
  const prefix = `clinical.diagnoses.${index}`
  return [
    field(rowId, 'Code', item.code, { fieldPath: `${prefix}.code`, presence: true }),
    field(rowId, 'Description', item.description, {
      fieldPath: `${prefix}.description`,
      presence: true,
    }),
    field(rowId, 'Added date', item.added_date, {
      fieldPath: `${prefix}.added_date`,
    }),
    field(rowId, 'Primary', item.is_primary, {
      fieldPath: `${prefix}.is_primary`,
      choice: 'yesno',
    }),
    field(rowId, 'Status', item.status, { fieldPath: `${prefix}.status` }),
  ]
}

export function medicationFields(
  item: CanonicalMedication,
  index: number,
): ArtifactField[] {
  const rowId = `medications.${index}`
  const prefix = `clinical.medications.${index}`
  return [
    field(rowId, 'Name', item.name, { fieldPath: `${prefix}.name`, presence: true }),
    field(rowId, 'Strength', item.strength, { fieldPath: `${prefix}.strength` }),
    field(rowId, 'Dose form', item.dose_form, { fieldPath: `${prefix}.dose_form` }),
    field(rowId, 'Directions', item.directions, {
      fieldPath: `${prefix}.directions`,
    }),
    field(rowId, 'Status', item.status, { fieldPath: `${prefix}.status` }),
    field(rowId, 'Prescribed date', item.prescribed_date, {
      fieldPath: `${prefix}.prescribed_date`,
    }),
    field(rowId, 'Prescriber', item.prescriber, {
      fieldPath: `${prefix}.prescriber`,
    }),
    field(rowId, 'Days supply', item.days_supply, {
      fieldPath: `${prefix}.days_supply`,
    }),
    field(rowId, 'Quantity', item.quantity, { fieldPath: `${prefix}.quantity` }),
    field(rowId, 'Refills', item.refills, { fieldPath: `${prefix}.refills` }),
  ]
}

export function allergyFlagFields(record: CanonicalReferral): ArtifactField[] {
  return [
    {
      label: 'No known allergies',
      value: displayCanonicalValue(record.clinical.no_known_allergies_explicit),
      fieldPath: 'clinical.no_known_allergies_explicit',
      rowId: 'allergies.nka',
      fixed: true,
      presence: true,
      choice: 'yesno',
    },
  ]
}

export function allergyFields(item: CanonicalAllergy, index: number): ArtifactField[] {
  const rowId = `allergies.${index}`
  const prefix = `clinical.allergies.${index}`
  return [
    field(rowId, 'Name', item.name, { fieldPath: `${prefix}.name`, presence: true }),
    field(rowId, 'Reaction', item.reaction, { fieldPath: `${prefix}.reaction` }),
    field(rowId, 'Treatment', item.treatment, { fieldPath: `${prefix}.treatment` }),
    field(rowId, 'Status', item.status, { fieldPath: `${prefix}.status` }),
  ]
}

export function noteFields(note: string, index: number): ArtifactField[] {
  const rowId = `notes.${index}`
  return [
    field(rowId, `Note ${index + 1}`, note, {
      fieldPath: `clinical.notes.${index}`,
      presence: true,
    }),
  ]
}

export function insuranceFields(
  item: CanonicalInsurance,
  index: number,
): ArtifactField[] {
  const rowId = `insurances.${index}`
  const prefix = `insurances.${index}`
  return [
    field(rowId, 'Type', item.insurance_type, {
      fieldPath: `${prefix}.insurance_type`,
      choice: 'insurance-type',
    }),
    field(rowId, 'Payer', item.payer_name, {
      fieldPath: `${prefix}.payer_name`,
      presence: true,
    }),
    field(rowId, 'Policy number', item.policy_number, {
      fieldPath: `${prefix}.policy_number`,
      presence: true,
    }),
    field(rowId, 'Group number', item.group_number, {
      fieldPath: `${prefix}.group_number`,
    }),
    field(rowId, 'Group name', item.group_name, {
      fieldPath: `${prefix}.group_name`,
    }),
    field(rowId, 'Policy holder', item.policy_holder_name, {
      fieldPath: `${prefix}.policy_holder_name`,
    }),
    field(rowId, 'Effective date', item.effective_date, {
      fieldPath: `${prefix}.effective_date`,
    }),
    field(rowId, 'Expiration date', item.expiration_date, {
      fieldPath: `${prefix}.expiration_date`,
    }),
    field(rowId, 'Patient is policy holder', item.is_patient_policy_holder, {
      fieldPath: `${prefix}.is_patient_policy_holder`,
      choice: 'yesno',
    }),
    field(rowId, 'Subscriber first name', item.subscriber_first_name, {
      fieldPath: `${prefix}.subscriber_first_name`,
    }),
    field(rowId, 'Subscriber last name', item.subscriber_last_name, {
      fieldPath: `${prefix}.subscriber_last_name`,
    }),
    field(rowId, 'Subscriber date of birth', item.subscriber_date_of_birth, {
      fieldPath: `${prefix}.subscriber_date_of_birth`,
    }),
    field(rowId, 'Subscriber relationship', item.subscriber_relationship, {
      fieldPath: `${prefix}.subscriber_relationship`,
    }),
  ]
}

export function serviceFields(
  item: CanonicalRequestedService,
  index: number,
): ArtifactField[] {
  const rowId = `services.${index}`
  const prefix = `requested_services.${index}`
  return [
    field(rowId, 'Service', item.service, {
      fieldPath: `${prefix}.service`,
      presence: true,
    }),
    field(rowId, 'Frequency', item.frequency, { fieldPath: `${prefix}.frequency` }),
    field(rowId, 'Instructions', item.instructions, {
      fieldPath: `${prefix}.instructions`,
    }),
  ]
}

export function warningFields(warning: string, index: number): ArtifactField[] {
  const rowId = `warnings.${index}`
  return [
    field(rowId, `Warning ${index + 1}`, warning, {
      fieldPath: `warnings.${index}`,
      presence: true,
    }),
  ]
}

export function addKindLabel(kind: ArtifactAddKind | undefined): string {
  switch (kind) {
    case 'phone':
      return 'Add phone'
    case 'diagnosis':
      return 'Add diagnosis'
    case 'medication':
      return 'Add medication'
    case 'allergy':
      return 'Add allergy'
    case 'note':
      return 'Add note'
    case 'insurance':
      return 'Add insurance policy'
    case 'service':
      return 'Add requested service'
    case 'warning':
      return 'Add warning'
    default:
      return 'Add field'
  }
}

export function createRepeatableFields(section: ArtifactSection): ArtifactField[] {
  const rowId = newRowId(section.id)
  const kind: ArtifactAddKind = section.addKind ?? 'guard'
  if (kind === 'phone') {
    return [
      field(rowId, 'Number', '', { presence: true, required: true }),
      field(rowId, 'Type', ''),
    ]
  }
  if (kind === 'diagnosis') {
    return [
      field(rowId, 'Code', '', { presence: true }),
      field(rowId, 'Description', '', { presence: true }),
      field(rowId, 'Added date', ''),
      field(rowId, 'Primary', '', { choice: 'yesno' }),
      field(rowId, 'Status', ''),
    ]
  }
  if (kind === 'medication') {
    return [
      field(rowId, 'Name', '', { presence: true }),
      field(rowId, 'Strength', ''),
      field(rowId, 'Dose form', ''),
      field(rowId, 'Directions', ''),
      field(rowId, 'Status', ''),
      field(rowId, 'Prescribed date', ''),
      field(rowId, 'Prescriber', ''),
      field(rowId, 'Days supply', ''),
      field(rowId, 'Quantity', ''),
      field(rowId, 'Refills', ''),
    ]
  }
  if (kind === 'allergy') {
    return [
      field(rowId, 'Name', '', { presence: true }),
      field(rowId, 'Reaction', ''),
      field(rowId, 'Treatment', ''),
      field(rowId, 'Status', ''),
    ]
  }
  if (kind === 'insurance') {
    const types = section.fields
      .filter((item) => item.label === 'Type')
      .map((item) => item.value)
    return [
      field(rowId, 'Type', nextInsuranceType(types), { choice: 'insurance-type' }),
      field(rowId, 'Payer', '', { presence: true }),
      field(rowId, 'Policy number', '', { presence: true }),
      field(rowId, 'Group number', ''),
      field(rowId, 'Group name', ''),
      field(rowId, 'Policy holder', ''),
      field(rowId, 'Effective date', ''),
      field(rowId, 'Expiration date', ''),
      field(rowId, 'Patient is policy holder', '', { choice: 'yesno' }),
      field(rowId, 'Subscriber first name', ''),
      field(rowId, 'Subscriber last name', ''),
      field(rowId, 'Subscriber date of birth', ''),
      field(rowId, 'Subscriber relationship', ''),
    ]
  }
  if (kind === 'service') {
    return [
      field(rowId, 'Service', '', { presence: true }),
      field(rowId, 'Frequency', ''),
      field(rowId, 'Instructions', ''),
    ]
  }
  if (kind === 'note') {
    const labels = section.fields.filter((item) => !item.fixed).map((item) => item.label)
    return [
      field(rowId, nextNumberedLabel('Note', labels), '', { presence: true }),
    ]
  }
  if (kind === 'warning') {
    const labels = section.fields.map((item) => item.label)
    return [
      field(rowId, nextNumberedLabel('Warning', labels), '', { presence: true }),
    ]
  }
  return [field(rowId, '', '', { presence: true })]
}
