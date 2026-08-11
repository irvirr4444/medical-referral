import { describe, expect, it } from 'vitest'
import {
  activityFeedForStage,
  defaultPatientIdForStage,
  detailForPatientStep,
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
      expect(openTotal).toBeGreaterThan(0)
    }
  })

  it('lists Butler, Alva first on intake and selects them by default', () => {
    const patients = patientsForStage('intake')
    expect(patients[0]?.patientId).toBe('butler-alva')
    expect(defaultPatientIdForStage('intake')).toBe('butler-alva')

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

    const rosa = detailForPatientStep('intake', 'rosa-delgado', 'confirm-referral-contacted')
    expect(rosa.example?.patientName).toMatch(/Rosa/i)
    expect(rosa.example?.artifactSections?.[0]?.fields.length).toBeGreaterThan(0)

    const handoffPatient = detailForPatientStep(
      'handoff',
      'james-carter',
      'verify-handoff',
    )
    expect(handoffPatient.example?.artifactSections?.length).toBeGreaterThan(0)
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

  it('uses detailed hero artifacts for each post-intake stage', () => {
    const heroes: Array<[FlowOpsPageId, string, string]> = [
      ['handoff', 'maria-alvarez', 'create-monday-record'],
      ['assignment', 'marcus-feldman', 'determine-owner'],
      ['provider', 'helen-park', 'select-provider'],
      ['scheduling', 'maria-alvarez', 'capture-provider-response'],
      ['end-of-day', 'frank-owens', 'find-unscheduled'],
      ['weekly', 'arthur-kim', 'record-visit-outcome'],
    ]

    for (const [stageId, patientId, stepId] of heroes) {
      expect(defaultPatientIdForStage(stageId)).toBe(patientId)
      const detail = detailForPatientStep(stageId, patientId, stepId)
      expect(detail.example?.artifactSections?.map((section) => section.id)).toEqual([
        'technical-details',
      ])
      expect(detail.example?.actionFields?.length).toBeGreaterThan(0)
    }
  })
})
