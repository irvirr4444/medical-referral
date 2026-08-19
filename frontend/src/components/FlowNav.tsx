import { WORKFLOW_MODAL_TABS } from '../data/constants'
import { unreadCountForStage } from '../features/automation/unreadSteps'
import { canonicalOpsPageId } from '../features/automation/combinedAssignment'
import { useAttention } from '../features/automation/AttentionContext'
import { attentionGroups } from '../features/automation/liveWorkflow/attentionDisplay'
import { navigateAppPath, patientKeyFromPath } from '../features/automation/patientRoute'
import { useDemo } from '../state/useDemo'
import './FlowNav.css'

export const APP_NAV_ITEMS = [...WORKFLOW_MODAL_TABS] as const

export type AppPageId = (typeof APP_NAV_ITEMS)[number]['id']

export function FlowNav() {
  const { state, dispatch } = useDemo()
  const { timers } = useAttention()
  const groups = attentionGroups(Object.values(timers))
  const blockedStages = new Set<string>(
    groups.blocked.map((timer) => timer.stageId)
  )
  const overdueStages = new Set<string>(
    groups.overdue.map((timer) => timer.stageId)
  )

  return (
    <nav className="flow-nav" aria-label="Primary">
      <div className="flow-nav__inner">
        {APP_NAV_ITEMS.map((item) => {
          const active = canonicalOpsPageId(state.activePage) === item.id
          // Red is scoped to the open step so clearing the worklist in front of
          // you clears the badge; blue stays stage-wide so a new update waiting
          // on a later step still surfaces.
          const selectedStep = active
            ? state.opsSelectedStepByStage[item.id]
            : undefined
          const matchesStage = (timer: { stageId: string; stepId: string }) =>
            timer.stageId === item.id &&
            (!selectedStep || timer.stepId === selectedStep)
          const blockedCount = groups.blocked.filter(matchesStage).length
          const overdueCount = groups.overdue.filter(matchesStage).length
          const visualCount = blockedCount + overdueCount
          const isOverdue = active
            ? visualCount > 0
            : blockedStages.has(item.id) || overdueStages.has(item.id)
          const unreadCount = unreadCountForStage(state, item.id)
          const needsAttention = unreadCount > 0
          const parts = [
            blockedCount ? `${blockedCount} blocked` : null,
            overdueCount ? `${overdueCount} overdue` : null,
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
                        {visualCount}
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
