import { ChevronRight } from 'lucide-react'
import type { AutomationMicrostep } from './types'
import './Microstep.css'

export function MicrostepList({
  steps,
  selectedStepId,
  onSelect,
  attentionStepIds = [],
  stepStatuses,
}: {
  steps: AutomationMicrostep[]
  selectedStepId: string
  onSelect: (stepId: string) => void
  attentionStepIds?: string[]
  stepStatuses?: Record<string, string>
}) {
  return (
    <nav className="microstep-list" aria-label="Automation steps">
      <ol>
        {steps.map((step, index) => {
          const selected = step.id === selectedStepId
          const needsAttention = attentionStepIds.includes(step.id)
          const stepStatus = stepStatuses?.[step.id]
          return (
            <li key={step.id}>
              <button
                type="button"
                className={`microstep-list__button${selected ? ' is-selected' : ''}${
                  stepStatus ? ` is-${stepStatus}` : ''
                }`}
                aria-current={selected ? 'step' : undefined}
                aria-label={
                  needsAttention
                    ? `${step.name}, new update`
                    : stepStatus === 'waiting' || stepStatus === 'blocked'
                      ? `${step.name}, ${stepStatus}`
                      : undefined
                }
                onClick={() => onSelect(step.id)}
              >
                <span className="microstep-list__number" aria-hidden="true">
                  {index + 1}
                </span>
                <span className="microstep-list__copy">
                  <span className="microstep-list__title-row">
                    <strong>{step.name}</strong>
                    {needsAttention ? (
                      <span
                        className="microstep-list__attention-dot"
                        aria-hidden="true"
                      />
                    ) : null}
                  </span>
                </span>
                <ChevronRight size={18} aria-hidden="true" />
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
