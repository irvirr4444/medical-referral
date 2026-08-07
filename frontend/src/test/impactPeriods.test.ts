import { describe, expect, it } from 'vitest'
import { BASELINE_METRICS, INBOX_BATCH_DELTA, addMetrics } from '../data/constants'
import {
  IMPACT_STAGES,
  allocateStageMinutes,
  buildPeriodImpacts,
  impactBoardCopy,
} from '../data/impactPeriods'

describe('period impact board', () => {
  it('builds today / week / month overview totals from live today metrics', () => {
    const periods = buildPeriodImpacts(BASELINE_METRICS, 'overview')
    expect(periods.map((p) => p.id)).toEqual(['today', 'week', 'month'])
    expect(periods[0].timeMinutes).toBe(BASELINE_METRICS.timeReturnedMinutes)
    expect(periods[1].timeMinutes).toBeGreaterThan(periods[0].timeMinutes)
    expect(periods[2].timeMinutes).toBeGreaterThan(periods[1].timeMinutes)
  })

  it('allocates stage minutes that sum exactly to overview', () => {
    const allocated = allocateStageMinutes(BASELINE_METRICS.timeReturnedMinutes)
    const stageSum = IMPACT_STAGES.reduce((sum, stage) => sum + allocated[stage], 0)
    expect(stageSum).toBe(BASELINE_METRICS.timeReturnedMinutes)

    const overview = buildPeriodImpacts(BASELINE_METRICS, 'overview')[0]
    const stages = IMPACT_STAGES.map(
      (stage) => buildPeriodImpacts(BASELINE_METRICS, stage)[0].timeMinutes,
    )
    expect(stages.reduce((sum, n) => sum + n, 0)).toBe(overview.timeMinutes)
    expect(impactBoardCopy('intake').title).toMatch(/Intake/i)
    expect(buildPeriodImpacts(BASELINE_METRICS, 'scheduling')[0].patients).toBeLessThan(
      buildPeriodImpacts(BASELINE_METRICS, 'intake')[0].patients,
    )
  })

  it('keeps extras additive across stages and overview', () => {
    const extras = { assignment: 8, provider: 11 }
    const overview = buildPeriodImpacts(BASELINE_METRICS, 'overview', extras)[0]
    const assignment = buildPeriodImpacts(BASELINE_METRICS, 'assignment', extras)[0]
    const provider = buildPeriodImpacts(BASELINE_METRICS, 'provider', extras)[0]
    const bareAssignment = buildPeriodImpacts(BASELINE_METRICS, 'assignment')[0]
    expect(assignment.timeMinutes - bareAssignment.timeMinutes).toBe(8)
    expect(overview.timeMinutes).toBe(BASELINE_METRICS.timeReturnedMinutes + 8 + 11)
    expect(provider.timeMinutes).toBeGreaterThan(0)
  })

  it('grows after inbox processing and rolls into longer periods', () => {
    const before = buildPeriodImpacts(BASELINE_METRICS, 'assignment')
    const afterToday = addMetrics(BASELINE_METRICS, INBOX_BATCH_DELTA)
    const after = buildPeriodImpacts(afterToday, 'assignment')
    expect(after[0].patients).toBeGreaterThan(before[0].patients)
    expect(after[2].timeMinutes).toBeGreaterThan(before[2].timeMinutes)
  })
})
