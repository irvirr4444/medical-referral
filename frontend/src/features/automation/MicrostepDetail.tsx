import { Clock3, Database } from 'lucide-react'
import { ArtifactSections } from './ArtifactSections'
import type {
  AutomationMicrostep,
  AutomationRunFixture,
  MicrostepExample,
} from './types'
import './Microstep.css'
import './ArtifactSections.css'

function ValueList({
  title,
  values,
}: {
  title: string
  values: MicrostepExample['inputs']
}) {
  return (
    <section className="microstep-values">
      <h4>{title}</h4>
      <dl>
        {values.map((item) => (
          <div key={`${item.label}-${item.value}`}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

export function MicrostepDetail({
  step,
  run,
  example,
}: {
  step: AutomationMicrostep
  run: AutomationRunFixture
  example: MicrostepExample
}) {
  const hasPatientWalkthrough = Boolean(
    example.patientName && example.artifactSections?.length,
  )

  return (
    <article
      className="microstep-detail"
      aria-labelledby={`microstep-${step.id}`}
    >
      <header className="microstep-detail__header">
        <div>
          <h2 id={`microstep-${step.id}`}>{step.name}</h2>
          <p>{step.description}</p>
        </div>
      </header>

      <div
        className="microstep-detail__receipt"
        aria-label="Microstep execution receipt"
      >
        <span>
          <Clock3 size={17} aria-hidden="true" />
          <strong>{example.duration}</strong>
          Processing time
        </span>
        <span>
          <Database size={17} aria-hidden="true" />
          <strong>{run.label}</strong>
          Workflow run
        </span>
      </div>

      {hasPatientWalkthrough ? (
        <>
          <div className="microstep-detail__patient">
            <p className="caption">Patient in this step</p>
            <strong>{example.patientName}</strong>
            <span className="muted">
              {example.referralId} · {example.executedAt}
            </span>
          </div>

          {example.knownAtThisPoint?.length ? (
            <section className="microstep-detail__known" aria-label="Known at this point">
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

          <section className="microstep-detail__artifact" aria-label="Produced output">
            <h3>Output produced in this step</h3>
            <dl className="microstep-detail__artifact-meta">
              <div>
                <dt>Artifact</dt>
                <dd>{example.artifactTitle}</dd>
              </div>
              <div>
                <dt>Execution</dt>
                <dd>{example.executionId}</dd>
              </div>
            </dl>
            <ArtifactSections
              sections={example.artifactSections ?? []}
              artifactId={example.artifactId ?? step.id}
            />
          </section>
        </>
      ) : (
        <div className="microstep-detail__io">
          <ValueList title="Input" values={example.inputs} />
          <ValueList title="Output" values={example.outputs} />
        </div>
      )}

    </article>
  )
}
