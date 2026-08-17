import { describe, expect, it } from 'vitest'
import {
  ACTION_DEFS,
  DEMO_TIMER_SEEDS,
  FLOW_ONLY_ACTION_IDS,
  attentionSummary,
  compareAttention,
  formatBusinessDuration,
  seedActionTimers,
  slaLabel,
} from '../features/automation/confirmationTimers'
import type { ConfirmationActionId } from '../types'

describe('confirmation timers', () => {
  it('seeds every cold-start confirmation action across pending, warning, and overdue', () => {
    const seeded = new Set(DEMO_TIMER_SEEDS.map((seed) => seed.actionId))
    const required = (Object.keys(ACTION_DEFS) as ConfirmationActionId[]).filter(
      (actionId) => !FLOW_ONLY_ACTION_IDS.includes(actionId),
    )
    expect(required.every((actionId) => seeded.has(actionId))).toBe(true)
    expect(DEMO_TIMER_SEEDS.some((seed) => seed.state === 'pending')).toBe(true)
    expect(DEMO_TIMER_SEEDS.some((seed) => seed.state === 'warning')).toBe(true)
    expect(DEMO_TIMER_SEEDS.some((seed) => seed.state === 'overdue')).toBe(true)

    const timers = seedActionTimers(1_000_000)
    expect(Object.values(timers).filter((timer) => timer.status === 'overdue').length).toBeGreaterThan(1)
    expect(Object.values(timers).filter((timer) => timer.status === 'warning').length).toBeGreaterThan(0)
    expect(Object.values(timers).filter((timer) => timer.status === 'pending').length).toBeGreaterThan(0)
  })

  it('ranks overdue ahead of warning and pending', () => {
    const now = 1_000_000
    const timers = seedActionTimers(now)
    const overdue = Object.values(timers).find((timer) => timer.status === 'overdue')
    const warning = Object.values(timers).find((timer) => timer.status === 'warning')
    const pending = Object.values(timers).find((timer) => timer.status === 'pending')
    expect(overdue && warning && pending).toBeTruthy()
    expect(compareAttention(overdue, warning)).toBeLessThan(0)
    expect(compareAttention(warning, pending)).toBeLessThan(0)
    expect(compareAttention(pending, null)).toBeLessThan(0)

    const summary = attentionSummary(timers)
    expect(summary.total).toBe(summary.overdue.length)
    expect(summary.oldest?.status).toBe('overdue')
    expect(summary.oldest?.deadlineAt).toBe(
      Math.min(...summary.overdue.map((timer) => timer.deadlineAt)),
    )
  })

  it('renders business-time SLA copy instead of the demo clock', () => {
    expect(formatBusinessDuration(30 * 60_000)).toBe('30m')
    expect(formatBusinessDuration(90 * 60_000)).toBe('1h 30m')
    expect(slaLabel('confirm-assignment')).toBe('30m')
    expect(slaLabel('eod-follow-up-cm')).toBe('24h')
  })
})
