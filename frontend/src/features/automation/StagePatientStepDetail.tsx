import { Clock3 } from 'lucide-react'
import { parseOpsDate, detailForPatientStep } from './ops'
import type { HumanDecisionRecord } from './ops/types'
import './StageOps.css'

type PatientStepDetail = ReturnType<typeof detailForPatientStep>

export function StagePatientStepDetail({
  detail,
  canConfirm = false,
  isConfirmed = false,
  onConfirm,
  actionLabel,
  confirmedLabel,
  options = [],
  decision,
}: {
  detail: PatientStepDetail
  canConfirm?: boolean
  isConfirmed?: boolean
  onConfirm?: (selectedOption?: string) => void
  actionLabel?: string
  confirmedLabel?: string
  options?: Array<{
    value: string
    label: string
    detail?: string
    recommended?: boolean
  }>
  decision?: HumanDecisionRecord
}) {
  const { microstep, progress, example } = detail
  if (!microstep || !progress) {
    return <p className="muted">No detail for this patient step.</p>
  }

  const when = progress.occurredAt ? parseOpsDate(progress.occurredAt) : null
  const actionFields = (example?.actionFields ?? []).map((field) =>
    decision?.selectedOption ? { ...field, value: decision.selectedOption } : field,
  )
  const showConfirmationPanel = canConfirm || isConfirmed
  const fieldSectionTitle =
    showConfirmationPanel && !isConfirmed
      ? 'Proposed updates'
      : actionFieldSectionTitle(microstep.id)
  const confirmationCopy = isConfirmed
    ? `${confirmedLabel ?? 'Confirmed'} and recorded in this patient trail.`
    : progress.status === 'blocked'
      ? 'Blocked pending confirmation before this stage can proceed.'
      : progress.status === 'current'
        ? 'Ready for confirmation now.'
        : 'Awaiting confirmation.'
  const confirmationCta = actionLabel ?? 'Confirm step'
  return (
    <article
      className={`stage-ops-step-detail is-${progress.status}`}
      aria-label={`${microstep.name} for this patient`}
    >
      <header className="stage-ops-step-detail__header">
        <div>
          <div className="stage-ops-step-detail__title">
            <h2>{microstep.name}</h2>
            <span className="stage-ops-steps__badge">
              {statusLabel(progress.status, showConfirmationPanel)}
            </span>
          </div>
          <p>{microstep.description}</p>
        </div>
        {when ? (
          <time dateTime={progress.occurredAt}>
            <Clock3 size={16} aria-hidden="true" />
            {when.label} · {when.time}
          </time>
        ) : null}
      </header>

      <section className="stage-ops-step-detail__outcome" aria-label="Result">
        <p className="caption">Result</p>
        <strong>{progress.summary}</strong>
      </section>

      {actionFields.length > 0 && progress.status !== 'upcoming' ? (
        <section
          className="stage-ops-step-detail__changes"
          aria-label={fieldSectionTitle}
        >
          <h3>{fieldSectionTitle}</h3>
          <div className="stage-ops-step-detail__change-table" role="table">
            <div className="stage-ops-step-detail__change-head" role="row">
              <span role="columnheader">Field</span>
              <span role="columnheader">Value</span>
              <span role="columnheader">System field</span>
            </div>
            {actionFields.map((field) => (
              <div
                key={`${field.label}-${field.meta ?? field.fieldPath ?? ''}`}
                className="stage-ops-step-detail__change-row"
                role="row"
              >
                <strong role="cell">{field.label}</strong>
                <span role="cell">{field.value}</span>
                <small role="cell">{field.meta ?? field.fieldPath ?? 'Workflow'}</small>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {showConfirmationPanel ? (
        <section
          className="stage-ops-step-detail__confirmation"
          aria-label="Confirmation"
        >
          <div className="stage-ops-step-detail__confirmation-copy">
            <p className="caption">Confirmation</p>
            <strong>{confirmationCopy}</strong>
          </div>
          {options.length > 0 && !isConfirmed ? (
            <div className="stage-ops-step-detail__choices" aria-label="Available choices">
              {options.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={`stage-ops-step-detail__choice${option.recommended ? ' is-recommended' : ''}`}
                  onClick={() => onConfirm?.(option.value)}
                  disabled={!canConfirm}
                >
                  <span>
                    <strong>{option.label}</strong>
                    {option.recommended ? <em>Recommended</em> : null}
                  </span>
                  {option.detail ? <small>{option.detail}</small> : null}
                </button>
              ))}
            </div>
          ) : (
            <button
              type="button"
              className={`stage-ops-step-detail__confirm${isConfirmed ? ' is-confirmed' : ''}${canConfirm && !isConfirmed ? ' is-actionable' : ''}`}
              onClick={() => onConfirm?.()}
              disabled={isConfirmed || !canConfirm}
            >
              {isConfirmed
                ? decision?.selectedOption ?? 'Confirmed'
                : confirmationCta}
            </button>
          )}
        </section>
      ) : null}

      {progress.status === 'upcoming' ? (
        <p className="muted stage-ops-step-detail__pending">
          This step has not run for this patient yet.
          {microstep.next ? ` Next after this: ${microstep.next}.` : ''}
        </p>
      ) : null}

    </article>
  )
}

function statusLabel(status: string, isHumanGate: boolean) {
  switch (status) {
    case 'done':
      return 'Done'
    case 'current':
      return 'In progress'
    case 'waiting':
      return isHumanGate ? 'Awaiting confirmation' : 'Waiting'
    case 'blocked':
      return isHumanGate ? 'Blocked pending confirmation' : 'Blocked'
    default:
      return 'Next'
  }
}

const WRITE_ACTIONS = new Set([
  'create-monday-record',
  'create-update-drk',
  'assign-owner',
  'record-provider',
  'confirm-record-appointment',
  'record-visit-outcome',
  'apply-weekly-rules',
])

function actionFieldSectionTitle(stepId: string) {
  return WRITE_ACTIONS.has(stepId) ? 'Field updates' : 'Action data'
}
