import { Clock3 } from 'lucide-react'
import { ArtifactSections } from './ArtifactSections'
import { parseOpsDate, detailForPatientStep } from './ops'
import './ArtifactSections.css'
import './StageOps.css'

type PatientStepDetail = ReturnType<typeof detailForPatientStep>

export function StagePatientStepDetail({
  detail,
}: {
  detail: PatientStepDetail
}) {
  const { microstep, progress, example } = detail
  if (!microstep || !progress) {
    return <p className="muted">No detail for this patient step.</p>
  }

  const when = progress.occurredAt ? parseOpsDate(progress.occurredAt) : null
  const rich = Boolean(example?.artifactSections?.length)

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
        <p className="caption">For this patient</p>
        <strong>{progress.summary}</strong>
      </section>

      {progress.status === 'upcoming' ? (
        <p className="muted stage-ops-step-detail__pending">
          This step has not run for this patient yet.
          {microstep.next ? ` Next after this: ${microstep.next}.` : ''}
        </p>
      ) : null}

      {rich && example ? (
        <>
          {example.knownAtThisPoint?.length ? (
            <section
              className="microstep-detail__known"
              aria-label="Known at this point"
            >
              <h3>Known at this point</h3>
              <dl>
                {example.knownAtThisPoint.map((item) => (
                  <div key={`${item.label}-${item.value}`}>
                    <dt>{item.label}</dt>
                    <dd>{item.value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ) : null}

          <section
            className="microstep-detail__artifact"
            aria-label="Produced output"
          >
            <h3>Output produced in this step</h3>
            <dl className="microstep-detail__artifact-meta">
              {example.artifactTitle ? (
                <div>
                  <dt>Artifact</dt>
                  <dd>{example.artifactTitle}</dd>
                </div>
              ) : null}
              {example.duration ? (
                <div>
                  <dt>Duration</dt>
                  <dd>{example.duration}</dd>
                </div>
              ) : null}
              {example.validation ? (
                <div>
                  <dt>Validation</dt>
                  <dd>{example.validation}</dd>
                </div>
              ) : null}
            </dl>
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
      return 'Waiting'
    case 'blocked':
      return 'Blocked'
    default:
      return 'Next'
  }
}
