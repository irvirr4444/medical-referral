import { useState } from 'react'
import {
  buildPeriodImpacts,
  completedMinutesByStage,
  impactBoardCopy,
  type ImpactPeriodId,
  type ImpactScope,
} from '../data/impactPeriods'
import { useDemo } from '../state/useDemo'
import './OverviewImpactBoard.css'

export function OverviewImpactBoard({ scope = 'overview' }: { scope?: ImpactScope }) {
  const { state } = useDemo()
  const copy = impactBoardCopy(scope)
  const extrasByStage = completedMinutesByStage(state.workflowScenarios)
  const periods = buildPeriodImpacts(state.batchMetrics, scope, extrasByStage)
  const [activeId, setActiveId] = useState<ImpactPeriodId>('today')
  const active = periods.find((period) => period.id === activeId) ?? periods[0]
  const headingId = `impact-board-heading-${scope}`

  return (
    <section className="impact-board panel" aria-labelledby={headingId}>
      <div className="section-heading">
        <div>
          <h2 id={headingId}>{copy.title}</h2>
          <p className="muted">{copy.blurb}</p>
        </div>
      </div>

      <div className="impact-board__tabs" role="tablist" aria-label="Capacity period">
        {periods.map((period) => (
          <button
            key={period.id}
            type="button"
            role="tab"
            aria-selected={period.id === active.id}
            className={`impact-board__tab ${period.id === active.id ? 'is-active' : ''}`}
            onClick={() => setActiveId(period.id)}
          >
            {period.label}
          </button>
        ))}
      </div>

      <article className="impact-board__period" aria-live="polite">
        <header>
          <h3>{active.label}</h3>
          <p className="caption">{active.caption}</p>
        </header>
        <p className="impact-board__time">
          <strong>{active.timeLabel}</strong>
          <span>
            {scope === 'overview' ? 'Time returned' : 'Time returned by this stage'}
          </span>
        </p>
        <ul className="impact-board__stats">
          <li>
            <strong>{active.patients}</strong>
            <span>{active.patientLabel}</span>
          </li>
          {active.stats.map((stat) => (
            <li key={stat.label}>
              <strong>{stat.value}</strong>
              <span>{stat.label}</span>
            </li>
          ))}
        </ul>
      </article>
    </section>
  )
}
