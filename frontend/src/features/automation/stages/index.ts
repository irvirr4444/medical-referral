import type { FlowOpsPageId } from '../../../data/flowOps'
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

const STAGE_BY_ID = new Map<string, AutomationStageDefinition>([
  ...AUTOMATION_STAGES.map((stage) => [stage.id, stage] as const),
  ['handoff', HANDOFF_STAGE],
])

export function automationStage(
  pageId: FlowOpsPageId,
): AutomationStageDefinition {
  const stage = STAGE_BY_ID.get(pageId)
  if (!stage)
    throw new Error(`Missing automation stage definition for ${pageId}`)
  return stage
}

export { HANDOFF_STAGE }
