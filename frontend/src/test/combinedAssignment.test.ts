import { describe, expect, it } from 'vitest'
import {
  VISIBLE_STAGE_ORDER,
  canonicalOpsPageId,
  combinedVisibleStageOutcome,
  visibleStageLabel,
} from '../features/automation/combinedAssignment'
import { STAGE_LABEL } from '../features/automation/ops'
import { automationStage, AUTOMATION_STAGES } from '../features/automation/stages'
import type { PatientStageOutcome } from '../features/automation/ops/types'

function outcome(
  stageId: PatientStageOutcome['stageId'],
  status: PatientStageOutcome['status'],
  headline: string,
  outcomes: PatientStageOutcome['outcomes'] = [],
): PatientStageOutcome {
  return { stageId, status, headline, outcomes }
}

describe('combined assignment presentation', () => {
  it('keeps six visible stages and the four combined actions', () => {
    expect(VISIBLE_STAGE_ORDER).toEqual([
      'intake',
      'assignment',
      'provider',
      'scheduling',
      'end-of-day',
      'weekly',
    ])
    expect(AUTOMATION_STAGES.map((stage) => stage.id)).toEqual(VISIBLE_STAGE_ORDER)
    expect(automationStage('assignment').microsteps.map((step) => step.name)).toEqual(
      [
        'Assign Case Manager',
        'Notify Case Manager',
        'Create Monday.com Record',
        'Prepare DRK Chart',
      ],
    )
  })

  it('renders a completed assignment plus current handoff as current', () => {
    const combined = combinedVisibleStageOutcome(
      [
        outcome('intake', 'done', 'Approved'),
        outcome('assignment', 'done', 'Cole confirmed', [
          { occurredAt: 'August 10, 2026 at 10:16 AM', summary: 'Owner recorded' },
        ]),
        outcome('handoff', 'current', 'Monday write in progress', [
          { occurredAt: 'August 10, 2026 at 10:17 AM', summary: 'Case manager notified' },
        ]),
      ],
      'assignment',
    )

    expect(combined?.status).toBe('current')
    expect(combined?.stageId).toBe('assignment')
    expect(combined?.headline).toBe('Cole confirmed · Monday write in progress')
    expect(combined?.outcomes.map((item) => item.summary)).toEqual([
      'Owner recorded',
      'Case manager notified',
    ])
  })

  it('renders a completed assignment plus blocked handoff as blocked', () => {
    const combined = combinedVisibleStageOutcome(
      [
        outcome('assignment', 'done', 'Owner confirmed'),
        outcome('handoff', 'blocked', 'DRK identity match unresolved'),
      ],
      'assignment',
    )

    expect(combined?.status).toBe('blocked')
    expect(combined?.headline).toBe(
      'Owner confirmed · DRK identity match unresolved',
    )
  })

  it('renders done only when both assignment and handoff are done', () => {
    const combined = combinedVisibleStageOutcome(
      [
        outcome('assignment', 'done', 'Owner confirmed', [
          { occurredAt: 'August 10, 2026 at 10:16 AM', summary: 'Owner recorded' },
        ]),
        outcome('handoff', 'done', 'Records prepared', [
          { occurredAt: 'August 10, 2026 at 10:16 AM', summary: 'Owner recorded' },
          { occurredAt: 'August 10, 2026 at 10:19 AM', summary: 'DRK draft ready' },
        ]),
      ],
      'assignment',
    )

    expect(combined?.status).toBe('done')
    expect(combined?.outcomes.map((item) => item.summary)).toEqual([
      'Owner recorded',
      'DRK draft ready',
    ])
  })

  it('uses the single internal outcome when only one phase exists', () => {
    expect(
      combinedVisibleStageOutcome(
        [outcome('assignment', 'current', 'Awaiting owner confirm')],
        'assignment',
      )?.status,
    ).toBe('current')
    expect(
      combinedVisibleStageOutcome(
        [outcome('handoff', 'blocked', 'Monday write failed')],
        'assignment',
      )?.status,
    ).toBe('blocked')
  })

  it('displays a legacy current handoff stage as Assignment & handoff', () => {
    expect(canonicalOpsPageId('handoff')).toBe('assignment')
    expect(visibleStageLabel('handoff', STAGE_LABEL)).toBe('Assignment & handoff')
    expect(visibleStageLabel('handoff', STAGE_LABEL)).not.toBe('Handoff')
    expect(STAGE_LABEL.handoff).toBe('Handoff')
  })
})
