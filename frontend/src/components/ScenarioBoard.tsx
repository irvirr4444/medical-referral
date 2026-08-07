import { useEffect, useState } from 'react'
import { CheckCircle2, Clock3, ShieldAlert, Sparkles } from 'lucide-react'
import { WORKFLOW_TAB_MINUTES } from '../data/constants'
import { countScenarioBuckets, scenariosForTab } from '../data/workflowScenarios'
import type { FlowOpsPageId } from '../data/flowOps'
import type { ScenarioBucket, ScenarioCase, WorkflowScenario } from '../data/scenarioTypes'
import { useDemo } from '../state/useDemo'
import './ScenarioBoard.css'

const FILTERS: Array<{ id: ScenarioBucket | 'all'; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'ready', label: 'Ready' },
  { id: 'attention', label: 'Attention' },
  { id: 'blocked', label: 'Blocked' },
  { id: 'approval', label: 'Approval' },
]

function bucketClass(bucket: ScenarioBucket): string {
  return `scenario-bucket scenario-bucket--${bucket}`
}

function StatusPill({ status }: { status: ScenarioCase['status'] }) {
  if (status === 'completed') {
    return (
      <span className="badge badge-ready">
        <CheckCircle2 size={14} aria-hidden="true" />
        Completed
      </span>
    )
  }
  if (status === 'escalated') {
    return (
      <span className="badge badge-blocked">
        <ShieldAlert size={14} aria-hidden="true" />
        Escalated
      </span>
    )
  }
  if (status === 'monitoring') {
    return (
      <span className="badge badge-attention">
        <Clock3 size={14} aria-hidden="true" />
        Monitoring
      </span>
    )
  }
  if (status === 'waiting_human' || status === 'in_progress') {
    return <span className="badge badge-attention">Needs human action</span>
  }
  return <span className="badge badge-neutral">Open</span>
}

function ScenarioCaseCard({ item }: { item: ScenarioCase }) {
  const { dispatch } = useDemo()
  const done = item.status === 'completed' || item.status === 'escalated'

  return (
    <article className={`scenario-case status-${item.status}`}>
      <div className="scenario-case__top">
        <div>
          <h4>{item.patientName}</h4>
          <p>{item.summary}</p>
        </div>
        <StatusPill status={item.status} />
      </div>
      <p className="muted">{item.detail}</p>
      <p className="caption">
        Owner: {item.owner}
        <span aria-hidden="true"> · </span>
        {item.facilityOrContext}
        {item.deadlineLabel ? (
          <>
            <span aria-hidden="true"> · </span>
            {item.deadlineLabel}
          </>
        ) : null}
      </p>
      <div className="scenario-case__footer">
        <span className="chip">{item.minutesReturned} min returned</span>
        {item.humanOnly ? <span className="chip chip-human">Human-controlled</span> : null}
        <button
          type="button"
          className="btn btn-secondary"
          disabled={done}
          onClick={() => dispatch({ type: 'RESOLVE_SCENARIO_CASE', id: item.id })}
        >
          {done ? item.resultLabel : item.actionLabel}
        </button>
      </div>
    </article>
  )
}

function ScenarioSection({ scenario }: { scenario: WorkflowScenario }) {
  return (
    <section className="scenario-section panel" aria-labelledby={`scenario-${scenario.id}`}>
      <div className="scenario-section__header">
        <div>
          <p className={`caption ${bucketClass(scenario.bucket)}`}>{scenario.branchLabel}</p>
          <h3 id={`scenario-${scenario.id}`}>{scenario.title}</h3>
          <p className="muted">{scenario.description}</p>
        </div>
        <span className="chip">{scenario.cases.length} cases</span>
      </div>
      <div className="scenario-section__rules">
        <p>
          <strong>Rule:</strong> {scenario.rule}
        </p>
        <p className="caption">
          <strong>Human control:</strong> {scenario.humanControlNote}
        </p>
      </div>
      <ul className="scenario-section__cases">
        {scenario.cases.map((item) => (
          <li key={item.id}>
            <ScenarioCaseCard item={item} />
          </li>
        ))}
      </ul>
    </section>
  )
}

