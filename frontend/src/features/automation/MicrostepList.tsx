import { ChevronRight } from 'lucide-react'
import { RunStatusBadge } from './StatusBadge'
import type { AutomationMicrostep, AutomationRunFixture } from './types'
import { exampleForRun } from './runFixtures'
import './Microstep.css'
import type { FlowOpsPageId } from '../../data/flowOps'

export function MicrostepList({
  steps,
  stageId,
  run,
  selectedStepId,
  onSelect,
}: {
  steps: AutomationMicrostep[]
  stageId: FlowOpsPageId
  run: AutomationRunFixture
  selectedStepId: string
  onSelect: (stepId: string) => void
}) {
  return (
    <nav className="microstep-list" aria-label="Automation microsteps">
      <ol>
        {steps.map((step, index) => {
          const selected = step.id === selectedStepId
          const example = exampleForRun(run, step, stageId)
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
                  <span>{step.system}</span>
                  <RunStatusBadge status={example.status} />
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
