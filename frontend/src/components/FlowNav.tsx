import { WORKFLOW_MODAL_TABS } from '../data/constants'
import {
  overdueStageIds,
  overdueTimers,
} from '../features/automation/confirmationTimers'
import { unreadCountForStage } from '../features/automation/unreadSteps'
import { navigateAppPath, patientKeyFromPath } from '../features/automation/patientRoute'
import { useDemo } from '../state/useDemo'
import './FlowNav.css'

export const APP_NAV_ITEMS = [...WORKFLOW_MODAL_TABS] as const

export type AppPageId = (typeof APP_NAV_ITEMS)[number]['id']

export function FlowNav() {
  const { state, dispatch } = useDemo()
  const overdue = overdueTimers(state.actionTimers)
  const overdueStages = overdueStageIds(state.actionTimers)

  return (
    <nav className="flow-nav" aria-label="Primary">
      <div className="flow-nav__inner">
        {APP_NAV_ITEMS.map((item) => {
          const active = state.activePage === item.id
          // Red is scoped to the open step so clearing the worklist in front of
          // you clears the badge; blue stays stage-wide so a new update waiting
          // on a later step still surfaces.
          const selectedStep = active
            ? state.opsSelectedStepByStage[item.id]
            : undefined
          const overdueCount = overdue.filter(
            (timer) =>
              timer.stageId === item.id &&
              (!selectedStep || timer.stepId === selectedStep),
          ).length
          const isOverdue = active ? overdueCount > 0 : overdueStages.has(item.id)
          const unreadCount = unreadCountForStage(state, item.id)
          const needsAttention = unreadCount > 0
          const parts = [
            isOverdue ? `${overdueCount} overdue` : null,
            needsAttention
              ? `${unreadCount} new update${unreadCount === 1 ? '' : 's'}`
              : null,
          ].filter(Boolean)
          return (
            <button
              key={item.id}
              type="button"
              className={`flow-nav__link ${active ? 'is-active' : ''}${
                isOverdue ? ' is-overdue' : ''
              }${needsAttention ? ' is-unread' : ''}`}
              aria-current={active ? 'page' : undefined}
              aria-label={
                parts.length ? `${item.label}, ${parts.join(', ')}` : undefined
              }
              onClick={() => {
                if (patientKeyFromPath(window.location.pathname)) {
                  navigateAppPath('/')
                }
                dispatch({ type: 'SET_ACTIVE_PAGE', page: item.id })
                window.scrollTo({ top: 0, behavior: 'smooth' })
              }}
            >
              <span className="flow-nav__label-row">
                {item.label}
                {isOverdue || needsAttention ? (
                  <span className="flow-nav__badges">
                    {isOverdue ? (
                      <span
                        className="flow-nav__overdue-count"
                        aria-hidden="true"
                      >
                        {overdueCount}
                      </span>
                    ) : null}
                    {needsAttention ? (
                      <span
                        className="flow-nav__unread-count"
                        aria-hidden="true"
                      >
                        {unreadCount}
                      </span>
                    ) : null}
                  </span>
                ) : null}
              </span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