export function ScenarioBoard({ tab }: { tab: FlowOpsPageId }) {
  const { state, dispatch } = useDemo()
  const allForTab = scenariosForTab(state.workflowScenarios, tab)
  const availableFilters = FILTERS.filter(
    (filter) =>
      filter.id === 'all' || allForTab.some((item) => item.bucket === filter.id),
  )
  const activeFilter =
    availableFilters.some((filter) => filter.id === state.scenarioFilter)
      ? state.scenarioFilter
      : 'all'
  const filtered =
    activeFilter === 'all'
      ? allForTab
      : allForTab.filter((item) => item.bucket === activeFilter)
  const counts = countScenarioBuckets(allForTab)
  const typicalMinutes = WORKFLOW_TAB_MINUTES[tab] ?? 10
  const tabMinutesCaptured = allForTab
    .flatMap((item) => item.cases)
    .filter((item) => item.status === 'completed' || item.status === 'escalated')
    .reduce((sum, item) => sum + item.minutesReturned, 0)
  const [activeQueueId, setActiveQueueId] = useState(filtered[0]?.id ?? '')

  useEffect(() => {
    if (activeFilter !== state.scenarioFilter) {
      dispatch({ type: 'SET_SCENARIO_FILTER', filter: 'all' })
    }
  }, [activeFilter, state.scenarioFilter, dispatch, tab])

  useEffect(() => {
    const stillVisible = filtered.some((item) => item.id === activeQueueId)
    if (!stillVisible) {
      setActiveQueueId(filtered[0]?.id ?? '')
    }
  }, [tab, activeFilter, filtered, activeQueueId])

  const activeQueue = filtered.find((item) => item.id === activeQueueId) ?? null

  return (
    <section className="scenario-board" aria-label="Live work queue">
      <div className="scenario-board__summary panel">
        <div className="section-heading">
          <div>
            <h2>
              <Sparkles size={18} aria-hidden="true" /> Live work queue
            </h2>
            <p className="muted">
              Live cases on this stage — open a queue to confirm, escalate, or clear work.
            </p>
          </div>
          <div className="scenario-board__chips">
            <span className="chip">{typicalMinutes} min / typical case</span>
            {tabMinutesCaptured > 0 ? (
              <span className="chip">{tabMinutesCaptured} captured on this stage</span>
            ) : null}
          </div>
        </div>
        <div className="scenario-board__metrics" aria-label="Queue status">
          <article>
            <strong>{counts.scenarioCount}</strong>
            <span>Queues</span>
          </article>
          <article>
            <strong>{counts.totalCases}</strong>
            <span>Cases</span>
          </article>
          <article>
            <strong>{counts.openCases}</strong>
            <span>Open actions</span>
          </article>
          <article>
            <strong>{counts.ready}</strong>
            <span>Ready</span>
          </article>
          <article>
            <strong>{counts.attention}</strong>
            <span>Attention</span>
          </article>
          <article>
            <strong>{counts.blocked + counts.approval}</strong>
            <span>Blocked / approval</span>
          </article>
        </div>
        <div className="scenario-board__filters" role="toolbar" aria-label="Queue filters">
          {availableFilters.map((filter) => (
            <button
              key={filter.id}
              type="button"
              className={`btn ${activeFilter === filter.id ? 'btn-primary' : 'btn-secondary'}`}
              aria-pressed={activeFilter === filter.id}
              onClick={() => dispatch({ type: 'SET_SCENARIO_FILTER', filter: filter.id })}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {filtered.length > 0 ? (
        <div className="scenario-board__tabs panel" role="tablist" aria-label="Queues on this stage">
          {filtered.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={item.id === activeQueueId}
              className={`scenario-board__tab ${item.id === activeQueueId ? 'is-active' : ''}`}
              onClick={() => setActiveQueueId(item.id)}
            >
              <span className={`scenario-board__tab-bucket ${bucketClass(item.bucket)}`}>
                {item.branchLabel}
              </span>
              <strong>{item.title}</strong>
              <span className="caption">{item.cases.length} cases</span>
            </button>
          ))}
        </div>
      ) : null}

      <div className="scenario-board__list">
        {activeQueue ? <ScenarioSection scenario={activeQueue} /> : null}
        {filtered.length === 0 ? (
          <p className="caption panel" style={{ padding: '1rem' }}>
            No queues match this filter on this stage.
          </p>
        ) : null}
      </div>

      <StageExceptions scenarios={allForTab} />
    </section>
  )
}

function StageExceptions({ scenarios }: { scenarios: WorkflowScenario[] }) {
  const openExceptions = flattenOpenExceptions(scenarios).slice(0, 8)
  if (openExceptions.length === 0) return null

  return (
    <div className="stage-exceptions panel">
      <h3>Active exceptions & approvals</h3>
      <p className="muted">Open attention, blocked, and approval cases on this stage.</p>
      <ul>
        {openExceptions.map((item) => (
          <li key={item.id}>
            <strong>{item.patientName}</strong>
            <span>
              {item.summary}
              <span aria-hidden="true"> · </span>
              {item.owner}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function OverviewScenarioSummary() {
  const { state } = useDemo()
  const totals = countScenarioBuckets(state.workflowScenarios)
  const approvals = state.workflowScenarios.filter((s) => s.bucket === 'approval').length
  const blocked = state.workflowScenarios.filter((s) => s.bucket === 'blocked').length

  return (
    <section className="overview-scenarios panel" aria-labelledby="overview-scenarios-heading">
      <div className="section-heading">
        <div>
          <h2 id="overview-scenarios-heading">Live workflow command summary</h2>
          <p className="muted">
            Cross-stage queue counts, exceptions, and approvals waiting — without claiming
            autonomous clinical decisions.
          </p>
        </div>
      </div>

      <div className="scenario-board__metrics">
        <article>
          <strong>{totals.scenarioCount}</strong>
          <span>Queues across workflow</span>
        </article>
        <article>
          <strong>{totals.totalCases}</strong>
          <span>Live cases</span>
        </article>
        <article>
          <strong>{totals.openCases}</strong>
          <span>Open actions</span>
        </article>
        <article>
          <strong>{approvals}</strong>
          <span>Approval queues</span>
        </article>
        <article>
          <strong>{blocked}</strong>
          <span>Blocked queues</span>
        </article>
        <article>
          <strong>
            {state.scenarioMinutesReturned > 0
              ? state.scenarioMinutesReturned
              : Object.values(WORKFLOW_TAB_MINUTES).reduce((sum, n) => sum + n, 0)}
          </strong>
          <span>
            {state.scenarioMinutesReturned > 0
              ? 'Minutes captured today'
              : 'Minutes across typical cases'}
          </span>
        </article>
      </div>
    </section>
  )
}

function flattenOpenExceptions(scenarios: WorkflowScenario[]) {
  return scenarios
    .filter(
      (scenario) =>
        scenario.bucket === 'blocked' ||
        scenario.bucket === 'approval' ||
        scenario.bucket === 'attention',
    )
    .flatMap((scenario) =>
      scenario.cases
        .filter((item) => item.status !== 'completed' && item.status !== 'escalated')
        .map((item) => ({ ...item, scenarioTitle: scenario.title })),
    )
}
