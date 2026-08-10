import { ChevronRight } from 'lucide-react'
import type { AutomationMicrostep } from './types'
import './Microstep.css'

export function MicrostepList({
  steps,
  selectedStepId,
  onSelect,
}: {
  steps: AutomationMicrostep[]
  selectedStepId: string
  onSelect: (stepId: string) => void
}) {
  return (
    <nav className="microstep-list" aria-label="Automation microsteps">
      <ol>
        {steps.map((step, index) => {
          const selected = step.id === selectedStepId
          return (
            <li key={step.id}>
              <button
                type="button"
                className={`microstep-list__button ${selected ? 'is-selected' : ''}`}
                aria-current={selected ? 'step' : undefined}
                onClick={() => onSelect(step.id)}
              >
                <span className="microstep-list__number">{index + 1}</span>
                <span className="microstep-list__copy">
                  <strong>{step.name}</strong>
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
