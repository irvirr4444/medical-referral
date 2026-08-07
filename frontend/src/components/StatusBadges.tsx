import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  MinusCircle,
  ShieldAlert,
} from 'lucide-react'
import type { DuplicateStatus, FieldStatus, ReferralOutcome } from '../types'

export function FieldStatusBadge({ status }: { status: FieldStatus }) {
  const map = {
    complete: { label: 'Complete', className: 'badge-ready', Icon: CheckCircle2 },
    explicitly_none: {
      label: 'Explicitly none',
      className: 'badge-ready',
      Icon: MinusCircle,
    },
    missing: { label: 'Missing', className: 'badge-attention', Icon: AlertTriangle },
    unclear: { label: 'Unclear', className: 'badge-attention', Icon: CircleHelp },
  } as const
  const item = map[status]
  const Icon = item.Icon
  return (
    <span className={`badge ${item.className}`}>
      <Icon size={14} aria-hidden="true" />
      {item.label}
    </span>
  )
}

export function OutcomeBadge({
  outcome,
  duplicateStatus,
  confirmed,
  processed = true,
}: {
  outcome: ReferralOutcome
  duplicateStatus: DuplicateStatus
  confirmed: boolean
  processed?: boolean
}) {
  if (!processed) {
    return (
      <span className="badge badge-neutral">
        <CircleHelp size={14} aria-hidden="true" />
        Received
      </span>
    )
  }
  if (confirmed) {
    return (
      <span className="badge badge-ready">
        <CheckCircle2 size={14} aria-hidden="true" />
        Confirmed
      </span>
    )
  }
  if (duplicateStatus === 'probable_duplicate' || outcome === 'blocked_duplicate') {
    return (
      <span className="badge badge-blocked">
        <ShieldAlert size={14} aria-hidden="true" />
        Possible duplicate blocked
      </span>
    )
  }
  if (outcome === 'needs_information' || outcome === 'needs_clarification') {
    return (
      <span className="badge badge-attention">
        <AlertTriangle size={14} aria-hidden="true" />
        Needs attention
      </span>
    )
  }
  return (
    <span className="badge badge-ready">
      <CheckCircle2 size={14} aria-hidden="true" />
      Ready for Monday.com
    </span>
  )
}

export function DuplicateBadge({ status }: { status: DuplicateStatus }) {
  if (status === 'clear') {
    return (
      <span className="badge badge-ready">
        <CheckCircle2 size={14} aria-hidden="true" />
        Clear
      </span>
    )
  }
  if (status === 'resolved_different') {
    return (
      <span className="badge badge-ready">
        <CheckCircle2 size={14} aria-hidden="true" />
        Resolved as different
      </span>
    )
  }
  return (
    <span className="badge badge-blocked">
      <ShieldAlert size={14} aria-hidden="true" />
      Probable duplicate
    </span>
  )
}
