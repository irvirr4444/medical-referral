import { Target } from 'lucide-react'
import { FLOW_OPS, type FlowOpsPageId } from '../data/flowOps'
import { StageInspector } from '../features/automation/StageInspector'
import { automationStage } from '../features/automation/stages'
import './WorkflowModal.css'

/** Inspectable automation page shared by workflow sections 1-7. */
export function StageOperationsPage({ pageId }: { pageId: FlowOpsPageId }) {
  const config = FLOW_OPS[pageId]
  const stage = automationStage(pageId)

  return (
    <>
      <header className="stage-ops-hero panel">
        <div>
          <h1>{config.title}</h1>
          <div className="stage-ops-hero__goal">
            <span className="stage-ops-hero__goal-label">
              <Target size={18} aria-hidden="true" />
              Goal
            </span>
            <p>{stage.purpose}</p>
          </div>
        </div>
      </header>
      <StageInspector key={pageId} stage={stage} />
    </>
  )
}
