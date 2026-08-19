import { ChevronRight } from 'lucide-react'
import type { AutomationMicrostep } from './types'
import './Microstep.css'

export function MicrostepList({
  steps,
  selectedStepId,
  onSelect,
  attentionStepIds = [],
  overdueStepIds = [],
  overdueCounts = {},
  blockedStepIds = [],
  blockedCounts = {},
  warningStepIds = [],
  unreadCounts = {},
  stepStatuses,
}: {
  steps: AutomationMicrostep[]
  selectedStepId: string
  onSelect: (stepId: string) => void
  attentionStepIds?: string[]
  overdueStepIds?: string[]
  overdueCounts?: Record<string, number>
  blockedStepIds?: string[]
  blockedCounts?: Record<string, number>
  warningStepIds?: string[]
  unreadCounts?: Record<string, number>
  stepStatuses?: Record<string, string>
}) {
  return (
    <nav className="microstep-list" aria-label="Automation steps">
      <ol>
        {steps.map((step, index) => {
          const selected = step.id === selectedStepId
          const blockedCount = blockedCounts[step.id] ?? 0
          const overdueCount = overdueCounts[step.id] ?? 0
          const isBlocked =
            blockedCount > 0 || blockedStepIds.includes(step.id)
          const isOverdue =
            overdueCount > 0 || overdueStepIds.includes(step.id)
          const isDueSoon =
            !isBlocked && !isOverdue && warningStepIds.includes(step.id)
          const unreadCount = Math.max(
            unreadCounts[step.id] ?? 0,
            attentionStepIds.includes(step.id) ? 1 : 0,
          )
          const needsAttention = unreadCount > 0
          const stepStatus = stepStatuses?.[step.id]
          const blockedBadge = isBlocked ? blockedCount || 1 : 0
          const overdueBadge = isOverdue ? overdueCount || 1 : 0
          const visualCount = blockedBadge + overdueBadge
          const parts = [
            blockedBadge > 0 ? `${blockedBadge} blocked` : null,
            overdueBadge > 0 ? `${overdueBadge} overdue` : null,
            unreadCount > 0
              ? `${unreadCount} new update${unreadCount === 1 ? '' : 's'}`
              : null,
            isDueSoon ? 'due soon' : null,
          ].filter(Boolean)

          return (
            <li key={step.id}>
              <button
                type="button"
                className={`microstep-list__button${selected ? ' is-selected' : ''}${
                  stepStatus ? ` is-${stepStatus}` : ''
                }${isBlocked || isOverdue ? ' is-overdue' : ''}${
                  needsAttention ? ' is-unread' : ''
                }`}
                aria-current={selected ? 'step' : undefined}
                aria-label={
                  parts.length
                    ? `${step.name}, ${parts.join(', ')}`
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
                    {visualCount > 0 || unreadCount > 0 ? (
                      <span className="microstep-list__badges">
                        {visualCount > 0 ? (
                          <span
                            className="microstep-list__count is-overdue"
                            aria-hidden="true"
                          >
                            {visualCount}
                          </span>
                        ) : null}
                        {unreadCount > 0 ? (
                          <span
                            className="microstep-list__count is-unread"
                            aria-hidden="true"
                          >
                            {unreadCount}
                          </span>
                        ) : null}
                      </span>
                    ) : isDueSoon ? (
                      <span
                        className="microstep-list__attention-dot is-warning"
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
