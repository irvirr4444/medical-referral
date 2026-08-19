import { RefreshCw } from 'lucide-react'
import type { LiveInboxState } from './types'

export function LiveInboxStatus({
  state,
  onRefresh,
}: {
  state: LiveInboxState
  onRefresh: () => void
}) {
  const monitor = state.monitor
  const detail = monitor?.last_cycle
    ? `Last ${monitor.last_cycle.kind}: ${monitor.last_cycle.status}`
    : monitor?.state === 'stopped'
      ? 'No background processing while off'
      : 'Monday and DRK writes are disabled'

  return (
    <div
      className={`stage-ops-live-inbox is-${state.status} is-monitor-${monitor?.state ?? 'unknown'}`}
      title={state.error}
    >
      <span className="stage-ops-live-inbox__dot" aria-hidden="true" />
      <span className="stage-ops-live-inbox__copy">
        <strong>{statusLabel(state)}</strong>
        <small>{detail}</small>
      </span>
      <span className="stage-ops-live-inbox__actions">
        <button type="button" onClick={onRefresh} aria-label="Refresh test infobox">
          <RefreshCw size={14} aria-hidden="true" />
        </button>
      </span>
    </div>
  )
}

function statusLabel(state: LiveInboxState) {
  if (state.status === 'unavailable') return 'Demo data - test infobox unavailable'
  if (state.status === 'loading' && !state.monitor) return 'Connecting test infobox...'
  if (state.status === 'loading' || state.status === 'syncing') {
    return 'Monitoring test infobox · syncing referrals'
  }
  const count = `${state.referrals.length} PDF${state.referrals.length === 1 ? '' : 's'}`
  switch (state.monitor?.state) {
    case 'starting': return `Starting live monitor - ${count}`
    case 'monitoring': return `Monitoring test infobox - ${count}`
    case 'processing': return processingLabel(state.monitor.active_cycle, count)
    case 'stopping': return `Stopping after current cycle - ${count}`
    case 'error': return `Monitor needs attention - ${count}`
    default: return `Live monitoring off - ${count}`
  }
}

function processingLabel(cycle: string | null | undefined, count: string) {
  if (cycle === 'approvals') return 'Checking review replies'
  return `Processing ${cycleLabel(cycle)} - ${count}`
}

function cycleLabel(value: string | null | undefined) {
  return {
    poll: 'new referrals',
    retries: 'retry queue',
    approvals: 'review replies',
  }[value ?? ''] ?? 'Stage 1'
}
