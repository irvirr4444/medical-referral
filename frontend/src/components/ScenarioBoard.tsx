import { useEffect, useState } from 'react'
import { CheckCircle2, Clock3, FileText, ShieldAlert, Sparkles } from 'lucide-react'
import { WORKFLOW_TAB_MINUTES } from '../data/constants'
import {
  JOURNEY_STAGE_ORDER,
  patientIdForJourneyCase,
  scenarioContainingCase,
} from '../data/patientJourney'
import { countScenarioBuckets, scenariosForTab } from '../data/workflowScenarios'
import { FLOW_OPS, type FlowOpsPageId } from '../data/flowOps'
import {
  scenarioCaseIsOpen,
  type ScenarioBucket,
  type ScenarioCase,
  type WorkflowScenario,
} from '../data/scenarioTypes'
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
  if (status === 'upcoming') {
    return <span className="badge badge-neutral">Upcoming stage</span>
  }
  if (status === 'waiting_human' || status === 'in_progress') {
    return <span className="badge badge-attention">Needs human action</span>
  }
  return <span className="badge badge-neutral">Open</span>
}

function ScenarioCaseCard({
  item,
  highlighted,
}: {
  item: ScenarioCase
  highlighted: boolean
}) {
  const { dispatch } = useDemo()
  const done = item.status === 'completed' || item.status === 'escalated'

  return (
    <article
      className={`scenario-case status-${item.status}${highlighted ? ' is-journey-focus' : ''}`}
      data-journey-focus={highlighted ? 'true' : undefined}
    >
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
          onClick={() => {
            dispatch({ type: 'RESOLVE_SCENARIO_CASE', id: item.id })
            if (patientIdForJourneyCase(item.id)) {
              window.scrollTo({ top: 0, behavior: 'smooth' })
            }
          }}
        >
          {done ? item.resultLabel : item.actionLabel}
        </button>
      </div>
    </article>
  )
}

interface PatientActionItem {
  item: ScenarioCase
  scenario: WorkflowScenario
}

interface PatientActionGroup {
  patientName: string
  items: PatientActionItem[]
  primary: PatientActionItem
}

const ACTION_PRIORITY: Record<ScenarioBucket, number> = {
  blocked: 0,
  approval: 1,
  attention: 2,
  ready: 3,
}

function groupPatientActions(
  scenarios: WorkflowScenario[],
  focusCaseId: string | null,
): PatientActionGroup[] {
  const grouped = new Map<string, PatientActionItem[]>()

  for (const scenario of scenarios) {
    for (const item of scenario.cases) {
      const existing = grouped.get(item.patientName) ?? []
      existing.push({ item, scenario })
      grouped.set(item.patientName, existing)
    }
  }

  return Array.from(grouped.entries())
    .map(([patientName, items]) => {
      const sorted = [...items].sort((a, b) => {
        if (a.item.id === focusCaseId) return -1
        if (b.item.id === focusCaseId) return 1
        return ACTION_PRIORITY[a.scenario.bucket] - ACTION_PRIORITY[b.scenario.bucket]
      })
      return { patientName, items: sorted, primary: sorted[0] }
    })
    .sort((a, b) => {
      if (a.primary.item.id === focusCaseId) return -1
      if (b.primary.item.id === focusCaseId) return 1
      const priority =
        ACTION_PRIORITY[a.primary.scenario.bucket] - ACTION_PRIORITY[b.primary.scenario.bucket]
      return priority || a.patientName.localeCompare(b.patientName)
    })
}

