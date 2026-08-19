import type { FlowOpsPageId } from '../../../data/flowOps'
import { canonicalOpsPageId } from '../combinedAssignment'
import type { AutomationStageDefinition } from '../types'
import { ASSIGNMENT_STAGE } from './assignment'
import { END_OF_DAY_STAGE } from './endOfDay'
import { HANDOFF_STAGE } from './handoff'
import { INTAKE_STAGE } from './intake'
import { PROVIDER_STAGE } from './provider'
import { SCHEDULING_STAGE } from './scheduling'
import { WEEKLY_STAGE } from './weekly'

export const AUTOMATION_STAGES: AutomationStageDefinition[] = [
  INTAKE_STAGE,
  ASSIGNMENT_STAGE,
  PROVIDER_STAGE,
  SCHEDULING_STAGE,
  END_OF_DAY_STAGE,
  WEEKLY_STAGE,
]

const STAGE_BY_ID = new Map(
  [...AUTOMATION_STAGES, HANDOFF_STAGE].map((stage) => [stage.id, stage]),
)

export function automationStage(
  pageId: FlowOpsPageId,
): AutomationStageDefinition {
  const canonicalId = canonicalOpsPageId(pageId)
  const stage = STAGE_BY_ID.get(canonicalId)
  if (!stage)
    throw new Error(`Missing automation stage definition for ${pageId}`)
  return stage
}
