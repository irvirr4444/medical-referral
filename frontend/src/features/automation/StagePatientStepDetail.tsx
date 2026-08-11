import { Clock3 } from 'lucide-react'
import { ArtifactSections } from './ArtifactSections'
import { parseOpsDate, detailForPatientStep } from './ops'
import './ArtifactSections.css'
import './StageOps.css'

type PatientStepDetail = ReturnType<typeof detailForPatientStep>

export function StagePatientStepDetail({
  detail,
  canConfirm = false,
  isConfirmed = false,
  onConfirm,
}: {
  detail: PatientStepDetail
  canConfirm?: boolean
  isConfirmed?: boolean
  onConfirm?: () => void
}) {
  const { microstep, progress, example } = detail
  if (!microstep || !progress) {
    return <p className="muted">No detail for this patient step.</p>
  }

  const when = progress.occurredAt ? parseOpsDate(progress.occurredAt) : null
  const rich = Boolean(example?.artifactSections?.length)
  const showConfirmationPanel = canConfirm || isConfirmed
  const confirmationCopy = isConfirmed
    ? 'Confirmed and recorded in this patient trail.'
    : progress.status === 'blocked'
      ? 'Blocked pending confirmation before this stage can proceed.'
      : progress.status === 'current'
        ? 'Ready for confirmation now.'
        : 'Awaiting confirmation.'
  const confirmationCta =
    progress.status === 'blocked' ? 'Resolve and confirm' : 'Confirm step'

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
              {statusLabel(progress.status)}
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

      <section className="stage-ops-step-detail__outcome" aria-label="Outcome">
        <p className="caption">Outcome summary</p>
        <strong>{progress.summary}</strong>
      </section>

      {showConfirmationPanel ? (
        <section
          className="stage-ops-step-detail__confirmation"
          aria-label="Confirmation"
        >
          <div className="stage-ops-step-detail__confirmation-copy">
            <p className="caption">Confirmation</p>
            <strong>{confirmationCopy}</strong>
          </div>
          <button
            type="button"
            className={`stage-ops-step-detail__confirm${isConfirmed ? ' is-confirmed' : ''}${canConfirm && !isConfirmed ? ' is-actionable' : ''}`}
            onClick={onConfirm}
            disabled={isConfirmed || !canConfirm}
          >
            {isConfirmed ? 'Confirmed' : confirmationCta}
          </button>
        </section>
      ) : null}

      {progress.status === 'upcoming' ? (
        <p className="muted stage-ops-step-detail__pending">
          This step has not run for this patient yet.
          {microstep.next ? ` Next after this: ${microstep.next}.` : ''}
        </p>
      ) : null}

      {rich && example ? (
        <>
          <section
            className="microstep-detail__artifact"
            aria-label="Produced output"
          >
            <ArtifactSections
              sections={example.artifactSections ?? []}
              artifactId={example.artifactId ?? microstep.id}
            />
          </section>
        </>
      ) : progress.status !== 'upcoming' ? (
        <section className="stage-ops-step-detail__facts" aria-label="Step facts">
          <div>
            <p className="caption">System</p>
            <strong>{microstep.system}</strong>
          </div>
          <div>
            <p className="caption">Next</p>
            <strong>{microstep.next}</strong>
          </div>
        </section>
      ) : null}
    </article>
  )
}

function statusLabel(status: string) {
  switch (status) {
    case 'done':
      return 'Done'
    case 'current':
      return 'Here'
    case 'waiting':
      return 'Awaiting confirmation'
    case 'blocked':
      return 'Blocked pending confirmation'
    default:
      return 'Next'
  }
}
