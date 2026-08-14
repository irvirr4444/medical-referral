import { ArtifactSections } from './ArtifactSections'
import { IntakePdfPreview } from './IntakePdfPreview'
import { detailForPatientStep, parseOpsDate } from './ops'
import type { PatientStepStatus } from './ops/types'
import './ArtifactSections.css'
import './StageOps.css'

type PatientStepDetail = ReturnType<typeof detailForPatientStep>

const STATUS_MEANINGS: Array<{ id: PatientStepStatus; meaning: string }> = [
  { id: 'waiting', meaning: 'Needs confirmation' },
  { id: 'blocked', meaning: 'Needs confirmation' },
  { id: 'current', meaning: 'In progress' },
  { id: 'done', meaning: 'Finished' },
]

export function statusMeaning(status: PatientStepStatus | string) {
  return (
    STATUS_MEANINGS.find((item) => item.id === status)?.meaning ?? 'Next'
  )
}

export function StagePatientStepDetail({
  detail,
  canConfirm = false,
  isConfirmed = false,
  onConfirm,
  variant = 'page',
}: {
  detail: PatientStepDetail
  canConfirm?: boolean
  isConfirmed?: boolean
  onConfirm?: () => void
  variant?: 'page' | 'embedded'
}) {
  const { microstep, progress, example } = detail
  if (!microstep || !progress) {
    return <p className="muted">No detail for this patient step.</p>
  }

  const when = progress.occurredAt ? parseOpsDate(progress.occurredAt) : null
  const rich = Boolean(example?.artifactSections?.length)
  const patientName = example?.patientName ?? 'Patient'
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
  const embedded = variant === 'embedded'

  return (
    <article
      className={`stage-ops-step-detail is-${progress.status}${embedded ? ' is-embedded' : ''}`}
      aria-label={`${microstep.name} for this patient`}
    >
      {embedded ? null : (
        <header className="stage-ops-step-detail__header">
          <div className="stage-ops-step-detail__meta">
            {when ? (
              <time dateTime={progress.occurredAt}>
                {when.time} · {shortDate(when)}
              </time>
            ) : (
              <span className="stage-ops-step-detail__time-fallback">—</span>
            )}
            <span
              className={`stage-ops-step-detail__status is-${progress.status}`}
            >
              {statusMeaning(progress.status)}
            </span>
          </div>
          <p className="stage-ops-step-detail__patient">{patientName}</p>
          <p className="stage-ops-step-detail__step">{microstep.name}</p>
          <h2 className="stage-ops-step-detail__message">{progress.summary}</h2>
        </header>
      )}

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

      {example?.samplePdf ? (
        <IntakePdfPreview samplePdf={example.samplePdf} />
      ) : null}

      {rich && example ? (
        <section
          className="stage-ops-step-detail__evidence"
          aria-label="Produced output"
        >
          <ArtifactSections
            sections={example.artifactSections ?? []}
            artifactId={example.artifactId ?? microstep.id}
          />
        </section>
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

function shortDate(when: ReturnType<typeof parseOpsDate>) {
  const month =
    when.month.charAt(0) + when.month.slice(1).toLowerCase()
  return `${month} ${Number(when.day)}`
}
