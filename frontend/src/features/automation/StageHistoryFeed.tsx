import { historyDaysForStage, parseOpsDate } from './ops'
import type { FlowOpsPageId } from '../../data/flowOps'
import './StageOps.css'

export function StageHistoryFeed({
  stageId,
  onSelectPatient,
}: {
  stageId: FlowOpsPageId
  onSelectPatient: (patientId: string, patientName: string) => void
}) {
  const days = historyDaysForStage(stageId)

  return (
    <div className="stage-ops-history" aria-label="Stage history">
      <ol className="stage-ops-history__stream">
        {days.map((day) => (
          <li key={day.key} className="stage-ops-history__day">
            <div className="stage-ops-history__marker">
              <time className="stage-ops-history__date" aria-label={day.label}>
                <span>{day.month}</span>
                <strong>{day.day}</strong>
              </time>
            </div>
            <div className="stage-ops-history__day-body">
              {day.sections.map((section) => (
                <section key={`${day.key}-${section.eventType}`} className="stage-ops-history__section">
                  <h3>
                    {section.label}
                    <span>{section.events.length}</span>
                  </h3>
                  <ul>
                    {section.events.map((event) => {
                      const when = parseOpsDate(event.occurredAt)
                      return (
                        <li key={event.id}>
                          <button
                            type="button"
                            className="stage-ops-history__event"
                            onClick={() =>
                              onSelectPatient(event.patientId, event.patientName)
                            }
                          >
                            <time dateTime={event.occurredAt}>{when.time}</time>
                            <div>
                              <strong>{event.patientName}</strong>
                              <p>{event.summary}</p>
                            </div>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                </section>
              ))}
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
