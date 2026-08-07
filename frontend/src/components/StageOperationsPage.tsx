import { Play, RefreshCw } from 'lucide-react'
import { WAITING_INBOX_COUNT, WORKFLOW_TAB_MINUTES } from '../data/constants'
import { FLOW_OPS, type FlowOpsPageId } from '../data/flowOps'
import { scenariosForTab } from '../data/workflowScenarios'
import { WORKFLOW_COMPARISONS } from '../data/workflowComparisons'
import { useDemo } from '../state/useDemo'
import { ActivityFeed } from './ActivityFeed'
import { ImpactStrip } from './ImpactStrip'
import { OverviewImpactBoard } from './OverviewImpactBoard'
import { ReferralQueue } from './ReferralQueue'
import { ReferralWorkspace } from './ReferralWorkspace'
import { ScenarioBoard } from './ScenarioBoard'
import { WorkflowSpine } from './WorkflowSpine'
import './WorkflowModal.css'
import './StageOperationsPage.css'

function StageComparisonStrip({ pageId }: { pageId: FlowOpsPageId }) {
  const { state } = useDemo()
  const config = FLOW_OPS[pageId]
  const comparison = WORKFLOW_COMPARISONS.find((item) => item.id === config.comparisonId)
  const examplePatients = scenariosForTab(state.workflowScenarios, pageId)
    .flatMap((scenario) => scenario.cases.map((item) => item.patientName))
    .filter((name, index, all) => all.indexOf(name) === index)
    .slice(0, 4)

  if (!comparison) return null

  return (
    <section className="stage-compare panel" aria-label="Before and after for this stage">
      <div className="stage-compare__meta">
        <p>
          <strong>{WORKFLOW_TAB_MINUTES[pageId] ?? 10} minutes</strong> returned per typical case
        </p>
        <p className="caption">Example patients: {examplePatients.join(' · ')}</p>
      </div>
      <div className="workflow-modal__grid">
        <article>
          <h3>Before</h3>
          <ol>
            {comparison.before.slice(0, 6).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </article>
        <article>
          <h3>With automation</h3>
          <ol>
            {comparison.after.slice(0, 6).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </article>
      </div>
      <p className="workflow-modal__value">{comparison.value}</p>
    </section>
  )
}

function IntakeActions() {
  const { state, dispatch, runAutomation } = useDemo()
  const waiting = state.referrals.filter((r) => r.inboxBatch && !r.processed).length
  const inboxLabel = state.automationComplete
    ? `${WAITING_INBOX_COUNT} processed`
    : `${waiting || WAITING_INBOX_COUNT} waiting`

  return (
    <div className="stage-ops-actions panel">
      <p className="caption" aria-live="polite">
        Inbox <strong>{inboxLabel}</strong>
        <span aria-hidden="true"> · </span>
        Sync {state.lastInboxSyncLabel}
      </p>
      <div className="stage-ops-actions__buttons">
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
  )
}

/** Operations-style live page for Flow sections 1–5. */
export function StageOperationsPage({ pageId }: { pageId: FlowOpsPageId }) {
  const config = FLOW_OPS[pageId]

  return (
    <>
      <header className="stage-ops-hero">
        <p className="caption">Live operations</p>
        <h2>{config.title}</h2>
        <p className="muted">{config.blurb}</p>
      </header>

      {pageId === 'intake' ? <IntakeActions /> : null}

      <OverviewImpactBoard scope={pageId} />
      <StageComparisonStrip pageId={pageId} />
      <ScenarioBoard key={pageId} tab={pageId} />

      {config.showImpact ? <ImpactStrip /> : null}
      {config.showSpine ? <WorkflowSpine /> : null}
      {config.showActivity ? <ActivityFeed stage={pageId} /> : null}
      {config.showQueue ? (
        <>
          <ReferralQueue />
          <ReferralWorkspace />
        </>
      ) : null}
    </>
  )
}
