import { describe, expect, it } from 'vitest'
import {
  BUTLER_INTAKE_SNAPSHOTS,
  BUTLER_INTAKE_STEP_IDS,
} from '../features/automation/fixtures/butlerIntakeSnapshots'
import { lifecycleHistoryForStep } from '../features/automation/fixtures/lifecycleHistory'
import { BUTLER_RUN_FIXTURE } from '../features/automation/types'
import {
  AUTOMATION_RUNS,
  exampleForRun,
} from '../features/automation/runFixtures'
import { automationStage } from '../features/automation/stages'

describe('Butler intake walkthrough fixtures', () => {
  it('defines all 6 intake snapshots with unique artifact IDs', () => {
    expect(BUTLER_INTAKE_STEP_IDS).toHaveLength(6)
    expect(Object.keys(BUTLER_INTAKE_SNAPSHOTS).sort()).toEqual(
      [...BUTLER_INTAKE_STEP_IDS].sort(),
    )

    const artifactIds = Object.values(BUTLER_INTAKE_SNAPSHOTS).map(
      (snapshot) => snapshot.artifactId,
    )
    expect(new Set(artifactIds).size).toBe(6)
  })

  it('defines one explicit input and output for every intake step', () => {
    for (const stepId of BUTLER_INTAKE_STEP_IDS) {
      const snapshot = BUTLER_INTAKE_SNAPSHOTS[stepId]
      expect(snapshot.input.trim().length).toBeGreaterThan(0)
      expect(snapshot.output.trim().length).toBeGreaterThan(0)
      expect(snapshot.executedAt).toMatch(/August 10, 2026 at/)
    }
  })

  it('keeps step-scoped input and output free of premature patient contact data', () => {
    const discover = BUTLER_INTAKE_SNAPSHOTS['receive-referral']
    const extract = BUTLER_INTAKE_SNAPSHOTS['extract-and-verify']

    expect(discover.input).not.toMatch(/1940-10-04/)
    expect(discover.output).not.toMatch(/1940-10-04/)
    expect(extract.input).toMatch(/Valid PDF|PDF/i)
    expect(extract.output).toMatch(/Details extracted/i)
    expect(extract.output).toMatch(/6 of 7|agency missing|threshold/i)
  })

  it('routes intake through a single history entry using snapshot input and output', () => {
    const stage = automationStage('intake')
    const extractStep = stage.microsteps.find(
      (step) => step.id === 'extract-and-verify',
    )!
    const example = exampleForRun(BUTLER_RUN_FIXTURE, extractStep, stage.id)
    const history = lifecycleHistoryForStep(
      stage.id,
      extractStep,
      BUTLER_RUN_FIXTURE,
      example,
    )

    expect(history).toHaveLength(1)
    expect(history[0].input).toBe(
      BUTLER_INTAKE_SNAPSHOTS['extract-and-verify'].input,
    )
    expect(history[0].output).toBe(
      BUTLER_INTAKE_SNAPSHOTS['extract-and-verify'].output,
    )
    expect(history[0].occurredAt).toBe('August 10, 2026 at 9:14 AM')
  })

  it('uses Butler snapshots when the Butler run is selected on intake', () => {
    const stage = automationStage('intake')
    const extractStep = stage.microsteps.find(
      (step) => step.id === 'extract-and-verify',
    )!
    const example = exampleForRun(BUTLER_RUN_FIXTURE, extractStep, stage.id)

    expect(example.patientName).toBe('BUTLER, ALVA')
    expect(example.artifactTitle).toBe(
      'Referral details extracted and verified',
    )
    expect(example.inputs).toEqual([
      {
        label: 'Input received',
        value: BUTLER_INTAKE_SNAPSHOTS['extract-and-verify'].input,
      },
    ])
    expect(example.outputs).toEqual([
      {
        label: 'Output produced',
        value: BUTLER_INTAKE_SNAPSHOTS['extract-and-verify'].output,
      },
    ])
  })

  it('defaults the automation run list to Butler first', () => {
    expect(AUTOMATION_RUNS[0].id).toBe('butler-alva')
    expect(AUTOMATION_RUNS[0].referralId).toBe('ref_demo_butler_alva_001')
  })
})
