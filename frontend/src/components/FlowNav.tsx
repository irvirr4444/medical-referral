import { Bell, User } from 'lucide-react'
import { attentionSummary } from '../features/automation/confirmationTimers'
import { navigateAppPath, patientKeyFromPath } from '../features/automation/patientRoute'
import { useDemo } from '../state/useDemo'
import './FlowNav.css'

export type AppPageId =
  | 'overview'
  | 'intake'
  | 'assignment'
  | 'handoff'
  | 'provider'
  | 'scheduling'
  | 'end-of-day'
  | 'weekly'
  | 'operations'

export function FlowNav() {
  const { state, dispatch } = useDemo()
  const { overdue, oldest } = attentionSummary(state.actionTimers)

  return (
    <nav className="flow-nav panel" aria-label="Primary">
      <div className="flow-nav__inner">
        <button
          type="button"
          className="flow-nav__brand"
          onClick={() => {
            if (patientKeyFromPath(window.location.pathname)) {
              navigateAppPath('/')
            }
            dispatch({ type: 'SET_ACTIVE_PAGE', page: 'overview' })
            window.scrollTo({ top: 0, behavior: 'smooth' })
          }}
        >
          <span className="flow-nav__brand-mark">MedRef</span>
        </button>

        <div className="flow-nav__actions">
          <button
            type="button"
            className="flow-nav__icon-btn"
            aria-label={
              overdue.length
                ? `Notifications: ${overdue.length} confirmations overdue`
                : 'Notifications'
            }
            onClick={() => {
              if (!oldest) return
              dispatch({ type: 'SET_ACTIVE_PAGE', page: oldest.stageId })
              window.scrollTo({ top: 0, behavior: 'smooth' })
            }}
          >
            <Bell size={18} aria-hidden="true" strokeWidth={2} />
            {overdue.length ? (
              <span className="flow-nav__badge" aria-hidden="true">
                {overdue.length}
              </span>
            ) : null}
          </button>
          <button
            type="button"
            className="flow-nav__icon-btn"
            aria-label="Account"
          >
            <User size={18} aria-hidden="true" strokeWidth={2} />
          </button>
        </div>
      </div>
    </nav>
  )
}
