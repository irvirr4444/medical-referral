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
      <header className="stage-ops-hero">
        <div>
          <p className="caption">Automation stage</p>
          <h1>{config.title}</h1>
          <p className="muted">{stage.purpose}</p>
        </div>
      </header>
      <StageInspector key={pageId} stage={stage} />
    </>
  )
}
