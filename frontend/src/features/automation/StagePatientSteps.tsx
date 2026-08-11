import { useEffect, useMemo, useState } from 'react'
import { Search, Users, X } from 'lucide-react'
import { useEscapeDismiss } from '../../hooks/useEscapeDismiss'
import { MicrostepList } from './MicrostepList'
import { StagePatientStepDetail } from './StagePatientStepDetail'
import {
  defaultPatientIdForStage,
  detailForPatientStep,
  patientsForStage,
  stepsForPatient,
} from './ops'
import type { FlowOpsPageId } from '../../data/flowOps'
import type { AutomationMicrostep } from './types'
import './StageOps.css'

export function StagePatientSteps({
  stageId,
  microsteps,
  selectedPatientId,
  onSelectPatient,
}: {
  stageId: FlowOpsPageId
  microsteps: AutomationMicrostep[]
  selectedPatientId: string
  onSelectPatient: (patientId: string, patientName: string) => void
}) {
  const [query, setQuery] = useState('')
  const [listOpen, setListOpen] = useState(false)
  const [selectedStepId, setSelectedStepId] = useState(microsteps[0]?.id ?? '')
  const [confirmedByPatient, setConfirmedByPatient] = useState<
    Record<string, Record<string, true>>
  >({})

  useEffect(() => {
    setListOpen(false)
    setQuery('')
    setConfirmedByPatient({})
  }, [stageId])

  const patients = patientsForStage(stageId)
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return patients
    return patients.filter((patient) =>
      patient.patientName.toLowerCase().includes(normalized),
    )
  }, [patients, query])

  const activeId =
    selectedPatientId ||
    defaultPatientIdForStage(stageId) ||
    patients[0]?.patientId
  const activePatient =
    patients.find((patient) => patient.patientId === activeId) ?? patients[0]
  const rawSteps = activePatient
    ? stepsForPatient(stageId, activePatient.patientId)
    : []
  const patientConfirmed = activePatient
    ? confirmedByPatient[activePatient.patientId] ?? {}
    : {}
  const steps = useMemo(
    () =>
      rawSteps.map((step) =>
        patientConfirmed[step.stepId]
          ? {
              ...step,
              status: 'done' as const,
              summary:
                step.status === 'done'
                  ? step.summary
                  : `${step.summary} · confirmation recorded`,
            }
          : step,
      ),
    [rawSteps, patientConfirmed],
  )

  const stepStatuses = useMemo(() => {
    const map: Record<string, (typeof steps)[number]['status']> = {}
    for (const step of steps) {
      map[step.stepId] = step.status
    }
    return map
  }, [steps])

  const focusStepId = useMemo(
    () => focusStepIdForProgress(steps) || microsteps[0]?.id || '',
    [steps, microsteps],
  )

  useEffect(() => {
    if (focusStepId) setSelectedStepId(focusStepId)
  }, [activePatient?.patientId, focusStepId, stageId])

  const stepDetail =
    activePatient && selectedStepId
      ? detailForPatientStep(
          stageId,
          activePatient.patientId,
          selectedStepId,
        )
      : null
  const detailWithConfirm =
    stepDetail && patientConfirmed[selectedStepId]
      ? {
          ...stepDetail,
          progress: stepDetail.progress
            ? {
                ...stepDetail.progress,
                status: 'done' as const,
                summary:
                  stepDetail.progress.status === 'done'
                    ? stepDetail.progress.summary
                    : `${stepDetail.progress.summary} · confirmation recorded`,
              }
            : stepDetail.progress,
        }
      : stepDetail

  const canConfirmSelected = Boolean(
    stepDetail?.progress &&
      (stepDetail.progress.status === 'waiting' ||
        stepDetail.progress.status === 'blocked' ||
        stepDetail.progress.status === 'current'),
  )
  const isSelectedConfirmed = Boolean(patientConfirmed[selectedStepId])

  const confirmSelectedStep = () => {
    if (!activePatient || !selectedStepId) return
    setConfirmedByPatient((current) => ({
      ...current,
      [activePatient.patientId]: {
        ...(current[activePatient.patientId] ?? {}),
        [selectedStepId]: true,
      },
    }))
  }

  const closePatientList = () => {
    setListOpen(false)
    setQuery('')
  }

  useEscapeDismiss(listOpen, closePatientList)

  return (
    <div className="stage-ops-steps" aria-label="Patient steps">
      <aside className="stage-ops-steps__rail">
        <div className="stage-ops-steps__rail-copy">
          <h2>{microsteps.length} steps</h2>
          <p className="muted">
            Select a patient and step to inspect what happened.
          </p>
        </div>
        <MicrostepList
          steps={microsteps}
          selectedStepId={selectedStepId}
          onSelect={setSelectedStepId}
          stepStatuses={stepStatuses}
        />
      </aside>

      <div className="stage-ops-steps__detail">
        {activePatient ? (
          <>
            <div className="stage-ops-steps__toolbar">
              <h3>{activePatient.patientName}</h3>
              <button
                type="button"
                className="stage-ops-steps__see-patients"
                aria-label="Patient list"
                onClick={() => {
                  setQuery('')
                  setListOpen(true)
                }}
              >
                <Users size={16} aria-hidden="true" />
                Patient list
                <span className="stage-ops-steps__patient-count">
                  {patients.length}
                </span>
              </button>
            </div>
            {detailWithConfirm ? (
              <StagePatientStepDetail
                detail={detailWithConfirm}
                canConfirm={canConfirmSelected}
                isConfirmed={isSelectedConfirmed}
                onConfirm={confirmSelectedStep}
              />
            ) : null}
          </>
        ) : (
          <p className="muted">No patients in this stage.</p>
        )}
      </div>

      {listOpen ? (
        <div
          className="stage-ops-steps__backdrop"
          role="presentation"
          onClick={closePatientList}
        >
          <section
            className="stage-ops-steps__modal panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="stage-patient-list-title"
            data-modal-scroll
            onClick={(event) => event.stopPropagation()}
          >
            <header className="stage-ops-steps__modal-header">
              <div>
                <h2 id="stage-patient-list-title">Patients in this stage</h2>
                <p className="stage-ops-steps__modal-count">
                  {filtered.length === patients.length
                    ? `${patients.length} patients`
                    : `${filtered.length} of ${patients.length} patients`}
                </p>
              </div>
              <button
                type="button"
                className="stage-ops-steps__modal-close"
                aria-label="Close patient list"
                onClick={closePatientList}
              >
                <X size={16} aria-hidden="true" />
              </button>
            </header>

            <label className="stage-ops-steps__modal-search">
              <Search size={16} aria-hidden="true" />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search patients"
                aria-label="Search patients"
                autoFocus
              />
            </label>

            <ul
              className="stage-ops-steps__modal-list"
              aria-label="Patients in this stage"
              data-modal-scroll
            >
              {filtered.map((patient) => {
                const selected = patient.patientId === activePatient?.patientId
                const progress = stepsForPatient(stageId, patient.patientId).find(
                  (step) =>
                    step.status === 'current' ||
                    step.status === 'waiting' ||
                    step.status === 'blocked',
                )
                return (
                  <li key={patient.patientId}>
                    <button
                      type="button"
                      className={`stage-ops-steps__modal-patient ${selected ? 'is-selected' : ''}`}
                      aria-current={selected ? 'true' : undefined}
                      onClick={() => {
                        onSelectPatient(patient.patientId, patient.patientName)
                        closePatientList()
                      }}
                    >
                      <span
                        className="stage-ops-steps__modal-avatar"
                        aria-hidden="true"
                      >
                        {initials(patient.patientName)}
                      </span>
                      <span className="stage-ops-steps__modal-copy">
                        <strong>{patient.patientName}</strong>
                        <small>
                          {progress
                            ? `${patientStatusLabel(progress.status)} · ${progress.stepName}`
                            : 'Complete'}
                        </small>
                      </span>
                    </button>
                  </li>
                )
              })}
              {filtered.length === 0 ? (
                <li className="stage-ops-steps__modal-empty">
                  No patients match your search.
                </li>
              ) : null}
            </ul>
          </section>
        </div>
      ) : null}
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

function focusStepIdForProgress(
  steps: Array<{ stepId: string; status: string }>,
) {
  const active = steps.find(
    (step) =>
      step.status === 'current' ||
      step.status === 'waiting' ||
      step.status === 'blocked',
  )
  if (active) return active.stepId
  const lastDone = [...steps].reverse().find((step) => step.status === 'done')
  return lastDone?.stepId ?? steps[0]?.stepId ?? ''
}

function patientStatusLabel(status: string) {
  switch (status) {
    case 'current':
      return 'In progress'
    case 'waiting':
      return 'Waiting'
    case 'blocked':
      return 'Blocked'
    default:
      return 'Next'
  }
}
