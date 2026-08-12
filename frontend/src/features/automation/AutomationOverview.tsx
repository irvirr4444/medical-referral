import { ArrowRight, Target } from 'lucide-react'
import { ActivityFeed } from '../../components/ActivityFeed'
import { OverviewImpactBoard } from '../../components/OverviewImpactBoard'
import { OPERATING_DATE } from '../../data/constants'
import { OVERVIEW_ATTENTION_BUCKETS } from '../../data/overviewAttention'
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

        <OverviewImpactBoard density="compact" title="Objectives" showChart />
      </div>

      <div className="overview-lower">
        <section
          className="overview-attention panel"
          aria-labelledby="overview-attention-title"
        >
          <div className="section-heading">
            <div>
              <p className="mono-label">Queues</p>
              <h2 id="overview-attention-title">Needs attention</h2>
            </div>
          </div>
          <div className="overview-attention__grid">
            {OVERVIEW_ATTENTION_BUCKETS.map((bucket) => (
              <article
                key={bucket.id}
                className={`overview-attention__bucket is-${bucket.tone}`}
              >
                <header>
                  <h3 className="mono-label">{bucket.title}</h3>
                  <strong className="stat-number">
                    {String(bucket.items.length).padStart(2, '0')}
                  </strong>
                </header>
                <ul>
                  {bucket.items.map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        className="overview-attention__row"
                        aria-label={`Open ${item.name} in ${item.stageLabel}`}
                        onClick={() => openStage(item.stageId)}
                      >
                        <span className="overview-attention__copy">
                          <strong>{item.name}</strong>
                          <small>{item.detail}</small>
                        </span>
                        <span className="overview-attention__meta mono-label">
                          {item.stageLabel}
                          <span aria-hidden="true">View ↗</span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <ActivityFeed stage="overview" />
      </div>
    </main>
  )
}