function PatientActionCard({
  group,
  highlighted,
  tab,
}: {
  group: PatientActionGroup
  highlighted: boolean
  tab: FlowOpsPageId
}) {
  const { state, dispatch } = useDemo()
  const { item, scenario } = group.primary
  const referral =
    tab === 'intake'
      ? state.referrals.find((candidate) => candidate.patientName === group.patientName) ?? null
      : null

  return (
    <article className={`action-patient-card ${highlighted ? 'is-journey-focus' : ''}`}>
      <div className="action-patient-card__top">
        <div>
          <div className="action-patient-card__labels">
            {highlighted ? <span className="chip action-patient-card__journey">Current walkthrough</span> : null}
            <span className={`caption ${bucketClass(scenario.bucket)}`}>{scenario.branchLabel}</span>
            {group.items.length > 1 ? (
              <span className="caption">{group.items.length} open items</span>
            ) : null}
          </div>
          <h3>{group.patientName}</h3>
        </div>
        <StatusPill status={item.status} />
      </div>

      <div className="action-patient-card__body">
        <strong>{item.summary}</strong>
        <p className="muted">{item.detail}</p>
      </div>

      <div className="action-patient-card__meta">
        <span>{item.owner}</span>
        <span>{item.facilityOrContext}</span>
        {item.deadlineLabel ? <span>{item.deadlineLabel}</span> : null}
      </div>

      <div className="action-patient-card__footer">
        <span className="caption">{item.minutesReturned} min returned</span>
        <div className="action-patient-card__buttons">
          {referral ? (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => dispatch({ type: 'SELECT_REFERRAL', id: referral.id })}
            >
              <FileText size={14} aria-hidden="true" />
              Review referral
            </button>
          ) : null}
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              dispatch({ type: 'RESOLVE_SCENARIO_CASE', id: item.id })
              if (patientIdForJourneyCase(item.id)) {
                window.scrollTo({ top: 0, behavior: 'smooth' })
              }
            }}
          >
            {item.actionLabel}
          </button>
        </div>
      </div>
    </article>
  )
}

function ScenarioSection({
  scenario,
  focusCaseId,
  actionOnly,
}: {
  scenario: WorkflowScenario
  focusCaseId: string | null
  actionOnly?: boolean
}) {
  const cases = actionOnly
    ? scenario.cases.filter((item) => scenarioCaseIsOpen(item.status))
    : scenario.cases
  if (actionOnly && cases.length === 0) return null

  return (
    <section className="scenario-section panel" aria-labelledby={`scenario-${scenario.id}`}>
      <div className="scenario-section__header">
        <div>
          <p className={`caption ${bucketClass(scenario.bucket)}`}>{scenario.branchLabel}</p>
          <h3 id={`scenario-${scenario.id}`}>{scenario.title}</h3>
          <p className="muted">{scenario.description}</p>
        </div>
        <span className="chip">{cases.length} {actionOnly ? 'open' : 'cases'}</span>
      </div>
      {!actionOnly ? (
        <div className="scenario-section__rules">
          <p>
            <strong>Rule:</strong> {scenario.rule}
          </p>
          <p className="caption">
            <strong>Human control:</strong> {scenario.humanControlNote}
          </p>
        </div>
      ) : null}
      <ul className="scenario-section__cases">
        {cases.map((item) => (
          <li key={item.id}>
            <ScenarioCaseCard item={item} highlighted={focusCaseId === item.id} />
          </li>
        ))}
      </ul>
    </section>
  )
}

