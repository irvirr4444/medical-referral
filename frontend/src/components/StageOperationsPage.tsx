import { Target } from 'lucide-react'
import { FLOW_OPS, type FlowOpsPageId } from '../data/flowOps'
import { StageInspector } from '../features/automation/StageInspector'
import {
  AUTOMATION_STAGES,
  automationStage,
} from '../features/automation/stages'
import { OverviewImpactBoard } from './OverviewImpactBoard'
import './WorkflowModal.css'
import './StageOperationsPage.css'

/** Inspectable automation page shared by workflow sections 1-7. */
export function StageOperationsPage({ pageId }: { pageId: FlowOpsPageId }) {
  const config = FLOW_OPS[pageId]
  const stage = automationStage(pageId)
  const stageIndex =
    AUTOMATION_STAGES.findIndex((item) => item.id === pageId) + 1

  return (
    <div className="stage-page">
      <aside className="stage-page__rail panel-dark" aria-label="Stage summary">
        <p className="mono-label stage-page__index">
          Stage {String(stageIndex).padStart(2, '0')}
        </p>
        <h1>{config.title}</h1>
        <div className="stage-page__goal">
          <span className="mono-label">
            <Target size={14} aria-hidden="true" />
            Goal
          </span>
          <p>{stage.purpose}</p>
        </div>
        <dl className="stage-page__meta">
          <div>
            <dt className="mono-label">Microsteps</dt>
            <dd>{stage.microsteps.length}</dd>
          </div>
          <div>
            <dt className="mono-label">Focus</dt>
            <dd>{stage.shortTitle}</dd>
          </div>
        </dl>
      </aside>

      <div className="stage-page__impact">
        <OverviewImpactBoard
          key={pageId}
          scope={pageId}
          density="compact"
          title="Stage objectives"
        />
      </div>

      <StageInspector key={`${pageId}-inspector`} stage={stage} />
    </div>
  )
}
