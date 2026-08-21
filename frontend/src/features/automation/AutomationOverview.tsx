import { useEffect, useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { useDemo } from '../../state/useDemo'
import { OverviewNeedsYou } from './OverviewNeedsYou'
import { AUTOMATION_STAGES } from './stages'
import './AutomationOverview.css'

export function AutomationOverview() {
  const { dispatch } = useDemo()
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 30_000)
    return () => window.clearInterval(id)
  }, [])

  const dateLabel = now.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
  const clockLabel = now.toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  })

  const openStage = (stageId: string) => {
    dispatch({ type: 'SET_ACTIVE_PAGE', page: stageId })
    dispatch({ type: 'SELECT_REFERRAL', id: null })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <main
      className="automation-overview"
      aria-labelledby="automation-overview-title"
    >
      <header className="overview-masthead">
        <div className="overview-masthead__copy">
          <p className="mono-label">
            {dateLabel} · {clockLabel}
          </p>
          <h1 id="automation-overview-title">Intake Automation</h1>
          <p className="overview-masthead__desc">
            Every referral is tracked automatically from inbox to scheduled
            visit you only confirm the decisions below.
          </p>
        </div>
      </header>

      <OverviewNeedsYou />

      <nav className="overview-flow" aria-label="Steps">
        <span className="overview-flow__label">How it works</span>
        <ol className="overview-flow__list">
          {AUTOMATION_STAGES.map((stage, index) => (
            <li key={stage.id}>
              <button
                type="button"
                className="overview-flow__link"
                aria-label={`Inspect ${stage.shortTitle}`}
                onClick={() => openStage(stage.id)}
              >
                <span className="overview-flow__index">
                  {String(index + 1).padStart(2, '0')}
                </span>
                {stage.shortTitle}
              </button>
              {index < AUTOMATION_STAGES.length - 1 ? (
                <ArrowRight
                  size={12}
                  strokeWidth={2}
                  className="overview-flow__arrow"
                  aria-hidden="true"
                />
              ) : null}
            </li>
          ))}
        </ol>
      </nav>
    </main>
  )
}
