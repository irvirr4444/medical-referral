import { StagePatientSteps } from './StagePatientSteps'
import type { AutomationStageDefinition } from './types'
import './StageInspector.css'
import './StageOps.css'

export function StageInspector({
  stage,
}: {
  stage: AutomationStageDefinition
}) {
  return (
    <div
      className="stage-ops"
      aria-label={`${stage.shortTitle} operations`}
    >
      <StagePatientSteps stageId={stage.id} microsteps={stage.microsteps} />
    </div>
  )
}
