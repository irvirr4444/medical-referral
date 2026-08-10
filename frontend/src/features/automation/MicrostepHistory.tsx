import { ArrowRight } from 'lucide-react'
import type { AutomationMicrostep } from './types'
import type { LifecycleHistoryEntry } from './fixtures/lifecycleHistory'
import './MicrostepHistory.css'

const STATUS_LABELS: Record<LifecycleHistoryEntry['status'], string> = {
  completed: 'Completed',
  attention: 'Needs attention',
  waiting: 'Waiting',
  planned: 'Planned example',
}

interface HistoryDate {
  dateTime: string
  day: string
  key: string
  label: string
  month: string
  time: string
}

function historyDate(value: string): HistoryDate {
  const parsed = new Date(value.replace(' at ', ' '))

  if (Number.isNaN(parsed.getTime())) {
    return {
      dateTime: value,
      day: '--',
      key: value,
      label: value,
      month: 'DATE',
      time: value,
    }
  }

  const dateTime = parsed.toISOString()
  const month = new Intl.DateTimeFormat('en-US', { month: 'short' })
    .format(parsed)
    .toUpperCase()

  return {
    dateTime,
    day: String(parsed.getDate()).padStart(2, '0'),
    key: dateTime.slice(0, 10),
    label: new Intl.DateTimeFormat('en-US', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }).format(parsed),
    month,
    time: new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    }).format(parsed),
  }
}

export function MicrostepHistory({
  step,
  entries,
  compact = false,
}: {
  step: AutomationMicrostep
  entries: LifecycleHistoryEntry[]
  /** Intake-only: date/time + output produced, no patient/run/status chrome. */
  compact?: boolean
}) {
  return (
    <article
      className={`microstep-history${compact ? ' microstep-history--compact' : ''}`}
      aria-labelledby={`microstep-${step.id}`}
    >
      <header className="microstep-history__header">
        <div>
          {!compact ? <p className="caption">Run history</p> : null}
          <h2 id={`microstep-${step.id}`}>{step.name}</h2>
          <p>{step.description}</p>
        </div>
      </header>

      <ol className="microstep-history__stream" aria-label="Microstep run history">
        {entries.map((entry, index) => {
          const occurredAt = historyDate(entry.occurredAt)
          const previousDate =
            index > 0 ? historyDate(entries[index - 1].occurredAt) : null
          const startsDate = previousDate?.key !== occurredAt.key

          return (
            <li key={entry.id} className="microstep-history__entry">
              <div className="microstep-history__marker">
                {startsDate ? (
                  <time
                    className="microstep-history__date"
                    dateTime={occurredAt.dateTime}
                    aria-label={occurredAt.label}
                  >
                    <span>{occurredAt.month}</span>
                    <strong>{occurredAt.day}</strong>
                  </time>
                ) : (
                  <span
                    className="microstep-history__date-continuation"
                    aria-hidden="true"
                  />
                )}
                {compact ? (
                  <time
                    className="microstep-history__gutter-time"
                    dateTime={occurredAt.dateTime}
                  >
                    {occurredAt.time}
                  </time>
                ) : null}
              </div>
              <article>
                {compact ? null : (
                  <>
                    <header className="microstep-history__entry-header">
                      <div>
                        <strong>{entry.patientName}</strong>
                        {index === 0 ? (
                          <span className="microstep-history__latest">Latest</span>
                        ) : null}
                      </div>
                      <time dateTime={occurredAt.dateTime}>{occurredAt.time}</time>
                    </header>
                    <p className="microstep-history__run">
                      Run {entry.runId} | {STATUS_LABELS[entry.status]}
                    </p>
                  </>
                )}
                {compact ? (
                  <div className="microstep-history__change microstep-history__change--output-only">
                    <section>
                      <p>{entry.output}</p>
                    </section>
                  </div>
                ) : (
                  <div className="microstep-history__change">
                    <section>
                      <span>Input received</span>
                      <p>{entry.input}</p>
                    </section>
                    <ArrowRight size={18} aria-hidden="true" />
                    <section>
                      <span>Output produced</span>
                      <p>{entry.output}</p>
                    </section>
                  </div>
                )}
              </article>
            </li>
          )
        })}
      </ol>
    </article>
  )
}
