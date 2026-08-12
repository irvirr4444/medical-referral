import { LoaderCircle, Play, RefreshCw, Square } from 'lucide-react'
import type { LiveInboxState } from './types'

export function LiveInboxStatus({
  state,
  onRefresh,
  onToggle,
}: {
  state: LiveInboxState
  onRefresh: () => void
  onToggle: () => void
}) {
  const monitor = state.monitor
  const monitorActive = monitor?.enabled
    || ['starting', 'monitoring', 'processing', 'stopping'].includes(monitor?.state ?? '')
  const detail = monitor?.last_cycle
    ? `Last ${monitor.last_cycle.kind}: ${monitor.last_cycle.status}`
    : monitor?.state === 'stopped'
      ? 'No background processing while off'
      : 'Monday and DRK writes are disabled'
  const toggleLabel = monitorActive ? 'Stop live monitoring' : 'Start live monitoring'

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
        <button
          type="button"
          className="stage-ops-live-inbox__toggle"
          onClick={onToggle}
          disabled={!monitor || state.monitorControlPending || monitor.state === 'stopping'}
          aria-label={toggleLabel}
        >
          {state.monitorControlPending || monitor?.state === 'starting' ? (
            <LoaderCircle className="is-spinning" size={14} aria-hidden="true" />
          ) : monitorActive ? (
            <Square size={12} fill="currentColor" aria-hidden="true" />
          ) : (
            <Play size={14} fill="currentColor" aria-hidden="true" />
          )}
          <span>{monitorActive ? 'Stop' : 'Start'}</span>
        </button>
      </span>
    </div>
  )
}

function statusLabel(state: LiveInboxState) {
  if (state.status === 'loading') return 'Connecting test infobox...'
  if (state.status === 'unavailable') return 'Demo data - test infobox unavailable'
  const count = `${state.referrals.length} PDF${state.referrals.length === 1 ? '' : 's'}`
  switch (state.monitor?.state) {
    case 'starting': return `Starting live monitor - ${count}`
    case 'monitoring': return `Monitoring test infobox - ${count}`
    case 'processing': return `Processing ${cycleLabel(state.monitor.active_cycle)} - ${count}`
    case 'stopping': return `Stopping after current cycle - ${count}`
    case 'error': return `Monitor needs attention - ${count}`
    default: return `Live monitoring off - ${count}`
  }
}

function cycleLabel(value: string | null | undefined) {
  return {
    poll: 'new referrals',
    retries: 'retry queue',
    approvals: 'review replies',
  }[value ?? ''] ?? 'Stage 1'
}
