import { Check, ChevronRight } from 'lucide-react'
import type { AutomationMicrostep } from './types'
import type { PatientStepStatus } from './ops/types'
import './Microstep.css'

export function MicrostepList({
  steps,
  selectedStepId,
  onSelect,
  stepStatuses,
}: {
  steps: AutomationMicrostep[]
  selectedStepId: string
  onSelect: (stepId: string) => void
  stepStatuses?: Record<string, PatientStepStatus>
}) {
  return (
    <nav className="microstep-list" aria-label="Automation steps">
      <ol>
        {steps.map((step, index) => {
          const selected = step.id === selectedStepId
          const status = stepStatuses?.[step.id]
          const statusClass = status ? ` is-${status}` : ''
          return (
            <li key={step.id}>
              <button
                type="button"
                className={`microstep-list__button${statusClass}${selected ? ' is-selected' : ''}`}
                aria-current={selected ? 'step' : undefined}
                data-status={status}
                onClick={() => onSelect(step.id)}
              >
                <span className="microstep-list__number" aria-hidden="true">
                  {status === 'done' ? <Check size={14} strokeWidth={2.5} /> : index + 1}
                </span>
                <span className="microstep-list__copy">
                  <strong>{step.name}</strong>
                  {status && status !== 'upcoming' ? (
                    <span className="microstep-list__status">
                      {listStatusLabel(status)}
                    </span>
                  ) : null}
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

function listStatusLabel(status: PatientStepStatus) {
  switch (status) {
    case 'done':
      return 'Done'
    case 'current':
      return 'In progress'
    case 'waiting':
      return 'Waiting'
    case 'blocked':
      return 'Blocked'
    default:
      return ''
  }
}
