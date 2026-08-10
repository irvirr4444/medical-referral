import {
  ArrowRight,
  Eye,
  GitBranch,
  MessageSquareText,
  Target,
} from 'lucide-react'
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
      <section className="automation-overview__hero panel">
        <div>
          <h1 id="automation-overview-title">
            Referral Intake & Scheduling
          </h1>
          <div className="automation-overview__goal">
            <span className="automation-overview__goal-label">
              <Target size={18} aria-hidden="true" />
              Goal
            </span>
            <p>
              Ensure every valid referral becomes a scheduled, continuously
              tracked patient case through treatment completion or discharge.
            </p>
          </div>
        </div>
      </section>

      <section
        className="automation-guide panel"
        aria-labelledby="automation-guide-title"
      >
        <div className="section-heading">
          <div>
            <p className="caption">How to use this console</p>
            <h2 id="automation-guide-title">
              Inspect, verify, and improve the workflow
            </h2>
          </div>
        </div>
        <div className="automation-guide__grid">
          <article>
            <GitBranch size={22} aria-hidden="true" />
            <h3>Follow the sequence</h3>
            <p>
              See the trigger, purpose, and expected handoff for every
              step.
            </p>
          </article>
          <article>
            <Eye size={22} aria-hidden="true" />
            <h3>Inspect inputs and outputs</h3>
            <p>
              Compare what the automation received with what it produced and
              validated.
            </p>
          </article>
          <article>
            <MessageSquareText size={22} aria-hidden="true" />
            <h3>Comment in context</h3>
            <p>
              Attach feedback to the exact run and step that needs
              correction.
            </p>
          </article>
        </div>
      </section>

      <section
        className="automation-stage-map panel"
        aria-labelledby="automation-stage-map-title"
      >
        <div className="section-heading">
          <div>
            <h2 id="automation-stage-map-title">Seven inspectable stages</h2>
          </div>
        </div>
        <ol className="automation-stage-map__grid">
          {AUTOMATION_STAGES.map((stage) => (
            <li key={stage.id}>
              <button
                type="button"
                className="automation-stage-card"
                onClick={() => openStage(stage.id)}
                aria-label={`Inspect ${stage.shortTitle}`}
              >
                <span className="automation-stage-card__top">
                  <span className="automation-stage-card__number">
                    {AUTOMATION_STAGES.indexOf(stage) + 1}
                  </span>
                </span>
                <strong>{stage.shortTitle}</strong>
                <span>{stage.purpose}</span>
                <span className="automation-stage-card__footer">
                  {stage.microsteps.length} steps
                  <ArrowRight size={16} aria-hidden="true" />
                </span>
              </button>
            </li>
          ))}
        </ol>
      </section>
    </main>
  )
}
