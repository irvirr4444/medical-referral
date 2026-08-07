import { describe, expect, it } from 'vitest'
import { createInitialState, demoReducer } from '../state/demoReducer'

describe('lifecycle operations', () => {
  it('runs a lifecycle stage and returns minutes', () => {
    let state = createInitialState()
    expect(state.lifecycleStageId).toBe('assignment')
    state = demoReducer(state, { type: 'START_LIFECYCLE_STAGE' })
    expect(state.lifecycleRunning).toBe(true)
    state = demoReducer(state, { type: 'COMPLETE_LIFECYCLE_STAGE' })
    expect(state.lifecycleRunning).toBe(false)
    expect(state.lifecycleMinutesReturned).toBeGreaterThan(0)
    expect(
      state.lifecycleCases
        .filter((item) => item.stageId === 'assignment')
        .every((item) => item.status === 'completed' || item.status === 'escalated'),
    ).toBe(true)
  })

  it('resolves a single lifecycle case', () => {
    let state = createInitialState()
    state = demoReducer(state, { type: 'SET_LIFECYCLE_STAGE', stageId: 'holds' })
    const target = state.lifecycleCases.find((item) => item.stageId === 'holds')!
    state = demoReducer(state, { type: 'RESOLVE_LIFECYCLE_CASE', id: target.id })
    const updated = state.lifecycleCases.find((item) => item.id === target.id)!
    expect(updated.status).toBe('completed')
    expect(state.lifecycleMinutesReturned).toBe(target.minutesReturned)
  })
})