export function ScenarioBoard({
  tab,
  actionOnly = false,
}: {
  tab: FlowOpsPageId
  actionOnly?: boolean
}) {
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
  const filteredBase =
    activeFilter === 'all'
      ? allForTab
      : allForTab.filter((item) => item.bucket === activeFilter)
  const filtered = actionOnly
    ? filteredBase
        .map((scenario) => ({
          ...scenario,
          cases: scenario.cases.filter((item) => scenarioCaseIsOpen(item.status)),
        }))
        .filter((scenario) => scenario.cases.length > 0)
    : filteredBase
  const counts = countScenarioBuckets(allForTab)
  const typicalMinutes = WORKFLOW_TAB_MINUTES[tab] ?? 10
  const tabMinutesCaptured = allForTab
    .flatMap((item) => item.cases)
    .filter((item) => item.status === 'completed' || item.status === 'escalated')
    .reduce((sum, item) => sum + item.minutesReturned, 0)
  const [activeQueueId, setActiveQueueId] = useState(filtered[0]?.id ?? '')
  const focusCaseId = state.journeyFocusCaseId
  const focusedScenario = focusCaseId
    ? scenarioContainingCase(state.workflowScenarios, focusCaseId)
    : null
  const focusOnThisTab = focusedScenario?.tab === tab

  useEffect(() => {
    if (activeFilter !== state.scenarioFilter) {
      dispatch({ type: 'SET_SCENARIO_FILTER', filter: 'all' })
    }
  }, [activeFilter, state.scenarioFilter, dispatch, tab])

  useEffect(() => {
    if (!focusOnThisTab || !focusedScenario) return
    if (filtered.some((item) => item.id === focusedScenario.id)) {
      setActiveQueueId(focusedScenario.id)
    }
  }, [focusOnThisTab, focusedScenario, filtered, tab, focusCaseId])

  useEffect(() => {
    const stillVisible = filtered.some((item) => item.id === activeQueueId)
    if (!stillVisible) {
      setActiveQueueId(filtered[0]?.id ?? '')
    }
  }, [tab, activeFilter, filtered, activeQueueId])

  const activeQueue = filtered.find((item) => item.id === activeQueueId) ?? null
  const patientActions = actionOnly ? groupPatientActions(filtered, focusCaseId) : []

  if (actionOnly) {
    return (
      <section className="action-worklist" aria-label="Patients requiring action">
        <header className="action-worklist__header panel">
          <div>
            <p className="caption">Action queue</p>
            <h2>Patients requiring action</h2>
            <p className="muted">
              One card per patient. The most urgent open item is shown first.
            </p>
          </div>
          <div className="action-worklist__filters" role="toolbar" aria-label="Action filters">
            {availableFilters.map((filter) => (
              <button
                key={filter.id}
                type="button"
                className={`action-worklist__filter ${activeFilter === filter.id ? 'is-active' : ''}`}
                aria-pressed={activeFilter === filter.id}
                onClick={() => dispatch({ type: 'SET_SCENARIO_FILTER', filter: filter.id })}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </header>

        {patientActions.length > 0 ? (
          <div className="action-worklist__grid">
            {patientActions.map((group) => (
              <PatientActionCard
                key={group.patientName}
                group={group}
                highlighted={group.items.some(({ item }) => item.id === focusCaseId)}
                tab={tab}
              />
            ))}
          </div>
        ) : (
          <div className="action-worklist__empty panel">
            <CheckCircle2 size={20} aria-hidden="true" />
            <div>
              <strong>No open actions</strong>
              <p className="muted">This stage is clear for the selected filter.</p>
            </div>
          </div>
        )}
      </section>
    )
  }

  return (
    <section
      className="scenario-board"
      aria-label={actionOnly ? 'Patients requiring action' : 'Live work queue'}
    >
      <div className="scenario-board__summary panel">
        <div className="section-heading">
          <div>
            <h2>
              <Sparkles size={18} aria-hidden="true" />{' '}
              {actionOnly ? 'Patients requiring action' : 'Live work queue'}
            </h2>
            <p className="muted">
              {actionOnly
                ? 'Open cases on this stage — confirm, escalate, or clear work.'
                : 'Live cases on this stage — open a queue to confirm, escalate, or clear work.'}
            </p>
          </div>
          {!actionOnly ? (
            <div className="scenario-board__chips">
              <span className="chip">{typicalMinutes} min / typical case</span>
              {tabMinutesCaptured > 0 ? (
                <span className="chip">{tabMinutesCaptured} captured on this stage</span>
              ) : null}
            </div>
          ) : (
            <div className="scenario-board__chips">
              <span className="chip">{counts.openCases} open actions</span>
            </div>
          )}
        </div>
        {!actionOnly ? (
          <>
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
          </>
        ) : (
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
        )}
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
              <span className="caption">{item.cases.length} open</span>
            </button>
          ))}
        </div>
      ) : null}

      <div className="scenario-board__list">
        {activeQueue ? (
          <ScenarioSection
            scenario={activeQueue}
            focusCaseId={focusOnThisTab ? focusCaseId : null}
            actionOnly={actionOnly}
          />
        ) : null}
        {filtered.length === 0 ? (
          <p className="caption panel" style={{ padding: '1rem' }}>
            {actionOnly
              ? 'No open actions on this stage.'
              : 'No queues match this filter on this stage.'}
          </p>
        ) : null}
      </div>

      {!actionOnly ? <StageExceptions scenarios={allForTab} /> : null}
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
  const { state, dispatch } = useDemo()
  const openWork = state.workflowScenarios
    .map((item) => ({
      ...item,
      cases: item.cases.filter((caseItem) => scenarioCaseIsOpen(caseItem.status)),
    }))
    .filter((item) => item.cases.length > 0)
  const patientWork = groupPatientActions(openWork, null)
  const readyCount = patientWork.filter(({ primary }) => primary.scenario.bucket === 'ready').length
  const followUpCount = patientWork.filter(
    ({ primary }) => primary.scenario.bucket === 'attention',
  ).length
  const escalationCount = patientWork.filter(
    ({ primary }) =>
      primary.scenario.bucket === 'blocked' || primary.scenario.bucket === 'approval',
  ).length
  const stageWork = JOURNEY_STAGE_ORDER.map((stage) => ({
    stage,
    label: FLOW_OPS[stage].title.replace(/^\d+\.\s*/, ''),
    count: patientWork.filter(({ primary }) => primary.scenario.tab === stage).length,
  }))
  const busiestStage = Math.max(1, ...stageWork.map((item) => item.count))

  return (
    <section className="overview-scenarios panel" aria-labelledby="overview-scenarios-heading">
      <div className="overview-scenarios__header">
        <div>
          <p className="caption">Live workload</p>
          <h2 id="overview-scenarios-heading">Patients requiring attention</h2>
          <p className="muted">
            Each patient is counted once under their highest-priority open action.
          </p>
        </div>
        <span className="overview-scenarios__live">
          <span aria-hidden="true" />
          Updated now
        </span>
      </div>

      <div className="overview-scenarios__summary">
        <article className="overview-scenarios__total">
          <strong>{patientWork.length}</strong>
          <span>patients need action</span>
          <small>A patient may have additional work later in the path.</small>
        </article>
        <div className="overview-scenarios__breakdown" aria-label="Patient action priority">
          <article>
            <span className="overview-scenarios__marker is-ready" aria-hidden="true" />
            <div>
              <strong>{readyCount}</strong>
              <span>Ready to process</span>
            </div>
          </article>
          <article>
            <span className="overview-scenarios__marker is-follow-up" aria-hidden="true" />
            <div>
              <strong>{followUpCount}</strong>
              <span>Needs follow-up</span>
            </div>
          </article>
          <article>
            <span className="overview-scenarios__marker is-escalation" aria-hidden="true" />
            <div>
              <strong>{escalationCount}</strong>
              <span>Blocked or awaiting approval</span>
            </div>
          </article>
        </div>
      </div>

      <div className="overview-scenarios__stages">
        <div className="overview-scenarios__stages-heading">
          <h3>Where the work is now</h3>
          <span>Primary action by stage</span>
        </div>
        <ol>
          {stageWork.map((item) => (
            <li key={item.stage}>
              <button
                type="button"
                onClick={() => {
                  dispatch({ type: 'SET_ACTIVE_PAGE', page: item.stage })
                  window.scrollTo({ top: 0, behavior: 'smooth' })
                }}
                title={`Open ${item.label} actions`}
                aria-label={`Open ${item.label} actions, ${item.count} patients`}
              >
                <div>
                  <span>{item.label}</span>
                  <strong>{item.count}</strong>
                </div>
                <span className="overview-scenarios__bar" aria-hidden="true">
                  <span style={{ width: `${(item.count / busiestStage) * 100}%` }} />
                </span>
              </button>
            </li>
          ))}
        </ol>
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
        .filter((item) => scenarioCaseIsOpen(item.status))
        .map((item) => ({ ...item, scenarioTitle: scenario.title })),
    )
}
