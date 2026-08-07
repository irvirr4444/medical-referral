import { useEffect, useState } from 'react'
import { RefreshCw, Play } from 'lucide-react'
import { COPY, OPERATING_DATE, WAITING_INBOX_COUNT } from '../data/constants'
import { useDemo } from '../state/useDemo'
import './HeaderBar.css'

export function HeaderBar() {
  const { state, dispatch, runAutomation } = useDemo()
  const [clock, setClock] = useState(() => new Date())
  const waiting = state.referrals.filter((r) => r.inboxBatch && !r.processed).length
  const inboxLabel = state.automationComplete
    ? `${WAITING_INBOX_COUNT} processed`
    : `${waiting || WAITING_INBOX_COUNT} waiting`

  useEffect(() => {
    const id = window.setInterval(() => setClock(new Date()), 30_000)
    return () => window.clearInterval(id)
  }, [])

  const clockLabel = clock.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })

  return (
    <header className="header-bar panel">
      <div className="header-bar__brand">
        <p className="header-bar__eyebrow">West Coast Wound</p>
        <h1>WCW Referral Operations</h1>
      </div>
      <div className="header-bar__meta">
        <div className="header-bar__status" aria-live="polite">
          <span className="badge badge-live" role="status">
            {COPY.liveBadge}
          </span>
          <span className="header-bar__status-line">
            {OPERATING_DATE} · {clockLabel}
            <span className="header-bar__dot" aria-hidden="true">
              ·
            </span>
            Sync {state.lastInboxSyncLabel}
            <span className="header-bar__dot" aria-hidden="true">
              ·
            </span>
            Inbox <strong>{inboxLabel}</strong>
          </span>
        </div>
        <div className="header-bar__actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={runAutomation}
            disabled={state.automationRunning || state.automationComplete}
            aria-label="Process referral inbox"
          >
            <Play size={16} aria-hidden="true" />
            Process referral inbox
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => dispatch({ type: 'RESET' })}
            aria-label="Reset day"
          >
            <RefreshCw size={16} aria-hidden="true" />
            Reset day
          </button>
        </div>
      </div>
    </header>
  )
}
