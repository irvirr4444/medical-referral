import type { FlowOpsPageId } from '../../data/flowOps'
import type { PatientStageOutcome } from './ops/types'

export const COMBINED_ASSIGNMENT_PAGE_ID = 'assignment' as const
export const LEGACY_HANDOFF_PAGE_ID = 'handoff' as const

export const HANDOFF_OPERATION_STEP_IDS = [
  'notify-referral-source',
  'create-monday-record',
  'create-update-drk',
] as const

export const COMBINED_ASSIGNMENT_STEP_IDS = [
  'assign-owner',
  ...HANDOFF_OPERATION_STEP_IDS,
] as const

export const VISIBLE_STAGE_ORDER: FlowOpsPageId[] = [
  'intake',
  'assignment',
  'provider',
  'scheduling',
  'end-of-day',
  'weekly',
]

export function isCombinedAssignmentStage(stageId: string): boolean {
  return stageId === COMBINED_ASSIGNMENT_PAGE_ID || stageId === LEGACY_HANDOFF_PAGE_ID
}

export type HandoffOperationStepId = (typeof HANDOFF_OPERATION_STEP_IDS)[number]

export function isHandoffOperationStep(
  stepId: string,
): stepId is HandoffOperationStepId {
  return (HANDOFF_OPERATION_STEP_IDS as readonly string[]).includes(stepId)
}

export function isAssignmentGateStep(stepId: string): boolean {
  return stepId === 'assign-owner' || stepId === 'determine-owner'
}

export function canonicalOpsPageId<T extends string>(pageId: T): T | typeof COMBINED_ASSIGNMENT_PAGE_ID {
  return pageId === LEGACY_HANDOFF_PAGE_ID ? COMBINED_ASSIGNMENT_PAGE_ID : pageId
}

export function visibleStageLabel(
  stageId: string,
  labels: Record<string, string>,
): string {
  return labels[canonicalOpsPageId(stageId)] ?? labels[stageId] ?? stageId
}

export function combinedVisibleStageOutcome(
  stages: PatientStageOutcome[],
  visibleStageId: FlowOpsPageId,
): PatientStageOutcome | undefined {
  if (!isCombinedAssignmentStage(visibleStageId)) {
    return stages.find((stage) => stage.stageId === visibleStageId)
  }

  const matching = stages.filter((stage) =>
    isCombinedAssignmentStage(stage.stageId),
  )
  if (matching.length === 0) return undefined
  if (matching.length === 1) return matching[0]

  return {
    stageId: COMBINED_ASSIGNMENT_PAGE_ID,
    status: combinedAssignmentStatus(matching),
    headline: combinedHeadlines(matching),
    outcomes: combinedOutcomes(matching),
  }
}

function combinedAssignmentStatus(
  outcomes: PatientStageOutcome[],
): PatientStageOutcome['status'] {
  if (outcomes.some((item) => item.status === 'blocked')) return 'blocked'
  if (outcomes.some((item) => item.status === 'current')) return 'current'
  if (outcomes.every((item) => item.status === 'done')) return 'done'
  if (outcomes.every((item) => item.status === 'upcoming')) return 'upcoming'
  return 'current'
}

function combinedHeadlines(outcomes: PatientStageOutcome[]): string {
  const useful = outcomes
    .filter((item) => item.status !== 'upcoming' && item.headline.trim())
    .map((item) => item.headline.trim())
  const source = useful.length
    ? useful
    : outcomes.map((item) => item.headline.trim()).filter(Boolean)
  return [...new Set(source)].join(' · ')
}

function combinedOutcomes(
  outcomes: PatientStageOutcome[],
): PatientStageOutcome['outcomes'] {
  const seen = new Set<string>()
  const merged: PatientStageOutcome['outcomes'] = []
  for (const item of outcomes) {
    for (const outcome of item.outcomes) {
      const key = `${outcome.occurredAt}|${outcome.summary}`
      if (seen.has(key)) continue
      seen.add(key)
      merged.push(outcome)
    }
  }
  return merged.sort(
    (left, right) => outcomeTimeMs(left.occurredAt) - outcomeTimeMs(right.occurredAt),
  )
}

function outcomeTimeMs(value: string): number {
  const parsed = new Date(value.replace(' at ', ' '))
  return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime()
}
