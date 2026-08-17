import { REQUIRED_FIELD_PATHS } from './canonicalReferral'
import {
  listRecordsFilled,
} from './intakeRecords'
import type {
  ArtifactField,
  ArtifactSection,
  FeedDecision,
  MicrostepExample,
} from './types'

export {
  INSURANCE_TYPES,
  YES_NO_OPTIONS,
  createRepeatableFields,
  groupRepeatableFields,
  listRecordsFilled,
  repeatableItemCount,
  sectionCountLabel,
} from './intakeRecords'

const EMPTY_VALUES = new Set(['', '—', 'Not documented'])
const MIN_IDENTITY_PATHS = [
  'patient.name',
  'patient.date_of_birth',
  'patient.phones',
  'patient.address',
] as const

export function intakeEditKey(sectionId: string, field: ArtifactField): string {
  return (
    field.fieldPath ??
    (field.rowId ? `${field.rowId}::${field.label}` : `${sectionId}::${field.label}`)
  )
}

export function isFilledIntakeValue(value: string): boolean {
  return !EMPTY_VALUES.has(value.trim())
}

export function isMultilineIntakeField(label: string): boolean {
  return /^(Summary|Description|Directions|Instructions|Note|Warning|Address|Place of service|Document type)/i.test(
    label,
  )
}

function overlayArtifactSections(
  sections: ArtifactSection[],
  edits: Record<string, string>,
): ArtifactSection[] {
  if (Object.keys(edits).length === 0) return sections
  return sections.map((section) => ({
    ...section,
    fields: section.fields.map((field) => {
      const key = intakeEditKey(section.id, field)
      if (!(key in edits)) return field
      return { ...field, value: edits[key] }
    }),
  }))
}

function replaceSectionRows(
  sections: ArtifactSection[],
  sectionRows: Record<string, ArtifactField[]> | undefined,
): ArtifactSection[] {
  if (!sectionRows || Object.keys(sectionRows).length === 0) return sections
  return sections.map((section) =>
    sectionRows[section.id]
      ? { ...section, fields: sectionRows[section.id] }
      : section,
  )
}

function listRowsFilled(rows: ArtifactField[]): boolean {
  return listRecordsFilled(rows)
}

function sectionField(
  sections: ArtifactSection[],
  sectionId: string,
  fieldPath: string,
): ArtifactField | undefined {
  return sections
    .find((section) => section.id === sectionId)
    ?.fields.find((field) => field.fieldPath === fieldPath)
}

function requiredFieldPresent(
  label: string,
  path: string,
  original: FeedDecision,
  edits: Record<string, string>,
  sections: ArtifactSection[],
  sectionRows: Record<string, ArtifactField[]> | undefined,
): boolean {
  const originallyMissing = original.missingLabels.includes(label)
  const originallyUnclear = original.unclearLabels.includes(label)
  if (path === 'insurances' && sectionRows?.insurance) {
    if (listRowsFilled(sectionRows.insurance)) return true
    return !originallyMissing && !originallyUnclear
  }
  if (path === 'patient.phones' && sectionRows?.phones) {
    if (listRowsFilled(sectionRows.phones)) return true
    return !originallyMissing && !originallyUnclear
  }
  if (path === 'home_health_or_hospice') {
    const agency = sectionField(
      sections,
      'home-health',
      'home_health_or_hospice.organization.name',
    )
    if (
      agency &&
      isFilledIntakeValue(agency.value) &&
      'home_health_or_hospice.organization.name' in edits
    ) {
      return true
    }
  }
  if (path === 'clinical') {
    if (sectionRows?.diagnoses && listRowsFilled(sectionRows.diagnoses)) return true
    if (sectionRows?.allergies && listRowsFilled(sectionRows.allergies)) return true
    if (sectionRows?.medications && listRowsFilled(sectionRows.medications)) return true
    const summary = sectionField(sections, 'clinical', 'clinical.summary')
    if (summary && isFilledIntakeValue(summary.value) && 'clinical.summary' in edits) {
      return true
    }
  }
  if (path in edits) {
    if (isFilledIntakeValue(edits[path])) return true
    return !originallyMissing && !originallyUnclear
  }
  return !originallyMissing && !originallyUnclear
}

function recomputeFeedDecision(
  original: FeedDecision,
  sections: ArtifactSection[],
  edits: Record<string, string>,
  sectionRows: Record<string, ArtifactField[]> | undefined,
): FeedDecision {
  const required =
    sections.find((section) => section.id === 'required-fields')?.fields ?? []
  const byPath = new Map(
    required.flatMap((field) =>
      field.fieldPath ? [[field.fieldPath, field] as const] : [],
    ),
  )

  const missingLabels: string[] = []
  const unclearLabels: string[] = []
  let completeCount = 0

  for (const spec of REQUIRED_FIELD_PATHS) {
    const originallyMissing = original.missingLabels.includes(spec.label)
    const originallyUnclear = original.unclearLabels.includes(spec.label)
    if (
      requiredFieldPresent(
        spec.label,
        spec.path,
        original,
        edits,
        sections,
        sectionRows,
      )
    ) {
      completeCount += 1
      continue
    }
    if (originallyMissing) missingLabels.push(spec.label)
    else if (originallyUnclear) unclearLabels.push(spec.label)
  }

  const identityParts = original.identityLine.split(' · ')
  const identityLine = [
    byPath.get('patient.name')?.value ?? identityParts[0] ?? '—',
    byPath.get('patient.date_of_birth')?.value ?? identityParts[1] ?? '—',
    byPath.get('patient.phones')?.value ?? identityParts[2] ?? '—',
  ].join(' · ')

  const thresholdMet = MIN_IDENTITY_PATHS.every((path) => {
    const spec = REQUIRED_FIELD_PATHS.find((item) => item.path === path)
    return spec
      ? requiredFieldPresent(
          spec.label,
          spec.path,
          original,
          edits,
          sections,
          sectionRows,
        )
      : false
  })

  return {
    ...original,
    completeCount,
    totalRequired: REQUIRED_FIELD_PATHS.length,
    missingLabels,
    unclearLabels,
    thresholdMet,
    identityLine,
  }
}

export function overlayIntakeFieldValues(
  sections: ArtifactSection[],
  edits: Record<string, string>,
): ArtifactSection[] {
  return overlayArtifactSections(sections, edits)
}

export function overlayIntakeExample(
  example: MicrostepExample,
  edits: Record<string, string> | undefined,
  sectionRows?: Record<string, ArtifactField[]>,
): MicrostepExample {
  const nextEdits = edits ?? {}
  const artifactSections = overlayArtifactSections(
    replaceSectionRows(example.artifactSections ?? [], sectionRows),
    nextEdits,
  )
  if (!example.feedDecision) {
    return { ...example, artifactSections }
  }
  return {
    ...example,
    artifactSections,
    feedDecision: recomputeFeedDecision(
      example.feedDecision,
      artifactSections,
      nextEdits,
      sectionRows,
    ),
  }
}

export function overlayIntakeDetail<T extends { example?: MicrostepExample }>(
  detail: T,
  edits: Record<string, string> | undefined,
  sectionRows?: Record<string, ArtifactField[]>,
): T {
  if (!detail.example) return detail
  return {
    ...detail,
    example: overlayIntakeExample(detail.example, edits, sectionRows),
  }
}
