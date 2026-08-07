import { COPY } from '../data/constants'
import { ActivityFeed } from './ActivityFeed'
import { CapacityCalculator } from './CapacityCalculator'
import { NetworkPanel } from './NetworkPanel'
import { OverviewImpactBoard } from './OverviewImpactBoard'
import { OverviewScenarioSummary } from './ScenarioBoard'
import './WorkflowModal.css'

/** Overview page — capacity returned by period, command summary, network. */
export function OverviewPage() {
  return (
    <>
      <section className="workflow-page panel" aria-labelledby="workflow-page-title">
        <div className="section-heading">
          <div>
            <p className="caption">Referral → Scheduling → Visit Workflow</p>
            <h2 id="workflow-page-title">Overview</h2>
            <p className="muted">{COPY.beforeAfterHeadline}</p>
          </div>
        </div>
      </section>
      <OverviewImpactBoard scope="overview" />
      <OverviewScenarioSummary />
      <ActivityFeed stage="overview" />
      <NetworkPanel />
      <CapacityCalculator />
    </>
  )
}
