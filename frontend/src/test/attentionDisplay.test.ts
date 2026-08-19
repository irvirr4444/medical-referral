import { describe, expect, it } from 'vitest'
import type { ActionTimer } from '../types'
import type { AttentionSignal } from '../features/automation/liveWorkflow/attention'
import {
  applyAttentionNavigation,
  attentionAriaSuffix,
  attentionBannerModel,
  selectAttentionTimers,
  timerAttentionSeverity,
  timerFromSignal,
} from '../features/automation/liveWorkflow/attentionDisplay'

const liveSignal: AttentionSignal = {
  signal_id: 'work_item:work-1',
  case_id: 'case-live',
  patient_label: 'Live Patient',
  stage: 2,
  step_id: 'assign-owner',
  severity: 'overdue',
  status: 'waiting',
  due_at: '2026-08-17T12:00:00Z',
  overdue_seconds: 120,
  action_label: 'Confirm case manager',
  source: 'work_item',
}

const blockedSignal: AttentionSignal = {
  signal_id: 'exception:open-1',
  case_id: 'case-blocked',
  patient_label: 'Blocked Patient',
  stage: 1,
  step_id: 'extract-and-verify',
  severity: 'blocked',
  status: 'open',
  due_at: null,
  overdue_seconds: 0,
  action_label: 'Resolve workflow exception',
  source: 'exception',
}

const dueSoonSignal: AttentionSignal = {
  signal_id: 'work_item:work-soon',
  case_id: 'case-soon',
  patient_label: 'Soon Patient',
  stage: 5,
  step_id: 'schedule-patient',
  severity: 'due_soon',
  status: 'waiting',
  due_at: '2026-08-17T12:10:00Z',
  overdue_seconds: 0,
  action_label: 'Schedule patient',
  source: 'work_item',
}

const demoTimer: ActionTimer = {
  id: 'demo:confirm-assignment',
  patientId: 'marcus-feldman',
  patientName: 'Marcus Feldman',
  stageId: 'assignment',
  stepId: 'assign-owner',
  actionId: 'confirm-assignment',
  eligibleAt: 1,
  deadlineAt: 2,
  status: 'overdue',
}

function captureWrites(run: () => void) {
  const writes: string[] = []
  const originalFetch = globalThis.fetch
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    const method = String(init?.method ?? 'GET').toUpperCase()
    if (method !== 'GET' && method !== 'HEAD') {
      writes.push(`${method} ${String(input)}`)
    }
    return Promise.reject(new Error('no network'))
  }) as typeof fetch
  try {
    run()
  } finally {
    globalThis.fetch = originalFetch
  }
  return writes
}

describe('attention display', () => {
  it('never mixes live signals with demo timers', () => {
    const mixed = selectAttentionTimers({
      liveStatus: 'connected',
      liveItems: [liveSignal],
      demoMode: true,
      demoTimers: { [demoTimer.id]: demoTimer },
    })
    expect(Object.keys(mixed)).toEqual(['work_item:work-1'])
    expect(mixed['work_item:work-1']?.patientId).toBe('case-live')
    expect(mixed[demoTimer.id]).toBeUndefined()
  })

  it('uses demo timers only when live attention is unavailable', () => {
    const demoOnly = selectAttentionTimers({
      liveStatus: 'unavailable',
      liveItems: [liveSignal],
      demoMode: true,
      demoTimers: { [demoTimer.id]: demoTimer },
    })
    expect(Object.keys(demoOnly)).toEqual([demoTimer.id])

    const empty = selectAttentionTimers({
      liveStatus: 'unavailable',
      liveItems: [liveSignal],
      demoMode: false,
      demoTimers: { [demoTimer.id]: demoTimer },
    })
    expect(empty).toEqual({})
  })

  it('keeps blocked live signals as blocked, not overdue confirmations', () => {
    const timer = timerFromSignal(blockedSignal)
    expect(timer.attentionSeverity).toBe('blocked')
    expect(timer.status).toBe('overdue')
    expect(timerAttentionSeverity(timer)).toBe('blocked')
    expect(attentionAriaSuffix(timer)).toContain('Needs attention')
    expect(attentionAriaSuffix(timer)).toContain('blocked')
    expect(attentionAriaSuffix(timer)).not.toMatch(/overdue/i)
    expect(attentionAriaSuffix(timer)).not.toMatch(/confirmation/i)

    const banner = attentionBannerModel([timer])
    expect(banner?.badge).toBe('Blocked')
    expect(banner?.headline).toBe('1 workflow issue needs attention')
    expect(banner?.headline).not.toMatch(/confirmation/i)
    expect(banner?.headline).not.toMatch(/action is overdue/i)
    expect(banner?.target.id).toBe('exception:open-1')
  })

  it('shows overdue actions without calling them confirmations', () => {
    const timer = timerFromSignal(liveSignal)
    expect(timer.attentionSeverity).toBe('overdue')
    const banner = attentionBannerModel([timer])
    expect(banner?.badge).toBe('Overdue')
    expect(banner?.headline).toBe('1 action is overdue')
    expect(banner?.headline).not.toMatch(/confirmation/i)
  })

  it('shows a due-soon banner when that is the only severity', () => {
    const banner = attentionBannerModel([timerFromSignal(dueSoonSignal)])
    expect(banner?.badge).toBe('Due soon')
    expect(banner?.headline).toBe('1 action is due soon')
    expect(banner?.target.id).toBe('work_item:work-soon')
  })

  it('prioritizes blocked over overdue and due soon', () => {
    const banner = attentionBannerModel([
      timerFromSignal(dueSoonSignal),
      timerFromSignal(liveSignal),
      timerFromSignal(blockedSignal),
    ])
    expect(banner?.badge).toBe('Blocked')
    expect(banner?.headline).toBe('1 workflow issue needs attention')
    expect(banner?.meta).toBe('1 overdue · 1 due soon')
    expect(banner?.target.attentionSeverity).toBe('blocked')
  })

  it('navigates each banner target without issuing a write request', () => {
    const cases = [blockedSignal, liveSignal, dueSoonSignal]
    for (const signal of cases) {
      const writes = captureWrites(() => {
        const dispatched: Array<{ type: string }> = []
        applyAttentionNavigation(timerFromSignal(signal), (action) => {
          dispatched.push(action)
        })
        expect(dispatched.map((action) => action.type)).toEqual([
          'SET_ACTIVE_PAGE',
          'SET_OPS_SELECTED_STEP',
          'SCOPE_OPS_PATIENT',
        ])
      })
      expect(writes).toEqual([])
    }
  })

  it('keeps legacy demo timers on their status without inventing blocked', () => {
    expect(demoTimer.attentionSeverity).toBeUndefined()
    expect(timerAttentionSeverity(demoTimer)).toBe('overdue')
    const banner = attentionBannerModel([demoTimer])
    expect(banner?.badge).toBe('Overdue')
    expect(banner?.headline).toBe('1 action is overdue')
    const mixed = selectAttentionTimers({
      liveStatus: 'unavailable',
      liveItems: [blockedSignal],
      demoMode: true,
      demoTimers: { [demoTimer.id]: demoTimer },
    })
    expect(mixed[demoTimer.id]?.status).toBe('overdue')
    expect(mixed[demoTimer.id]?.attentionSeverity).toBeUndefined()
  })
})
