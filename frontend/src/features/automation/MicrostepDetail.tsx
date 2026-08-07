import { ArrowRight, Clock3, Database, ShieldCheck } from 'lucide-react'
import { FeedbackPanel } from './FeedbackPanel'
import { ImplementationBadge, RunStatusBadge } from './StatusBadge'
import type {
  AutomationMicrostep,
  AutomationRunFixture,
  MicrostepExample,
  MicrostepFeedback,
} from './types'
import './Microstep.css'

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
  feedback,
  onAddFeedback,
}: {
  step: AutomationMicrostep
  run: AutomationRunFixture
  example: MicrostepExample
  feedback: MicrostepFeedback[]
  onAddFeedback: (
    category: MicrostepFeedback['category'],
    comment: string,
  ) => void
}) {
  return (
    <article
      className="microstep-detail"
      aria-labelledby={`microstep-${step.id}`}
    >
      <header className="microstep-detail__header">
        <div>
          <p className="caption">{step.system}</p>
          <h2 id={`microstep-${step.id}`}>{step.name}</h2>
          <p>{step.description}</p>
        </div>
        <div className="microstep-detail__badges">
          <ImplementationBadge status={step.implementationStatus} />
          <RunStatusBadge status={example.status} />
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

      <div className="microstep-detail__io">
        <ValueList title="Input" values={example.inputs} />
        <ArrowRight className="microstep-detail__arrow" aria-hidden="true" />
        <ValueList title="Output" values={example.outputs} />
      </div>

      <section className="microstep-validation">
        <ShieldCheck size={22} aria-hidden="true" />
        <div>
          <h3>Validation and handoff</h3>
          <p>{example.validation}</p>
          <p>
            <strong>Next:</strong> {step.next}
          </p>
        </div>
      </section>

      <FeedbackPanel feedback={feedback} onAdd={onAddFeedback} />
    </article>
  )
}
