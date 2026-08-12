import { ArrowRight, Target } from 'lucide-react'
import { OverviewImpactBoard } from '../../components/OverviewImpactBoard'
import { OPERATING_DATE } from '../../data/constants'
import { useDemo } from '../../state/useDemo'
import { AUTOMATION_STAGES } from './stages'
import './AutomationOverview.css'

export function AutomationOverview() {
  const { dispatch } = useDemo()

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
          <p className="mono-label">{OPERATING_DATE}</p>
          <h1 id="automation-overview-title">Today&apos;s Overview</h1>
          <p className="overview-masthead__sub">
            Referral Intake & Scheduling
          </p>
        </div>
        <div className="overview-masthead__aside">
          <div className="overview-masthead__goal panel-dark">
            <span className="mono-label">
              <Target size={14} aria-hidden="true" />
              Goal
            </span>
            <p>
              Ensure every valid referral becomes a scheduled, continuously
              tracked patient case through treatment completion or discharge.
            </p>
          </div>
        </div>
      </header>

      <div className="overview-dashboard">
        <aside className="overview-quick panel-dark" aria-label="Quick access">
          <p className="mono-label">Quick access</p>
          <ul className="overview-quick__list">
            {AUTOMATION_STAGES.map((stage, index) => (
              <li key={stage.id}>
                <button
                  type="button"
                  className="overview-quick__link"
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

        <OverviewImpactBoard
          density="compact"
          title="Objectives"
          showChart
        />
      </div>

      <section
        className="automation-stage-map panel"
        aria-labelledby="automation-stage-map-title"
      >
        <div className="section-heading">
          <div>
            <p className="mono-label">Pipeline</p>
            <h2 id="automation-stage-map-title">Seven inspectable stages</h2>
          </div>
        </div>
        <ol className="automation-stage-map__grid">
          {AUTOMATION_STAGES.map((stage, index) => (
            <li key={stage.id}>
              <button
                type="button"
                className="automation-stage-card"
                onClick={() => openStage(stage.id)}
                aria-label={`Inspect ${stage.shortTitle}`}
              >
                <span className="automation-stage-card__top">
                  <span className="automation-stage-card__number">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="automation-stage-card__steps mono-label">
                    {stage.microsteps.length} steps
                  </span>
                </span>
                <strong>{stage.shortTitle}</strong>
                <span className="automation-stage-card__blurb">{stage.purpose}</span>
                <span className="automation-stage-card__footer">
                  Open stage
                  <ArrowRight size={14} aria-hidden="true" />
                </span>
              </button>
            </li>
          ))}
        </ol>
      </section>
    </main>
  )
}
