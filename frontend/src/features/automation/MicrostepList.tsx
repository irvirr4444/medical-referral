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
  warningStepIds?: string[]
  unreadCounts?: Record<string, number>
  stepStatuses?: Record<string, string>
}) {
  return (
    <nav className="microstep-list" aria-label="Automation steps">
      <ol>
        {steps.map((step, index) => {
          const selected = step.id === selectedStepId
          const overdueCount = overdueCounts[step.id] ?? 0
          const isOverdue =
            overdueCount > 0 || overdueStepIds.includes(step.id)
          const isDueSoon = !isOverdue && warningStepIds.includes(step.id)
          const unreadCount = Math.max(
            unreadCounts[step.id] ?? 0,
            attentionStepIds.includes(step.id) ? 1 : 0,
          )
          const needsAttention = unreadCount > 0
          const stepStatus = stepStatuses?.[step.id]
          const overdueBadge = isOverdue ? overdueCount || 1 : 0
          const parts = [
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
                }${isOverdue ? ' is-overdue' : ''}${
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
                    {overdueBadge > 0 || unreadCount > 0 ? (
                      <span className="microstep-list__badges">
                        {overdueBadge > 0 ? (
                          <span
                            className="microstep-list__count is-overdue"
                            aria-hidden="true"
                          >
                            {overdueBadge}
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
