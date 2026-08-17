import { Target } from 'lucide-react'
import { FLOW_OPS, type FlowOpsPageId } from '../data/flowOps'
import { StageInspector } from '../features/automation/StageInspector'
import {
  AUTOMATION_STAGES,
  automationStage,
} from '../features/automation/stages'
import { useDemo } from '../state/useDemo'
import { OverviewImpactBoard } from './OverviewImpactBoard'
import './WorkflowModal.css'
import './StageOperationsPage.css'

/** Inspectable automation page shared by workflow sections 1-7. */
export function StageOperationsPage({ pageId }: { pageId: FlowOpsPageId }) {
  const { dispatch } = useDemo()
  const config = FLOW_OPS[pageId]
  const stage = automationStage(pageId)
  const stageIndex = AUTOMATION_STAGES.findIndex((item) => item.id === pageId)
  const previous = stageIndex > 0 ? AUTOMATION_STAGES[stageIndex - 1] : null
  const next =
    stageIndex >= 0 && stageIndex < AUTOMATION_STAGES.length - 1
      ? AUTOMATION_STAGES[stageIndex + 1]
      : null

  const goToStage = (id: string) => {
    dispatch({ type: 'SET_ACTIVE_PAGE', page: id })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="stage-page">
      <aside className="stage-page__rail panel-dark" aria-label="Stage summary">
        <p className="mono-label stage-page__index">
          Stage {String(stageIndex + 1).padStart(2, '0')}
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

        <nav className="stage-page__nav" aria-label="Stage navigation">
          {previous ? (
            <button
              type="button"
              className="stage-page__nav-btn"
              onClick={() => goToStage(previous.id)}
            >
              Previous
            </button>
          ) : null}
          {next ? (
            <button
              type="button"
              className="stage-page__nav-btn is-next"
              onClick={() => goToStage(next.id)}
            >
              Next
            </button>
          ) : null}
        </nav>
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
