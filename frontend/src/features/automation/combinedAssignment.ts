import type { FlowOpsPageId } from '../../data/flowOps'

/** Visible combined Assignment & handoff actions, in display order. */
export const COMBINED_ASSIGNMENT_STEP_IDS = [
  'assign-owner',
  'notify-referral-source',
  'create-monday-record',
  'create-update-drk',
] as const

const HANDOFF_OPERATION_STEP_IDS = [
  'notify-referral-source',
  'create-monday-record',
  'create-update-drk',
] as const

export const VISIBLE_STAGE_IDS: FlowOpsPageId[] = [
  'intake',
  'assignment',
  'provider',
  'scheduling',
  'end-of-day',
  'weekly',
]

/** Map a legacy Handoff page request onto the combined Assignment page. */
export function canonicalOpsPageId(pageId: FlowOpsPageId): FlowOpsPageId {
  return pageId === 'handoff' ? 'assignment' : pageId
}

export function isHandoffOperationStep(stepId: string): boolean {
  return (HANDOFF_OPERATION_STEP_IDS as readonly string[]).includes(stepId)
}

/**
 * Fixture stage that owns a step's demo data.
 * Handoff artifacts stay in the handoff fixtures; Assignment steps stay put.
 */
export function opsSourceStage(
  pageId: FlowOpsPageId,
  stepId?: string,
): FlowOpsPageId {
  if (stepId && isHandoffOperationStep(stepId)) return 'handoff'
  return pageId
}

/**
 * Visible Assign Case Manager (`assign-owner`) reuses the assignment
 * recommendation/confirmation fixture rows stored under `determine-owner`.
 */
export function fixtureStepId(pageId: FlowOpsPageId, stepId: string): string {
  if (pageId === 'assignment' && stepId === 'assign-owner') {
    return 'determine-owner'
  }
  return stepId
}
