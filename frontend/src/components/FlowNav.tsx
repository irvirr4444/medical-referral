import { User } from 'lucide-react'
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
  const { dispatch } = useDemo()

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

        <button
          type="button"
          className="flow-nav__account"
          aria-label="Account"
        >
          <User size={18} aria-hidden="true" strokeWidth={2} />
        </button>
      </div>
    </nav>
  )
}
