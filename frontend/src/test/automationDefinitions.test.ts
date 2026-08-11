import { describe, expect, it } from 'vitest'
import {
  AUTOMATION_STAGES,
  automationStage,
} from '../features/automation/stages'
import {
  AUTOMATION_RUNS,
  exampleForRun,
} from '../features/automation/runFixtures'

describe('automation stage definitions', () => {
  it('defines every workflow stage with inspectable microsteps', () => {
    expect(AUTOMATION_STAGES.map((stage) => stage.id)).toEqual([
      'intake',
      'handoff',
      'assignment',
      'provider',
      'scheduling',
      'end-of-day',
      'weekly',
    ])

    for (const stage of AUTOMATION_STAGES) {
      expect(stage.purpose.length).toBeGreaterThan(30)
      expect(stage.trigger.length).toBeGreaterThan(20)
      expect(stage.successDefinition.length).toBeGreaterThan(20)
      expect(stage.microsteps.length).toBeGreaterThanOrEqual(6)

      const ids = stage.microsteps.map((step) => step.id)
      expect(new Set(ids).size).toBe(ids.length)
      for (const step of stage.microsteps) {
        expect(step.description.length).toBeGreaterThan(20)
        expect(step.example.inputs.length).toBeGreaterThan(0)
        expect(step.example.outputs.length).toBeGreaterThan(0)
        expect(step.example.validation.length).toBeGreaterThan(20)
      }
    }
  })

  it('retrieves a stage through the shared lookup', () => {
    expect(automationStage('intake').microsteps[0].id).toBe('receive-referral')
    expect(automationStage('weekly').microsteps.at(-1)?.id).toBe(
      'notify-and-reconcile',
    )
  })

  it('blocks downstream examples when the intake exception run is selected', () => {
    const run = AUTOMATION_RUNS.find(
      (item) => item.id === 'synthetic-exception',
    )!
    const stage = automationStage('assignment')
    const example = exampleForRun(run, stage.microsteps[0], stage.id)

    expect(example.status).toBe('waiting')
    expect(example.duration).toBe('Not started')
    expect(example.outputs[0].value).toMatch(/No downstream action/i)
  })
})
