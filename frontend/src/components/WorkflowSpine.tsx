import { AnimatePresence, motion } from 'framer-motion'
import { AUTOMATION_STEPS, WORKFLOW_STAGES, stageCounts } from '../data/constants'
import { getAutomationStepIndex } from '../state/demoReducer'
import { useDemo } from '../state/useDemo'
import type { WorkflowStage } from '../types'
import './WorkflowSpine.css'

export function WorkflowSpine() {
  const { state, dispatch, prefersReducedMotion } = useDemo()
  const counts = stageCounts(state.referrals)
  const stepIndex = getAutomationStepIndex(state.automationStep)
  const currentLabel =
    AUTOMATION_STEPS.find((step) => step.id === state.automationStep)?.label ??
    (state.automationComplete ? 'Inbox batch complete' : 'Waiting for next inbox run')

  return (
    <section className="workflow-spine panel" aria-labelledby="spine-heading">
      <div className="section-heading">
        <div>
          <h2 id="spine-heading">Workflow spine</h2>
          <p className="muted" aria-live="polite">
            {state.automationRunning ? currentLabel : state.completionMessage ?? currentLabel}
          </p>
        </div>
      </div>

      <ol className="workflow-spine__track" aria-label="Referral workflow stages">
        {WORKFLOW_STAGES.map((stage, index) => {
          const active = state.spineFilter === stage.id
          const reached =
            state.automationComplete ||
            (state.automationRunning && stepIndex >= Math.min(index + 2, 11))
          return (
            <li key={stage.id}>
              <button
                type="button"
                className={`workflow-spine__stage ${active ? 'is-active' : ''} ${
                  reached ? 'is-reached' : ''
                }`}
                onClick={() =>
                  dispatch({
                    type: 'SET_SPINE_FILTER',
                    stage: active ? 'all' : (stage.id as WorkflowStage),
                  })
                }
                aria-pressed={active}
              >
                <span className="workflow-spine__dot" aria-hidden="true" />
                <span className="workflow-spine__label">{stage.label}</span>
                <span className="workflow-spine__count" aria-label={`${counts[stage.id]} referrals`}>
                  {counts[stage.id]}
                </span>
              </button>
              {index < WORKFLOW_STAGES.length - 1 ? (
                <span className="workflow-spine__connector" aria-hidden="true" />
              ) : null}
            </li>
          )
        })}
      </ol>

      <div className="workflow-spine__tokens" aria-hidden={!state.automationRunning}>
        <AnimatePresence>
          {state.automationRunning
            ? state.referrals
                .filter((referral) => referral.inboxBatch)
                .map((referral, index) => (
                <motion.span
                  key={referral.id}
                  className="workflow-spine__token"
                  initial={prefersReducedMotion ? false : { x: 0, opacity: 0.4 }}
                  animate={
                    prefersReducedMotion
                      ? { opacity: 1 }
                      : {
                          x: `${Math.min(stepIndex, 11) * 8}%`,
                          opacity: 1,
                        }
                  }
                  transition={{ duration: 0.45, delay: index * 0.03 }}
                  title={referral.patientName}
                />
              ))
            : null}
        </AnimatePresence>
      </div>

      {state.automationRunning ? (
        <ol className="workflow-spine__steps" aria-label="Automation progress">
          {AUTOMATION_STEPS.map((step, index) => (
            <li
              key={step.id}
              className={index <= stepIndex ? 'is-done' : ''}
            >
              <span aria-hidden="true">{index <= stepIndex ? '✓' : '•'}</span>
              {step.label}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  )
}
