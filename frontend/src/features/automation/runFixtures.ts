import type { FlowOpsPageId } from '../../data/flowOps'
import type { AutomationRunFixture } from './types'

export const AUTOMATION_RUNS: AutomationRunFixture[] = [
  {
    id: 'synthetic-complete',
    label: 'Complete referral walkthrough',
    source: 'Outlook email with synthetic-complete-referral.pdf',
    startedAt: 'August 7, 2026 at 10:18 AM',
    summary:
      'All minimum fields were present, no duplicate was found, and approval was recorded.',
  },
  {
    id: 'synthetic-exception',
    label: 'Missing-information walkthrough',
    source: 'Outlook email with synthetic-incomplete-referral.pdf',
    startedAt: 'August 7, 2026 at 9:42 AM',
    summary:
      'The referral was preserved, but downstream writes were blocked until missing data is resolved.',
  },
]

export function exampleForRun(
  run: AutomationRunFixture,
  step: import('./types').AutomationMicrostep,
  stageId: FlowOpsPageId,
) {
  if (run.id === 'synthetic-exception' && stageId !== 'intake') {
    return {
      status: 'waiting' as const,
      duration: 'Not started',
      inputs: [
        {
          label: 'Upstream gate',
          value: 'Referral intake is blocked by missing required information.',
        },
      ],
      outputs: [
        { label: 'Produced', value: 'No downstream action was allowed.' },
      ],
      validation:
        'This stage remains untouched until the referral returns to Intake and passes its guarded approval gate.',
    }
  }

  return run.id === 'synthetic-exception' && step.exceptionExample
    ? step.exceptionExample
    : step.example
}
