import { useState } from 'react'
import { Check, Circle, Search, Users, Waypoints, X } from 'lucide-react'
import {
  buildJourneyRoster,
  buildPatientJourney,
  JOURNEY_STAGE_ORDER,
  type JourneyStepView,
} from '../data/patientJourney'
import { useEscapeDismiss } from '../hooks/useEscapeDismiss'
import { useDemo } from '../state/useDemo'
import './PatientJourneyPanel.css'

function stepStateClass(step: JourneyStepView, currentId: string | null, focusId: string | null) {
  const parts = ['patient-journey__step']
  if (step.done) parts.push('is-done')
  if (currentId === step.caseId) parts.push('is-current')
  if (focusId === step.caseId) parts.push('is-focused')
  return parts.join(' ')
}

export function PatientJourneyPanel() {
  const { state, dispatch } = useDemo()
  const [pickerOpen, setPickerOpen] = useState(false)
  const [patientQuery, setPatientQuery] = useState('')
  const roster = buildJourneyRoster(state.workflowScenarios)
  const journey = buildPatientJourney(state.workflowScenarios, state.selectedJourneyPatientId)
  const normalizedQuery = patientQuery.trim().toLowerCase()
  const filteredRoster = roster.filter(({ patient, journey: item }) =>
    [patient.patientName, patient.scenarioLabel, patient.context, item.stuckStageLabel]
      .join(' ')
      .toLowerCase()
      .includes(normalizedQuery),
  )
  const rosterGroups: Array<{
    stage: string
    label: string
    items: typeof filteredRoster
  }> = JOURNEY_STAGE_ORDER.map((stage) => ({
    stage,
    label: roster[0]?.journey.steps.find((step) => step.stage === stage)?.stageLabel ?? stage,
    items: filteredRoster.filter(({ journey: item }) => item.current?.stage === stage),
  })).filter((group) => group.items.length > 0)
  const completedPatients = filteredRoster.filter(({ journey: item }) => item.complete)
  if (completedPatients.length > 0) {
    rosterGroups.push({ stage: 'complete', label: 'Complete', items: completedPatients })
  }
  const advanceLabel = journey.complete
    ? 'Journey complete'
    : journey.current
      ? `${journey.current.actionLabel} →`
      : 'Advance journey'

  useEscapeDismiss(pickerOpen, () => setPickerOpen(false))

  return (
    <>
      <section className="patient-journey" aria-label="Patient journey">
        <div className="patient-journey__header">
          <div className="patient-journey__identity">
            <p className="patient-journey__eyebrow">
              <Waypoints size={14} aria-hidden="true" />
              Live patient census
            </p>
            <h2>{journey.patientName}</h2>
            <p className="muted">
              {journey.scenarioLabel}
              <span aria-hidden="true"> · </span>
              {journey.context}
              <span aria-hidden="true"> · </span>
              Waiting at {journey.stuckStageLabel}
              <span aria-hidden="true"> · </span>
              {journey.completedCount} of {journey.totalSteps} stages complete
              {journey.minutesOnPath > 0 ? (
                <>
                  <span aria-hidden="true"> · </span>
                  {journey.minutesLabel} returned on this path
                </>
              ) : null}
            </p>
          </div>
          <div className="patient-journey__actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setPickerOpen(true)}
            >
              <Users size={15} aria-hidden="true" />
              Choose patient
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={journey.complete}
              onClick={() => {
                dispatch({ type: 'ADVANCE_JOURNEY' })
                window.scrollTo({ top: 0, behavior: 'smooth' })
              }}
            >
              {advanceLabel}
            </button>
          </div>
        </div>

        {journey.complete ? (
          <p className="patient-journey__complete" role="status">
            Journey complete — capacity returned on this path: {journey.minutesLabel}
          </p>
        ) : null}

        <ol className="patient-journey__spine">
          {journey.steps.map((step, index) => (
            <li key={step.caseId}>
              {index > 0 ? (
                <span className="patient-journey__connector" aria-hidden="true" />
              ) : null}
              <button
                type="button"
                className={stepStateClass(
                  step,
                  journey.current?.caseId ?? null,
                  state.journeyFocusCaseId,
                )}
                onClick={() => {
                  dispatch({ type: 'FOCUS_JOURNEY_STEP', caseId: step.caseId })
                  window.scrollTo({ top: 0, behavior: 'smooth' })
                }}
              >
                <span className="patient-journey__dot" aria-hidden="true">
                  {step.done ? (
                    <Check size={12} strokeWidth={3} />
                  ) : (
                    <Circle size={10} strokeWidth={2.5} />
                  )}
                </span>
                <span className="patient-journey__stage">{step.stageLabel}</span>
                <span className="patient-journey__short">
                  {step.done ? step.resultLabel : step.shortLabel}
                </span>
              </button>
            </li>
          ))}
        </ol>
      </section>

      {pickerOpen ? (
        <div
          className="patient-picker-backdrop"
          role="presentation"
          onClick={() => setPickerOpen(false)}
        >
          <section
            className="patient-picker panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="patient-picker-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="patient-picker__header">
              <div>
                <p className="caption">{roster.length} live patient journeys</p>
                <h2 id="patient-picker-title">Choose a patient</h2>
              </div>
              <button
                type="button"
                className="btn btn-secondary patient-picker__close"
                aria-label="Close patient list"
                onClick={() => setPickerOpen(false)}
              >
                <X size={16} aria-hidden="true" />
              </button>
            </header>
            <label className="patient-picker__search">
              <Search size={16} aria-hidden="true" />
              <input
                type="search"
                value={patientQuery}
                onChange={(event) => setPatientQuery(event.target.value)}
                placeholder="Search patient, stage, or care path"
                aria-label="Search patient journeys"
              />
            </label>
            <div className="patient-picker__list">
              {rosterGroups.map((group) => (
                <section className="patient-picker__group" key={group.stage}>
                  <h3>
                    {group.label}
                    <span>{group.items.length}</span>
                  </h3>
                  {group.items.map(({ patient, journey: item }) => {
                    const selected = patient.id === state.selectedJourneyPatientId
                    return (
                      <button
                        key={patient.id}
                        type="button"
                        className={`patient-picker__patient ${selected ? 'is-selected' : ''}`}
                        aria-current={selected ? 'true' : undefined}
                        onClick={() => {
                          setPickerOpen(false)
                          setPatientQuery('')
                          dispatch({ type: 'SELECT_JOURNEY_PATIENT', patientId: patient.id })
                          window.scrollTo({ top: 0, behavior: 'smooth' })
                        }}
                      >
                        <span>
                          <strong>{patient.patientName}</strong>
                          <small>{patient.scenarioLabel}</small>
                        </span>
                        <span className="patient-picker__progress">
                          <strong>{item.stuckStageLabel}</strong>
                          <small>
                            {item.completedCount} of {item.totalSteps} complete
                          </small>
                        </span>
                      </button>
                    )
                  })}
                </section>
              ))}
              {filteredRoster.length === 0 ? (
                <p className="patient-picker__empty">No patient journeys match that search.</p>
              ) : null}
            </div>
          </section>
        </div>
      ) : null}
    </>
  )
}
