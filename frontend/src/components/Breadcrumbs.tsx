import { ChevronRight } from 'lucide-react'
import { isFlowOpsPage } from '../data/flowOps'
import {
  AUTOMATION_STAGES,
  automationStage,
} from '../features/automation/stages'
import { useDemo } from '../state/useDemo'
import './Breadcrumbs.css'

export function Breadcrumbs() {
  const { state, dispatch } = useDemo()
  const page =
    state.activePage === 'operations' ? 'overview' : state.activePage
  if (!isFlowOpsPage(page)) return null

  const stage = automationStage(page)
  const stageIndex =
    AUTOMATION_STAGES.findIndex((item) => item.id === stage.id) + 1

  const goOverview = () => {
    dispatch({ type: 'SET_ACTIVE_PAGE', page: 'overview' })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      <ol className="breadcrumbs__list">
        <li>
          <button
            type="button"
            className="breadcrumbs__crumb is-link"
            onClick={goOverview}
          >
            Overview
          </button>
        </li>
        <li className="breadcrumbs__sep" aria-hidden="true">
          <ChevronRight size={14} strokeWidth={2} />
        </li>
        <li>
          <span className="breadcrumbs__crumb is-current" aria-current="page">
            <span className="breadcrumbs__index">
              {String(stageIndex).padStart(2, '0')}
            </span>
            {stage.shortTitle}
          </span>
        </li>
      </ol>
    </nav>
  )
}
