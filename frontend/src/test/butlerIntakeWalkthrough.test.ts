import { describe, expect, it } from 'vitest'
import {
  BUTLER_INTAKE_SNAPSHOTS,
  BUTLER_INTAKE_STEP_IDS,
} from '../features/automation/fixtures/butlerIntakeSnapshots'
import { BUTLER_RUN_FIXTURE } from '../features/automation/types'
import {
  AUTOMATION_RUNS,
  exampleForRun,
} from '../features/automation/runFixtures'
import { automationStage } from '../features/automation/stages'

describe('Butler intake walkthrough fixtures', () => {
  it('defines all 13 intake snapshots with unique artifact IDs', () => {
    expect(BUTLER_INTAKE_STEP_IDS).toHaveLength(13)
    expect(Object.keys(BUTLER_INTAKE_SNAPSHOTS).sort()).toEqual(
      [...BUTLER_INTAKE_STEP_IDS].sort(),
    )

    const artifactIds = Object.values(BUTLER_INTAKE_SNAPSHOTS).map(
      (snapshot) => snapshot.artifactId,
    )
    expect(new Set(artifactIds).size).toBe(13)
  })

  it('progressively reveals Butler identity and extraction output', () => {
    const discover = BUTLER_INTAKE_SNAPSHOTS['discover-email']
    const extract = BUTLER_INTAKE_SNAPSHOTS['extract-referral']
    const verify = BUTLER_INTAKE_SNAPSHOTS['verify-required-fields']

    expect(discover.knownAtThisPoint.map((item) => item.label)).not.toContain(
      'Date of birth',
    )
    expect(extract.knownAtThisPoint.map((item) => item.label)).toContain(
      'Date of birth',
    )
    expect(extract.artifactSections.some((section) => section.id === 'demographics')).toBe(
      true,
    )
    expect(
      verify.artifactSections[0]?.fields.some((field) =>
        field.label.includes('Home health'),
      ),
    ).toBe(true)
  })

  it('preserves source patient ID separately from MRN in extraction output', () => {
    const demographics = BUTLER_INTAKE_SNAPSHOTS['extract-referral'].artifactSections.find(
      (section) => section.id === 'demographics',
    )
    const sourceId = demographics?.fields.find((field) =>
      field.label.includes('Source patient ID'),
    )
    const mrn = demographics?.fields.find((field) => field.label === 'MRN')

    expect(sourceId?.value).toBe('6227')
    expect(mrn?.value).toMatch(/Not documented/)
  })

  it('uses Butler snapshots when the Butler run is selected on intake', () => {
    const stage = automationStage('intake')
    const extractStep = stage.microsteps.find((step) => step.id === 'extract-referral')!
    const example = exampleForRun(BUTLER_RUN_FIXTURE, extractStep, stage.id)

    expect(example.patientName).toBe('BUTLER, ALVA')
    expect(example.artifactTitle).toBe('Canonical referral extraction')
    expect(example.artifactSections?.length).toBeGreaterThan(3)
  })

  it('defaults the automation run list to Butler first', () => {
    expect(AUTOMATION_RUNS[0].id).toBe('butler-alva')
    expect(AUTOMATION_RUNS[0].referralId).toBe('ref_demo_butler_alva_001')
  })
})
