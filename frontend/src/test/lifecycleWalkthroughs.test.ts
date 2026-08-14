import { describe, expect, it } from 'vitest'
import { exampleForRun, runForStage } from '../features/automation/runFixtures'
import { automationStage } from '../features/automation/stages'
import { lifecycleHistoryForStep } from '../features/automation/fixtures/lifecycleHistory'

const LIFECYCLE_STAGE_IDS = ['scheduling', 'end-of-day', 'weekly'] as const

describe('lifecycle stage walkthroughs', () => {
  it.each(LIFECYCLE_STAGE_IDS)(
    'provides concise concrete input and output for every %s microstep',
    (stageId) => {
      const stage = automationStage(stageId)
      const run = runForStage(stageId)

      for (const step of stage.microsteps) {
        const example = exampleForRun(run, step, stageId)

        expect(example.inputs).toHaveLength(1)
        expect(example.outputs).toHaveLength(1)
        expect(example.inputs[0].value.length).toBeLessThan(90)
        expect(example.outputs[0].value.length).toBeLessThan(90)
      }
    },
  )

  it('uses a clear representative case for each lifecycle stage', () => {
    expect(runForStage('scheduling').label).toMatch(/Maria Alvarez/)
    expect(runForStage('end-of-day').label).toMatch(/Evelyn Brooks/)
    expect(runForStage('weekly').label).toMatch(/Walter Grant/)
  })

  it('keeps send-referral planned while schedule-patient is working', () => {
    const scheduling = automationStage('scheduling')
    const schedulingRun = runForStage('scheduling')
    const byId = Object.fromEntries(
      scheduling.microsteps.map((step) => [
        step.id,
        exampleForRun(schedulingRun, step, scheduling.id).status,
      ]),
    )
    expect(byId['send-referral-provider']).toBe('planned')
    expect(byId['schedule-patient']).toBe('completed')

    const weekly = automationStage('weekly')
    const weeklyRun = runForStage('weekly')
    const finalOutput = exampleForRun(
      weeklyRun,
      weekly.microsteps.at(-1)!,
      weekly.id,
    ).outputs[0].value
    expect(finalOutput).toMatch(/no automatic discharge/i)
  })

  it.each(LIFECYCLE_STAGE_IDS)(
    'shows three patient run versions for every %s microstep',
    (stageId) => {
      const stage = automationStage(stageId)
      const run = runForStage(stageId)

      for (const step of stage.microsteps) {
        const example = exampleForRun(run, step, stage.id)
        const history = lifecycleHistoryForStep(stage.id, step, run, example)

        expect(history).toHaveLength(3)
        expect(new Set(history.map((entry) => entry.runId)).size).toBe(3)
        expect(new Set(history.map((entry) => entry.patientName)).size).toBe(3)
        expect(history.every((entry) => entry.input && entry.output)).toBe(true)
      }
    },
  )
})
