import { ArrowRight, Eye, GitBranch, MessageSquareText } from 'lucide-react'
import { useDemo } from '../../state/useDemo'
import { AUTOMATION_STAGES } from './stages'
import { ImplementationBadge } from './StatusBadge'
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
          <p className="caption">WCW automation inspection console</p>
          <h1 id="automation-overview-title">
            Understand every step from referral to visit review
          </h1>
          <p className="automation-overview__lead">
            This console explains what starts each automation, what information
            it receives, what it produces, and where a WCW employee keeps
            control. Open any stage to inspect every microstep in execution
            order.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary automation-overview__walkthrough"
          onClick={() => openStage('intake')}
        >
          Walk through one referral
          <ArrowRight size={18} aria-hidden="true" />
        </button>
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
              microstep.
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
              Attach feedback to the exact run and microstep that needs
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
            <p className="caption">The complete workflow</p>
            <h2 id="automation-stage-map-title">Seven inspectable stages</h2>
            <p className="muted">
              Status describes current implementation maturity, not whether a
              clinical decision has been automated.
            </p>
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
                  <ImplementationBadge status={stage.implementationStatus} />
                </span>
                <strong>{stage.shortTitle}</strong>
                <span>{stage.purpose}</span>
                <span className="automation-stage-card__footer">
                  {stage.microsteps.length} microsteps
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
