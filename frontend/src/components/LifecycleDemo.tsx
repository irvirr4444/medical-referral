import { useCallback, useEffect, useMemo, useRef } from 'react'
import { CheckCircle2, Play, ShieldAlert } from 'lucide-react'
import { COPY } from '../data/constants'
import { LIFECYCLE_STAGES, lifecycleRunLabel, type LifecycleStageId } from '../data/lifecycle'
import { useDemo } from '../state/useDemo'
import './LifecycleDemo.css'

interface LifecycleDemoProps {
  allowedStages?: LifecycleStageId[]
  title?: string
  description?: string
  showExceptionBoard?: boolean
}

export function LifecycleDemo({
  allowedStages,
  title = 'Referral lifecycle operations',
  description = 'Assignment, provider selection, scheduling, weekly monitoring, holds, and discharge review — with WCW case managers and providers on the board.',
  showExceptionBoard = true,
}: LifecycleDemoProps) {
  const { state, dispatch, prefersReducedMotion } = useDemo()
  const timer = useRef<number | null>(null)

  const visibleStages = useMemo(
    () =>
      allowedStages?.length
        ? LIFECYCLE_STAGES.filter((stage) => allowedStages.includes(stage.id))
        : LIFECYCLE_STAGES,
    [allowedStages],
  )

  useEffect(() => {
    if (!allowedStages?.length) return
    if (!allowedStages.includes(state.lifecycleStageId)) {
      dispatch({ type: 'SET_LIFECYCLE_STAGE', stageId: allowedStages[0] })
    }
  }, [allowedStages, dispatch, state.lifecycleStageId])

  const stage =
    visibleStages.find((item) => item.id === state.lifecycleStageId) ?? visibleStages[0]
  const cases = useMemo(
    () => state.lifecycleCases.filter((item) => item.stageId === stage.id),
    [state.lifecycleCases, stage.id],
  )
  const openCount = cases.filter(
    (item) => item.status !== 'completed' && item.status !== 'escalated',
  ).length
  const doneCount = cases.length - openCount

  const clearTimer = useCallback(() => {
    if (timer.current != null) {
      window.clearTimeout(timer.current)
      timer.current = null
    }
  }, [])

  useEffect(() => () => clearTimer(), [clearTimer])

  const runStage = () => {
    if (state.lifecycleRunning || openCount === 0) return
    clearTimer()
    dispatch({ type: 'START_LIFECYCLE_STAGE' })
    const delay = prefersReducedMotion ? 200 : 1600
    timer.current = window.setTimeout(() => {
      dispatch({ type: 'COMPLETE_LIFECYCLE_STAGE' })
    }, delay)
  }

  const exceptionSummary = [
    {
      label: 'Awaiting provider confirmation',
      count: state.lifecycleCases.filter(
        (item) => item.stageId === 'provider_response' && item.status !== 'completed',
      ).length,
    },
    {
      label: 'Unscheduled at end-of-day checkpoint',
      count: state.lifecycleCases.filter(
        (item) => item.stageId === 'end_of_day' && item.status !== 'escalated',
      ).length,
    },
    {
      label: 'Approaching / at three consecutive not-seen',
      count: state.lifecycleCases.filter((item) => item.stageId === 'not_seen').length,
    },
    {
      label: 'Currently on hold / return-ready',
      count: state.lifecycleCases.filter((item) => item.stageId === 'holds').length,
    },
    {
      label: 'QA/discharge review awaiting approval',
      count: state.lifecycleCases.filter((item) => item.stageId === 'qa_discharge').length,
    },
  ]

  if (!stage) return null

  return (
    <section className="lifecycle panel" aria-labelledby="lifecycle-heading">
      <div className="section-heading">
        <div>
          <h2 id="lifecycle-heading">{title}</h2>
          <p className="muted">{description}</p>
        </div>
        <span className="badge badge-live">Active cases</span>
      </div>

      <div className="lifecycle__metrics" aria-label="Lifecycle metrics">
        <article>
          <strong>{state.lifecycleMinutesReturned}</strong>
          <span>Lifecycle minutes returned so far</span>
        </article>
        <article>
          <strong>{visibleStages.length}</strong>
          <span>Stages in this page</span>
        </article>
        <article>
          <strong>
            {doneCount}/{cases.length}
          </strong>
          <span>Cases completed in this stage</span>
        </article>
        <article>
          <strong>{openCount}</strong>
          <span>Open actions</span>
        </article>
      </div>

      {visibleStages.length > 1 ? (
        <div className="lifecycle__stages" role="tablist" aria-label="Lifecycle stages">
          {visibleStages.map((item) => {
            const stageCases = state.lifecycleCases.filter((entry) => entry.stageId === item.id)
            const finished = stageCases.every(
              (entry) => entry.status === 'completed' || entry.status === 'escalated',
            )
            return (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={state.lifecycleStageId === item.id}
                className={`lifecycle__stage ${
                  state.lifecycleStageId === item.id ? 'is-active' : ''
                } ${finished ? 'is-done' : ''}`}
                onClick={() =>
                  dispatch({
                    type: 'SET_LIFECYCLE_STAGE',
                    stageId: item.id as LifecycleStageId,
                  })
                }
              >
                <span>{item.label}</span>
                {finished ? <CheckCircle2 size={14} aria-hidden="true" /> : null}
              </button>
            )
          })}
        </div>
      ) : null}

      <div className="lifecycle__stage-panel">
        <div className="lifecycle__stage-copy">
          <h3>{stage.label}</h3>
          <p>{stage.description}</p>
          <p className="caption" aria-live="polite">
            {state.lifecycleMessage ??
              `${openCount} open case${openCount === 1 ? '' : 's'} ready to process.`}
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={runStage}
          disabled={state.lifecycleRunning || openCount === 0}
        >
          <Play size={16} aria-hidden="true" />
          {openCount === 0 ? 'Stage complete' : lifecycleRunLabel(stage.id)}
        </button>
      </div>

      {state.lifecycleRunning ? (
        <ol className="lifecycle__progress" aria-label="Stage progress">
          <li className="is-done">Reading Monday.com / DRK recorded statuses</li>
          <li className="is-done">Applying territory, schedule, and deadline rules</li>
          <li className="is-done">Preparing employee decisions and exception packages</li>
          <li>Recording outcomes without replacing clinical judgment</li>
        </ol>
      ) : null}

      <ul className="lifecycle__cases">
        {cases.map((item) => (
          <li key={item.id}>
            <article className={`lifecycle-card status-${item.status}`}>
              <div className="lifecycle-card__top">
                <div>
                  <h4>{item.patientName}</h4>
                  <p>{item.summary}</p>
                </div>
                <StatusPill status={item.status} />
              </div>
              <p className="muted">{item.detail}</p>
              <p className="caption">Owner: {item.owner}</p>
              <div className="lifecycle-card__footer">
                <span className="chip">{item.minutesReturned} min returned</span>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={
                    state.lifecycleRunning ||
                    item.status === 'completed' ||
                    item.status === 'escalated'
                  }
                  onClick={() => dispatch({ type: 'RESOLVE_LIFECYCLE_CASE', id: item.id })}
                >
                  {item.status === 'completed' || item.status === 'escalated'
                    ? item.resultLabel
                    : item.actionLabel}
                </button>
              </div>
            </article>
          </li>
        ))}
      </ul>

      {showExceptionBoard ? (
        <div className="lifecycle__exceptions">
          <div className="section-heading">
            <div>
              <h3>Management exception board</h3>
              <p className="muted">
                One place for unanswered providers, unscheduled referrals, missed visits, holds,
                and discharge approvals.
              </p>
            </div>
            <span className="badge badge-attention">Needs review</span>
          </div>
          <ul className="lifecycle__exception-grid">
            {exceptionSummary.map((item) => (
              <li key={item.label}>
                <strong>{item.count}</strong>
                <span>{item.label}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="caption" style={{ marginTop: '0.85rem' }}>
        {COPY.humanControl}
      </p>
    </section>
  )
}

function StatusPill({
  status,
}: {
  status: 'pending' | 'suggested' | 'awaiting_human' | 'completed' | 'escalated' | 'monitoring'
}) {
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
    return <span className="badge badge-attention">Monitoring</span>
  }
  if (status === 'awaiting_human') {
    return <span className="badge badge-attention">Human confirmation required</span>
  }
  return <span className="badge badge-neutral">Ready to process</span>
}
