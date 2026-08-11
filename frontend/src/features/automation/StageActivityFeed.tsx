import { useEffect, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { activityFeedForStage, parseOpsDate } from './ops'
import type { FlowOpsPageId } from '../../data/flowOps'
import type { HumanDecisionRecord } from './ops/types'
import './StageOps.css'

export function StageActivityFeed({
  stageId,
  decisions,
  onSelectPatient,
}: {
  stageId: FlowOpsPageId
  decisions: HumanDecisionRecord[]
  onSelectPatient: (patientId: string, patientName: string) => void
}) {
  const days = activityFeedForStage(
    stageId,
    decisions
      .filter((decision) => decision.stageId === stageId)
      .map((decision) => ({
        id: decision.id,
        stageId: decision.stageId,
        eventType: 'human-decision',
        patientId: decision.patientId,
        patientName: decision.patientName,
        occurredAt: decision.occurredAt,
        summary: decision.summary,
        status: 'resolved' as const,
      })),
  )
  const [collapsedDays, setCollapsedDays] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    setCollapsedDays(new Set())
  }, [stageId])

  const toggleDay = (dayKey: string) => {
    setCollapsedDays((current) => {
      const next = new Set(current)
      if (next.has(dayKey)) next.delete(dayKey)
      else next.add(dayKey)
      return next
    })
  }

  return (
    <div className="stage-ops-feed" aria-label="History">
      <ol className="stage-ops-feed__days">
        {days.map((day) => {
          const expanded = !collapsedDays.has(day.key)
          const panelId = `feed-day-${day.key}`
          return (
            <li
              key={day.key}
              className={`stage-ops-feed__day${expanded ? '' : ' is-collapsed'}`}
            >
              <h3 className="stage-ops-feed__day-header">
                <button
                  type="button"
                  className="stage-ops-feed__day-toggle"
                  aria-expanded={expanded}
                  aria-controls={panelId}
                  onClick={() => toggleDay(day.key)}
                >
                  <ChevronDown
                    size={16}
                    className="stage-ops-feed__chevron"
                    aria-hidden="true"
                  />
                  <time dateTime={day.key}>{day.label}</time>
                  <span className="stage-ops-feed__day-count">
                    {day.messages.length}{' '}
                    {day.messages.length === 1 ? 'update' : 'updates'}
                  </span>
                </button>
              </h3>

              {expanded ? (
                <ul
                  id={panelId}
                  className="stage-ops-feed__messages"
                >
                  {day.messages.map((message) => {
                    const when = parseOpsDate(message.occurredAt)
                    return (
                      <li key={message.id}>
                        <button
                          type="button"
                          className="stage-ops-feed__message"
                          onClick={() =>
                            onSelectPatient(
                              message.patientId,
                              message.patientName,
                            )
                          }
                        >
                          <span
                            className="stage-ops-feed__avatar"
                            aria-hidden="true"
                          >
                            {initials(message.patientName)}
                          </span>
                          <span className="stage-ops-feed__copy">
                            <strong>{message.patientName}</strong>
                            <span className="stage-ops-feed__summary">
                              {message.summary}
                            </span>
                          </span>
                          <span className="stage-ops-feed__meta">
                            <time dateTime={message.occurredAt}>
                              {when.time}
                            </time>
                            <span
                              className={`stage-ops-feed__status is-${message.status}`}
                            >
                              {message.status === 'open' ? 'Open' : 'Done'}
                            </span>
                          </span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              ) : null}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

function initials(name: string) {
  return name
    .split(/[\s,]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}
