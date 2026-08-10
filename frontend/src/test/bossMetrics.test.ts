import { describe, expect, it } from 'vitest'
import {
  bossPeriodById,
  buildBossPeriodViews,
  buildCustomBossMetrics,
  inclusiveDayCount,
} from '../data/bossMetrics'
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

describe('bossMetrics', () => {
  it('provides four illustrative business metrics with prior-period comparisons', () => {
    const periods = buildBossPeriodViews('overview')
    expect(periods.map((period) => period.id)).toEqual(['today', 'week', 'month'])
    for (const period of periods) {
      expect(period.comparisonLabel.length).toBeGreaterThan(0)
      expect(period.metrics).toHaveLength(4)
      expect(period.metrics.map((metric) => metric.id)).toEqual([
        'new-referrals',
        'patients-scheduled',
        'patients-seen',
        'wounds-healed',
      ])
      expect(period.metrics.every((metric) => metric.value > 0)).toBe(true)
      expect(
        period.metrics.every(
          (metric) => metric.delta === metric.value - metric.previousValue,
        ),
      ).toBe(true)
    }
    const today = bossPeriodById('today', 'overview')
    expect(today.comparisonLabel).toBe('vs yesterday')
    expect(today.comparisonHoverLabel).toBe('Compared to last day')
    expect(today.metrics[0].value).toBe(18)
    expect(today.metrics[0].previousValue).toBe(15)
    expect(today.metrics[0].delta).toBe(3)
  })

  it('provides four stage-specific metrics for every workflow stage', () => {
    for (const stage of STAGES) {
      const today = bossPeriodById('today', stage)
      expect(today.metrics).toHaveLength(4)
      expect(new Set(today.metrics.map((metric) => metric.id)).size).toBe(4)
      expect(today.metrics.every((metric) => metric.label.length > 0)).toBe(true)
    }
    expect(bossPeriodById('today', 'intake').metrics[0].label).toBe(
      'Referrals received',
    )
    expect(bossPeriodById('today', 'intake').metrics.map((m) => m.label)).toEqual([
      'Referrals received',
      'Ready to proceed',
      'Waiting on information',
      'Escalated to marketer',
    ])
    expect(bossPeriodById('today', 'weekly').metrics.map((m) => m.label)).toEqual([
      'Patients seen',
      'Missed visits',
      'Placed on hold',
      'Discharge reviews needed',
    ])
  })

  it('derives deterministic custom-range totals from the inclusive day count', () => {
    expect(inclusiveDayCount('2026-08-01', '2026-08-07')).toBe(7)
    expect(inclusiveDayCount('2026-08-07', '2026-08-01')).toBeNull()

    const first = buildCustomBossMetrics('2026-08-01', '2026-08-07', 'overview')
    const second = buildCustomBossMetrics('2026-08-01', '2026-08-07', 'overview')
    expect(first).not.toBeNull()
    expect(second).toEqual(first)
    expect(first?.metrics[0].value).toBe(112)
    expect(first?.metrics[0].previousValue).toBe(102)
    expect(first?.comparisonLabel).toBe('vs prior period')
    expect(first?.comparisonHoverLabel).toBe('Compared to the prior period')
    expect(first?.caption).toBe('August 1, 2026 – August 7, 2026')
  })
})
