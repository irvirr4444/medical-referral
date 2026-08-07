import { useEffect, useState } from 'react'
import { WORKFLOW_TAB_MINUTES } from '../data/constants'
import { FLOW_OPS, type FlowOpsPageId } from '../data/flowOps'
import { scenarioCaseIsOpen } from '../data/scenarioTypes'
import { scenariosForTab } from '../data/workflowScenarios'
import { WORKFLOW_COMPARISONS } from '../data/workflowComparisons'
import { useDemo } from '../state/useDemo'
import { ActivityFeed } from './ActivityFeed'
import { ImpactStrip } from './ImpactStrip'
import { OverviewImpactBoard } from './OverviewImpactBoard'
import { ReferralWorkspace } from './ReferralWorkspace'
import { ScenarioBoard } from './ScenarioBoard'
import { WorkflowSpine } from './WorkflowSpine'
import './WorkflowModal.css'
import './StageOperationsPage.css'

type StageView = 'action' | 'metrics'

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

function openActionCount(scenarios: ReturnType<typeof scenariosForTab>) {
  return new Set(
    scenarios
    .flatMap((scenario) => scenario.cases)
      .filter((item) => scenarioCaseIsOpen(item.status))
      .map((item) => item.patientName),
  ).size
}

/** Operations-style live page for Flow sections 1–7. */
export function StageOperationsPage({ pageId }: { pageId: FlowOpsPageId }) {
  const { state } = useDemo()
  const config = FLOW_OPS[pageId]
  const [view, setView] = useState<StageView>('action')
  const openCount = openActionCount(scenariosForTab(state.workflowScenarios, pageId))

  useEffect(() => {
    setView('action')
  }, [pageId, state.journeyFocusCaseId])

  return (
    <>
      <header className="stage-ops-hero">
        <p className="caption">Live operations</p>
        <h2>{config.title}</h2>
        <p className="muted">{config.blurb}</p>
      </header>

      <div className="stage-ops-tabs panel" role="tablist" aria-label={`${config.title} views`}>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'action'}
          className={`stage-ops-tabs__tab ${view === 'action' ? 'is-active' : ''}`}
          onClick={() => setView('action')}
        >
          Action
          <span className="stage-ops-tabs__count">{openCount} patients</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'metrics'}
          className={`stage-ops-tabs__tab ${view === 'metrics' ? 'is-active' : ''}`}
          onClick={() => setView('metrics')}
        >
          Automation impact
        </button>
      </div>

      {view === 'action' ? (
        <div className="stage-ops-pane" role="tabpanel" aria-label="Action">
          <ScenarioBoard key={pageId} tab={pageId} actionOnly />
          {pageId === 'intake' ? <ReferralWorkspace /> : null}
        </div>
      ) : (
        <div className="stage-ops-pane" role="tabpanel" aria-label="Automation impact">
          <OverviewImpactBoard scope={pageId} />
          <StageComparisonStrip pageId={pageId} />
          {config.showImpact ? <ImpactStrip /> : null}
          {config.showSpine ? <WorkflowSpine /> : null}
          {config.showActivity ? <ActivityFeed stage={pageId} /> : null}
        </div>
      )}
    </>
  )
}
