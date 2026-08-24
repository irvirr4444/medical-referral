import { Bell, User } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { actionLabel, attentionSummary } from '../features/automation/confirmationTimers'
import { STAGE_LABEL } from '../features/automation/ops'
import type { ActionTimer } from '../types'
import { navigateAppPath, patientKeyFromPath } from '../features/automation/patientRoute'
import { useEscapeDismiss } from '../hooks/useEscapeDismiss'
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
  const { overdue, warning } = attentionSummary(state.actionTimers)
  const notifications = [...overdue, ...warning]

  const [notifOpen, setNotifOpen] = useState(false)
  const notifRef = useRef<HTMLDivElement | null>(null)

  useEscapeDismiss(notifOpen, () => setNotifOpen(false))

  useEffect(() => {
    if (!notifOpen) return
    const onPointerDown = (event: PointerEvent) => {
      if (!notifRef.current?.contains(event.target as Node)) {
        setNotifOpen(false)
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [notifOpen])

  const openNotification = (timer: ActionTimer) => {
    setNotifOpen(false)
    if (patientKeyFromPath(window.location.pathname)) {
      navigateAppPath('/')
    }
    dispatch({ type: 'SET_ACTIVE_PAGE', page: timer.stageId })
    dispatch({
      type: 'SET_OPS_SELECTED_STEP',
      stageId: timer.stageId,
      stepId: timer.stepId,
    })
    dispatch({
      type: 'SCOPE_OPS_PATIENT',
      patientId: timer.patientId,
      patientName: timer.patientName,
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

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
          <div className="flow-nav__notif" ref={notifRef}>
            <button
              type="button"
              className="flow-nav__icon-btn"
              aria-label={
                overdue.length
                  ? `Notifications: ${overdue.length} confirmations overdue`
                  : 'Notifications'
              }
              aria-haspopup="true"
              aria-expanded={notifOpen}
              onClick={() => setNotifOpen((open) => !open)}
            >
              <Bell size={18} aria-hidden="true" strokeWidth={2} />
              {overdue.length ? (
                <span className="flow-nav__badge" aria-hidden="true">
                  {overdue.length}
                </span>
              ) : null}
            </button>

            {notifOpen ? (
              <div className="flow-nav__notif-panel" role="dialog" aria-label="Notifications">
                <header className="flow-nav__notif-header">
                  <h2>Notifications</h2>
                  {overdue.length ? <span>{overdue.length} overdue</span> : null}
                </header>
                {notifications.length ? (
                  <ul className="flow-nav__notif-list">
                    {notifications.map((timer) => (
                      <li key={timer.id}>
                        <button
                          type="button"
                          className="flow-nav__notif-item"
                          onClick={() => openNotification(timer)}
                        >
                          <span
                            className={`flow-nav__notif-dot flow-nav__notif-dot--${timer.status}`}
                            aria-hidden="true"
                          />
                          <span className="flow-nav__notif-copy">
                            <span className="flow-nav__notif-title">
                              {timer.patientName}
                            </span>
                            <span className="flow-nav__notif-meta">
                              {actionLabel(timer.actionId)} · {STAGE_LABEL[timer.stageId]}
                            </span>
                          </span>
                          <span
                            className={`flow-nav__notif-state flow-nav__notif-state--${timer.status}`}
                          >
                            {timer.status === 'overdue' ? 'Overdue' : 'Due soon'}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="flow-nav__notif-empty">You're all caught up.</p>
                )}
              </div>
            ) : null}
          </div>
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
