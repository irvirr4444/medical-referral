import { useEffect, useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { OverviewImpactBoard } from '../../components/OverviewImpactBoard'
import { useDemo } from '../../state/useDemo'
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
          <p className="overview-masthead__sub">
            Referral Intake & Scheduling
          </p>
        </div>
      </header>

      <div className="overview-dashboard">
        <aside className="overview-quick panel-dark" aria-label="Steps">
          <p className="mono-label">Steps</p>
          <ul className="overview-quick__list">
            {AUTOMATION_STAGES.map((stage, index) => (
              <li key={stage.id}>
                <button
                  type="button"
                  className="overview-quick__link"
                  aria-label={`Inspect ${stage.shortTitle}`}
                  onClick={() => openStage(stage.id)}
                >
                  <span className="overview-quick__index">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="overview-quick__title">{stage.shortTitle}</span>
                  <ArrowRight size={14} aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <OverviewImpactBoard density="compact" title="Objectives" />
      </div>
    </main>
  )
}
