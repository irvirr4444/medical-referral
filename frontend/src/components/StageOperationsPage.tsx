import { Target } from 'lucide-react'
import { FLOW_OPS, type FlowOpsPageId } from '../data/flowOps'
import { StageInspector } from '../features/automation/StageInspector'
import { automationStage } from '../features/automation/stages'
import { canonicalOpsPageId } from '../features/automation/combinedAssignment'
import { OverviewImpactBoard } from './OverviewImpactBoard'
import './WorkflowModal.css'

/** Inspectable automation page shared by workflow sections 1-6. */
export function StageOperationsPage({ pageId }: { pageId: FlowOpsPageId }) {
  const canonicalId = canonicalOpsPageId(pageId)
  const config = FLOW_OPS[canonicalId]
  const stage = automationStage(canonicalId)

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
      <OverviewImpactBoard key={canonicalId} scope={canonicalId} />
      <StageInspector key={`${canonicalId}-inspector`} stage={stage} />
    </>
  )
}
