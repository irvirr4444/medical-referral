import type { FlowOpsPageId } from '../../data/flowOps'
import {
  BUTLER_RUN_FIXTURE,
  snapshotToExample,
  type AutomationMicrostep,
  type AutomationRunFixture,
  type MicrostepExample,
} from './types'
import {
  walkthroughExampleForStep,
  walkthroughRunForStage,
} from './fixtures/lifecycleWalkthroughs'

export const AUTOMATION_RUNS: AutomationRunFixture[] = [
  BUTLER_RUN_FIXTURE,
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

function genericExampleForRun(
  run: AutomationRunFixture,
  step: AutomationMicrostep,
  stageId: FlowOpsPageId,
): MicrostepExample {
  if (run.id === 'synthetic-exception' && stageId !== 'intake') {
    return {
      status: 'waiting',
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

export function exampleForRun(
  run: AutomationRunFixture,
  step: AutomationMicrostep,
  stageId: FlowOpsPageId,
): MicrostepExample {
  const walkthroughExample = walkthroughExampleForStep(stageId, step)
  if (walkthroughExample && walkthroughRunForStage(stageId)?.id === run.id) {
    return walkthroughExample
  }

  if (stageId === 'intake' && run.intakeSnapshots?.[step.id]) {
    const snapshot = run.intakeSnapshots[step.id]
    return snapshotToExample(snapshot, run.patientName ?? 'Unknown patient')
  }

  return genericExampleForRun(run, step, stageId)
}

export function runForStage(stageId: FlowOpsPageId): AutomationRunFixture {
  return walkthroughRunForStage(stageId) ?? BUTLER_RUN_FIXTURE
}

export function snapshotForRun(
  run: AutomationRunFixture,
  stepId: string,
  stageId: FlowOpsPageId,
) {
  if (stageId !== 'intake') return null
  return run.intakeSnapshots?.[stepId] ?? null
}
