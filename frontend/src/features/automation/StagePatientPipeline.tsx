import { parseOpsDate } from './ops'
import { statusMeaning } from './StagePatientStepDetail'
import './StageOps.css'

export function StagePatientPipeline({
  patientName,
  steps,
  selectedStepId,
  onSelectStep,
}: {
  patientName: string
  steps: Array<{
    stepId: string
    stepName: string
    summary: string
    status: string
    occurredAt?: string
  }>
  selectedStepId: string
  onSelectStep: (stepId: string) => void
}) {
  return (
    <div className="stage-ops-pipeline" aria-label="Patient pipeline">
      <header className="stage-ops-pipeline__header">
        <p className="stage-ops-pipeline__eyebrow">Full pipeline</p>
        <h3>{patientName}</h3>
        <p className="muted">Every step in this stage for the demo patient.</p>
      </header>

      <ol className="stage-ops-pipeline__list">
        {steps.map((step, index) => {
          const when = step.occurredAt ? parseOpsDate(step.occurredAt) : null
          const selected = step.stepId === selectedStepId
          return (
            <li key={step.stepId}>
              <button
                type="button"
                className={`stage-ops-pipeline__row is-${step.status}${selected ? ' is-selected' : ''}`}
                aria-current={selected ? 'step' : undefined}
                onClick={() => onSelectStep(step.stepId)}
              >
                <span className="stage-ops-pipeline__index" aria-hidden="true">
                  {index + 1}
                </span>
                <span className="stage-ops-pipeline__copy">
                  <strong>{step.stepName}</strong>
                  <span className="stage-ops-pipeline__summary">
                    {step.summary}
                  </span>
                </span>
                <span className="stage-ops-pipeline__meta">
                  <time dateTime={step.occurredAt}>
                    {when ? when.time : '—'}
                  </time>
                  <span
                    className={`stage-ops-pipeline__status is-${step.status}`}
                  >
                    {statusMeaning(step.status)}
                  </span>
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
