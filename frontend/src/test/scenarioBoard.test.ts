import { describe, expect, it } from 'vitest'
import {
  assertScenarioCoverage,
  countScenarioBuckets,
  createInitialWorkflowScenarios,
  scenariosForTab,
} from '../data/workflowScenarios'
import { createInitialState, demoReducer } from '../state/demoReducer'

describe('workflow scenario catalog', () => {
  it('covers every tab with 2–4 examples per scenario', () => {
    const scenarios = createInitialWorkflowScenarios()
    const byTab = assertScenarioCoverage(scenarios)
    expect(Object.keys(byTab).sort()).toEqual([
      'assignment',
      'end-of-day',
      'handoff',
      'intake',
      'provider',
      'scheduling',
      'weekly',
    ])
    for (const tab of Object.keys(byTab)) {
      expect(byTab[tab].length).toBeGreaterThanOrEqual(3)
      for (const scenario of byTab[tab]) {
        expect(scenario.cases.length).toBeGreaterThanOrEqual(2)
        expect(scenario.humanControlNote.length).toBeGreaterThan(10)
      }
    }
    const totals = countScenarioBuckets(scenarios)
    expect(totals.totalCases).toBeGreaterThan(70)
    expect(totals.approval).toBeGreaterThan(0)
    expect(totals.blocked).toBeGreaterThan(0)
  })

  it('never auto-completes approval cases without an explicit action', () => {
    const state = createInitialState()
    const approvalCase = state.workflowScenarios
      .flatMap((scenario) => scenario.cases.map((item) => ({ scenario, item })))
      .find(({ scenario }) => scenario.bucket === 'approval')
    expect(approvalCase).toBeTruthy()
    expect(['open', 'waiting_human', 'monitoring', 'in_progress']).toContain(
      approvalCase!.item.status,
    )
  })
})

describe('scenario reducer actions', () => {
  it('resolves a scenario case, returns minutes, and appends activity', () => {
    let state = createInitialState()
    const target = scenariosForTab(state.workflowScenarios, 'assignment')[0].cases[0]
    state = demoReducer(state, { type: 'RESOLVE_SCENARIO_CASE', id: target.id })
    const updated = state.workflowScenarios
      .flatMap((scenario) => scenario.cases)
      .find((item) => item.id === target.id)!
    expect(updated.status).toBe('completed')
    expect(state.scenarioMinutesReturned).toBe(target.minutesReturned)
    expect(state.activityFeed[0].text).toContain(target.patientName)
  })

  it('escalates blocked/approval cases instead of marking them completed', () => {
    let state = createInitialState()
    const blocked = state.workflowScenarios
      .flatMap((scenario) => scenario.cases.map((item) => ({ scenario, item })))
      .find(({ scenario, item }) => scenario.bucket === 'blocked' && item.status !== 'completed')!
    state = demoReducer(state, { type: 'RESOLVE_SCENARIO_CASE', id: blocked.item.id })
    const updated = state.workflowScenarios
      .flatMap((scenario) => scenario.cases)
      .find((item) => item.id === blocked.item.id)!
    expect(updated.status).toBe('escalated')
  })

  it('resets scenario board with the day', () => {
    let state = createInitialState()
    const target = state.workflowScenarios[0].cases[0]
    state = demoReducer(state, { type: 'RESOLVE_SCENARIO_CASE', id: target.id })
    state = demoReducer(state, { type: 'SET_SCENARIO_FILTER', filter: 'blocked' })
    state = demoReducer(state, { type: 'RESET' })
    expect(state.scenarioMinutesReturned).toBe(0)
    expect(state.scenarioFilter).toBe('all')
    expect(state.workflowScenarios[0].cases[0].status).not.toBe('completed')
  })
})
