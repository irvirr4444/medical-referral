import { computeImpact, formatMinutes } from '../data/constants'
import { CountUp } from './CountUp'
import { useDemo } from '../state/useDemo'
import './ImpactStrip.css'

export function ImpactStrip() {
  const { state, dispatch } = useDemo()
  const m = state.batchMetrics
  const projection = computeImpact(state.impactAssumptions)

  const cards = [
    {
      value: m.timeReturnedMinutes,
      format: formatMinutes,
      label: 'Time returned today',
    },
    {
      value: m.manualActionsAvoided,
      format: String,
      label: 'Manual actions avoided',
    },
    {
      value: m.pagesAnalyzed,
      format: String,
      label: 'PDF pages analyzed',
    },
    {
      value: m.mondayPreviewsGenerated + m.drkDraftsGenerated,
      format: String,
      label: 'Destination previews/drafts generated',
    },
    {
      value: m.incompleteOrUnclear,
      format: String,
      label: 'Incomplete referrals found early',
    },
    {
      value: m.probableDuplicatesBlocked,
      format: String,
      label: 'Possible duplicates blocked',
    },
  ]

  return (
    <section className="impact-strip panel" aria-labelledby="impact-heading">
      <div className="section-heading">
        <div>
          <h2 id="impact-heading">Today’s referral impact</h2>
          <p className="muted">Capacity returned to the existing team from intake through destination prep.</p>
        </div>
        <div className="impact-strip__actions">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              dispatch({ type: 'SET_ACTIVE_PAGE', page: 'overview' })
              window.scrollTo({ top: 0, behavior: 'smooth' })
            }}
          >
            How the workflow changed
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => dispatch({ type: 'TOGGLE_HOW_CALCULATED' })}
            aria-expanded={state.howCalculatedOpen}
          >
            How calculated
          </button>
        </div>
      </div>

      <div className="grid-cards">
        {cards.map((card) => (
          <article key={card.label} className="metric-card">
            <strong>
              <CountUp value={card.value} format={card.format} />
            </strong>
            <span>{card.label}</span>
          </article>
        ))}
      </div>

      <div className="secondary-metrics" aria-label="Secondary impact metrics">
        <span className="chip">{projection.reductionPercent}% less admin touch time</span>
        <span className="chip">{m.readyForConfirmation} ready for confirmation</span>
        <span className="chip">
          {Math.round(projection.hoursPerYear)} projected annual hours
        </span>
        <span className="chip">
          {projection.fteEquivalent.toFixed(1)} full-time staff capacity returned
        </span>
      </div>

      {state.howCalculatedOpen ? (
        <div className="impact-strip__drawer" role="region" aria-label="How calculated">
          <p>
            Manual processing is modeled at {state.impactAssumptions.manualMinutes} minutes per
            referral. Assisted review is modeled at {state.impactAssumptions.assistedMinutes}{' '}
            minutes. The difference is treated as capacity returned to WCW employees.
          </p>
        </div>
      ) : null}
    </section>
  )
}
