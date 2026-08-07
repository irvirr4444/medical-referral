import type { ImplementationStatus, MicrostepRunStatus } from './types'
import './StatusBadge.css'

const IMPLEMENTATION_LABELS: Record<ImplementationStatus, string> = {
  working: 'Working',
  partial: 'Partially implemented',
  planned: 'Workflow mapped',
}

const RUN_LABELS: Record<MicrostepRunStatus, string> = {
  completed: 'Completed',
  attention: 'Needs attention',
  waiting: 'Waiting',
  planned: 'Preview only',
}

export function ImplementationBadge({
  status,
}: {
  status: ImplementationStatus
}) {
  return (
    <span className={`automation-status automation-status--${status}`}>
      {IMPLEMENTATION_LABELS[status]}
    </span>
  )
}

export function RunStatusBadge({ status }: { status: MicrostepRunStatus }) {
  return (
    <span className={`automation-run-status automation-run-status--${status}`}>
      {RUN_LABELS[status]}
    </span>
  )
}
