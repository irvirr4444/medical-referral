import { WORKFLOW_MODAL_TABS } from '../data/constants'
import { useDemo } from '../state/useDemo'
import './FlowNav.css'

export const APP_NAV_ITEMS = [...WORKFLOW_MODAL_TABS] as const

export type AppPageId = (typeof APP_NAV_ITEMS)[number]['id']

export function FlowNav() {
  const { state, dispatch } = useDemo()

  return (
    <nav className="flow-nav" aria-label="Primary">
      <div className="flow-nav__inner">
        <button
          type="button"
          className="flow-nav__brand"
          onClick={() => {
            dispatch({ type: 'SET_ACTIVE_PAGE', page: 'overview' })
            window.scrollTo({ top: 0, behavior: 'smooth' })
          }}
        >
          <span className="flow-nav__brand-mark">WCW</span>
          <span className="flow-nav__brand-sub">Referral Ops</span>
        </button>

        <div className="flow-nav__tabs" role="presentation">
          {APP_NAV_ITEMS.map((item) => {
            const active = state.activePage === item.id
            return (
              <button
                key={item.id}
                type="button"
                className={`flow-nav__link ${active ? 'is-active' : ''}`}
                aria-current={active ? 'page' : undefined}
                onClick={() => {
                  dispatch({ type: 'SET_ACTIVE_PAGE', page: item.id })
                  window.scrollTo({ top: 0, behavior: 'smooth' })
                }}
              >
                {item.label}
              </button>
            )
          })}
        </div>
      </div>
    </nav>
  )
}
