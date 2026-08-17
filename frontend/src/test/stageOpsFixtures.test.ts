import { describe, expect, it } from 'vitest'
import {
  activityFeedForStage,
  defaultPatientIdForStage,
  detailForPatientStep,
  feedForStep,
  openEventsForSection,
  opsFixtureForStage,
  opsRecipeForStage,
  PATIENT_OPS_JOURNEYS,
  patientJourneyById,
  patientsForStage,
  STAGE_ORDER,
  stepsForPatient,
} from '../features/automation/ops'
import { PATIENT_STEP_BREAKDOWNS } from '../features/automation/ops/fixtures/patientSteps'
import type { FlowOpsPageId } from '../data/flowOps'

const STAGES: FlowOpsPageId[] = [
  'intake',
  'handoff',
  'assignment',
  'provider',
  'scheduling',
  'end-of-day',
  'weekly',
]

describe('stage operations fixtures', () => {
  it('defines a recipe, events, patients, and step breakdowns for every stage', () => {
    for (const stageId of STAGES) {
      const recipe = opsRecipeForStage(stageId)
      const fixture = opsFixtureForStage(stageId)
      const patients = patientsForStage(stageId)
      const feed = activityFeedForStage(stageId)

      expect(recipe.sections.length).toBeGreaterThan(3)
      expect(fixture.events.length).toBeGreaterThan(5)
      expect(patients.length).toBeGreaterThan(0)
      expect(feed.length).toBeGreaterThan(0)
      expect(feed[0].messages.length).toBeGreaterThan(0)

      for (const patient of patients) {
        const steps = stepsForPatient(stageId, patient.patientId)
        expect(steps.length).toBeGreaterThan(0)
        expect(PATIENT_STEP_BREAKDOWNS[stageId][patient.patientId]).toBeTruthy()
      }

      const openTotal = recipe.sections.reduce(
        (sum, section) =>
          sum + openEventsForSection(stageId, section.id).length,
        0,
      )
      if (stageId === 'handoff') {
        expect(openTotal).toBe(0)
      } else {
        expect(openTotal).toBeGreaterThan(0)
      }
    }
  })

  it('lists Butler first on intake with canonical demo patients', () => {
    const patients = patientsForStage('intake')
    expect(patients[0]?.patientId).toBe('butler-alva')
    expect(defaultPatientIdForStage('intake')).toBe('butler-alva')
    expect(patients.map((patient) => patient.patientId)).toEqual(
      expect.arrayContaining([
        'butler-alva',
        'gonzalez-eric',
        'rodriguez-anita',
        'sardina-frank',
        'fay-william',
        'eliut-cruz-pagan',
        'zadran-khojagul',
      ]),
    )
    expect(patients).toHaveLength(7)

    const rows = openEventsForSection('intake', 'needs-information')
    expect(rows[0]?.patientId).toBe('butler-alva')

    const steps = stepsForPatient('intake', 'butler-alva')
    expect(steps[0]?.summary).toMatch(/Referral email identified/i)
    expect(steps.some((step) => step.status === 'waiting')).toBe(true)

    const detail = detailForPatientStep(
      'intake',
      'butler-alva',
      'confirm-referral-contacted',
    )
    expect(detail.progress?.status).toBe('waiting')
    expect(detail.example?.artifactSections?.length).toBeGreaterThan(0)

    const receive = detailForPatientStep(
      'intake',
      'butler-alva',
      'receive-referral',
    )
    expect(receive.example?.samplePdf).toBe('BUTLER, ALVA demo.pdf')

    const extract = detailForPatientStep(
      'intake',
      'gonzalez-eric',
      'extract-and-verify',
    )
    expect(extract.example?.feedDecision).toEqual(
      expect.objectContaining({
        thresholdMet: false,
        totalRequired: 7,
        unclearLabels: expect.arrayContaining(['Patient address']),
        missingLabels: expect.arrayContaining([
          'Home health or hospice agency',
        ]),
      }),
    )
    expect(extract.example?.feedDecision?.identityLine).toMatch(/Gonzalez/i)
    expect(extract.example?.artifactSections?.[0]?.id).toBe('gate')
    expect(
      extract.example?.artifactSections?.some(
        (section) => section.id === 'required-fields',
      ),
    ).toBe(true)
    expect(
      extract.example?.artifactSections?.map((section) => section.id),
    ).toEqual(
      expect.arrayContaining([
        'phones',
        'emergency-contact',
        'home-health',
        'admission',
        'clinical',
        'diagnoses',
        'medications',
        'allergies',
        'notes',
        'insurance',
        'services',
        'quality',
        'processing-guard',
      ]),
    )
    expect(
      extract.example?.artifactSections?.find(
        (section) => section.id === 'diagnoses',
      ),
    ).toEqual(
      expect.objectContaining({
        repeatable: true,
        addKind: 'diagnosis',
      }),
    )
    expect(
      extract.example?.artifactSections?.find(
        (section) => section.id === 'clinical',
      )?.fields.map((field) => field.label),
    ).toEqual(['Summary', 'Wound order included'])
    expect(
      extract.example?.artifactSections
        ?.find((section) => section.id === 'allergies')
        ?.fields.filter((field) => field.label === 'Name')
        .map((field) => field.value),
    ).toEqual(['Sulfamethoxazole-Trimethoprim'])

    const butlerExtract = detailForPatientStep(
      'intake',
      'butler-alva',
      'extract-and-verify',
    )
    expect(
      butlerExtract.example?.artifactSections
        ?.find((section) => section.id === 'allergies')
        ?.fields,
    ).toEqual([
      expect.objectContaining({
        label: 'No known allergies',
        value: 'Yes',
        rowId: 'allergies.nka',
        fixed: true,
      }),
    ])

    const eric = detailForPatientStep(
      'intake',
      'gonzalez-eric',
      'receive-referral',
    )
    expect(eric.example?.samplePdf).toMatch(/fax20260711-48483-ougwp2\.pdf/)
    expect(eric.example?.artifactSections?.length).toBeGreaterThan(0)

    const handoffPatient = detailForPatientStep(
      'handoff',
      'sardina-frank',
      'create-update-drk',
    )
    expect(handoffPatient.example?.artifactSections?.length).toBeGreaterThan(0)
  })

  it('keeps intake patient step stories aligned to the current steps', () => {
    const butler = stepsForPatient('intake', 'butler-alva')
    expect(butler).toHaveLength(5)
    expect(butler[4]?.status).toBe('waiting')

    const frank = stepsForPatient('intake', 'sardina-frank')
    expect(frank[1]?.status).toBe('blocked')
    expect(frank[1]?.summary).toMatch(/identity\/contact incomplete/i)

    const fay = stepsForPatient('intake', 'fay-william')
    expect(fay.every((step) => step.status === 'done')).toBe(true)
    expect(fay[4]?.summary).toMatch(/Partner contact confirmed/i)
  })

  it('keeps the activity feed newest-first within each day', () => {
    const feed = activityFeedForStage('scheduling')
    for (const day of feed) {
      for (let index = 1; index < day.messages.length; index += 1) {
        const newer = Date.parse(
          day.messages[index - 1].occurredAt.replace(' at ', ' '),
        )
        const older = Date.parse(
          day.messages[index].occurredAt.replace(' at ', ' '),
        )
        expect(newer).toBeGreaterThanOrEqual(older)
      }
    }
  })

  it('builds a newest-first step feed without upcoming patients by default', () => {
    const days = feedForStep('intake', 'receive-referral')
    expect(days.length).toBeGreaterThan(0)
    const rows = days.flatMap((day) => day.rows)
    expect(rows.length).toBeGreaterThan(1)
    expect(rows.some((row) => row.patientId === 'butler-alva')).toBe(true)
    expect(rows.every((row) => row.status !== 'upcoming')).toBe(true)

    for (const day of days) {
      for (let index = 1; index < day.rows.length; index += 1) {
        const newer = day.rows[index - 1].occurredAt
          ? Date.parse(day.rows[index - 1].occurredAt.replace(' at ', ' '))
          : 0
        const older = day.rows[index].occurredAt
          ? Date.parse(day.rows[index].occurredAt.replace(' at ', ' '))
          : 0
        expect(newer).toBeGreaterThanOrEqual(older)
      }
    }

    const waitingOnly = feedForStep('intake', 'confirm-referral-contacted', {
      statuses: ['waiting'],
    })
    const waitingRows = waitingOnly.flatMap((day) => day.rows)
    expect(waitingRows.length).toBeGreaterThan(0)
    expect(waitingRows.every((row) => row.status === 'waiting')).toBe(true)
  })

  it('provides hero patient spines across all seven stages', () => {
    expect(PATIENT_OPS_JOURNEYS.length).toBeGreaterThanOrEqual(3)
    for (const journey of PATIENT_OPS_JOURNEYS) {
      expect(journey.stages).toHaveLength(7)
      expect(journey.stages.map((stage) => stage.stageId)).toEqual(STAGE_ORDER)
      expect(journey.stages.some((stage) => stage.status === 'current')).toBe(
        true,
      )
    }

    const butler = patientJourneyById('butler-alva')
    expect(butler?.currentStageId).toBe('intake')
    expect(butler?.stages[0].outcomes.length).toBeGreaterThan(0)
  })
})
