import type { ReactNode } from 'react'
import { StagePatientSteps } from './StagePatientSteps'
import type { AutomationStageDefinition } from './types'
import './StageInspector.css'
import './StageOps.css'

export function StageInspector({
  stage,
  sidebarHeader,
  mainHeader,
}: {
  stage: AutomationStageDefinition
  sidebarHeader?: ReactNode
  mainHeader?: ReactNode
}) {
  return (
    <div
      className="stage-ops"
      aria-label={`${stage.shortTitle} operations`}
    >
      <StagePatientSteps
        stageId={stage.id}
        microsteps={stage.microsteps}
        sidebarHeader={sidebarHeader}
        mainHeader={mainHeader}
      />
    </div>
  )
}
