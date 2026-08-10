import {
  defaultNowSectionId,
  openEventsForSection,
  opsRecipeForStage,
  parseOpsDate,
} from './ops'
import type { FlowOpsPageId } from '../../data/flowOps'
import './StageOps.css'

export function StageNowBoard({
  stageId,
  selectedSectionId,
  onSelectSection,
  onSelectPatient,
}: {
  stageId: FlowOpsPageId
  selectedSectionId: string
  onSelectSection: (sectionId: string) => void
  onSelectPatient: (patientId: string, patientName: string) => void
}) {
  const recipe = opsRecipeForStage(stageId)
  const activeSectionId = selectedSectionId || defaultNowSectionId(stageId)
  const rows = openEventsForSection(stageId, activeSectionId)
  const activeSection = recipe.sections.find((section) => section.id === activeSectionId)

  return (
    <div className="stage-ops-now" aria-label="Worklist">
      <nav className="stage-ops-now__sections" aria-label="Worklist categories">
        <ul>
          {recipe.sections.map((section) => {
            const count = openEventsForSection(stageId, section.id).length
            const selected = section.id === activeSectionId
            return (
              <li key={section.id}>
                <button
                  type="button"
                  className={`stage-ops-now__section ${selected ? 'is-selected' : ''} ${section.isException ? 'is-exception' : ''}`}
                  aria-current={selected ? 'true' : undefined}
                  onClick={() => onSelectSection(section.id)}
                >
                  <span>{section.label}</span>
                  <strong>{count}</strong>
                </button>
              </li>
            )
          })}
        </ul>
      </nav>

      <div className="stage-ops-now__rows">
        <header>
          <h3>{activeSection?.label ?? 'Worklist'}</h3>
          <p className="muted">
            {rows.length === 0
              ? 'Nothing needs action in this category.'
              : `${rows.length} open · click a patient to open their current step.`}
          </p>
        </header>
        <ul className="stage-ops-patient-list">
          {rows.map((event) => {
            const when = parseOpsDate(event.occurredAt)
            return (
              <li key={event.id}>
                <button
                  type="button"
                  className="stage-ops-patient-row"
                  onClick={() => onSelectPatient(event.patientId, event.patientName)}
                >
                  <div>
                    <strong>{event.patientName}</strong>
                    <p>{event.summary}</p>
                  </div>
                  <div className="stage-ops-patient-row__meta">
                    {event.ageLabel ? <span>{event.ageLabel}</span> : null}
                    <time dateTime={event.occurredAt}>{when.time}</time>
                  </div>
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    </div>
  )
}
