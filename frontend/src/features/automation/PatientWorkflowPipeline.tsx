import { useState } from 'react'
import type { FlowOpsPageId } from '../../data/flowOps'
import { useDemo } from '../../state/useDemo'
import { timerForPatientStep } from './confirmationTimers'
import { MicrostepList } from './MicrostepList'
import {
  detailForPatientStep,
  parseOpsDate,
  patientJourneyById,
  STAGE_LABEL,
  stepsForCombinedAssignment,
  stepsForPatient,
} from './ops'
import { VISIBLE_STAGE_IDS, canonicalOpsPageId } from './combinedAssignment'
import { resolvePatientKey } from './patientProfile'
import { StageFeedMessage } from './StageFeedMessage'
import { automationStage } from './stages'
import './PatientProfilePage.css'
import './StageInspector.css'
import './StageOps.css'

type PipelineStep = ReturnType<typeof stepsForPatient>[number]

function activeStep(steps: PipelineStep[]) {
  return (
    steps.find(
      (step) =>
        step.status === 'current' ||
        step.status === 'waiting' ||
        step.status === 'blocked',
    ) ?? steps[0]
  )
}

export function PatientWorkflowPipeline({ patientKey }: { patientKey: string }) {
  const { state } = useDemo()
  const resolved = resolvePatientKey(patientKey)
  const journey = resolved
    ? patientJourneyById(resolved.patientId, resolved.patientName)
    : null
  const [viewedStageId, setViewedStageId] = useState<FlowOpsPageId>(
    canonicalOpsPageId(journey?.currentStageId ?? 'intake'),
  )
  const [selectedByStage, setSelectedByStage] = useState<
    Partial<Record<FlowOpsPageId, string>>
  >({})

  if (!journey) return null

  const visibleCurrentStageId = canonicalOpsPageId(journey.currentStageId)
  const currentStage = journey.stages.find(
    (stage) => stage.stageId === journey.currentStageId,
  )
  const currentStep = activeStep(
    visibleCurrentStageId === 'assignment'
      ? stepsForCombinedAssignment(journey.patientId)
      : stepsForPatient(journey.currentStageId, journey.patientId),
  )
  const skim = [
    STAGE_LABEL[visibleCurrentStageId],
    currentStep?.stepName,
    currentStage?.headline,
  ]
    .filter(Boolean)
    .join(' · ')

  const microsteps = automationStage(viewedStageId).microsteps
  const viewedSteps =
    viewedStageId === 'assignment'
      ? stepsForCombinedAssignment(journey.patientId)
      : stepsForPatient(viewedStageId, journey.patientId)
  const stepStatuses = viewedSteps.length
    ? Object.fromEntries(viewedSteps.map((step) => [step.stepId, step.status]))
    : undefined
  const selectedStepId =
    selectedByStage[viewedStageId] ??
    activeStep(viewedSteps)?.stepId ??
    microsteps[0]?.id ??
    ''
  const patientStepIdsByStatus = (status: 'overdue' | 'warning') =>
    Object.values(state.actionTimers)
      .filter(
        (timer) =>
          timer.status === status &&
          timer.patientId === journey.patientId &&
          timer.stageId === viewedStageId,
      )
      .map((timer) => timer.stepId)

  const selectedMicrostep = microsteps.find((step) => step.id === selectedStepId)
  const selectedStep = viewedSteps.find((step) => step.stepId === selectedStepId)
  const when = selectedStep?.occurredAt
    ? parseOpsDate(selectedStep.occurredAt)
    : null

  return (
    <section className="patient-workflow" aria-label="Demo workflow">
      <p className="patient-profile__label">Demo workflow</p>
      {skim ? <p className="patient-workflow__skim">{skim}</p> : null}

      <div className="patient-workflow__stages">
        {VISIBLE_STAGE_IDS.map((stageId, index) => {
          const outcome = journey.stages.find(
            (stage) => stage.stageId === stageId,
          )
          const status = outcome?.status ?? 'upcoming'
          const viewing = viewedStageId === stageId
          const current = visibleCurrentStageId === stageId
          return (
            <button
              key={stageId}
              type="button"
              className={`patient-workflow__stage is-${status}${current ? ' is-journey-current' : ''}${viewing ? ' is-viewing' : ''}`}
              aria-current={current ? 'step' : undefined}
              aria-pressed={viewing}
              onClick={() => setViewedStageId(stageId)}
            >
              {index + 1} {STAGE_LABEL[stageId]}
            </button>
          )
        })}
      </div>

      <div
        className="stage-ops panel"
        aria-label={`${STAGE_LABEL[viewedStageId]} operations`}
      >
        <div className="stage-ops-steps" aria-label="Patient steps">
          <aside className="stage-ops-steps__rail">
            <div className="stage-ops-steps__rail-copy">
              <h2>{microsteps.length} steps</h2>
              <p className="muted">Select a step to see patient updates.</p>
            </div>
            <MicrostepList
              steps={microsteps}
              selectedStepId={selectedStepId}
              onSelect={(stepId) =>
                setSelectedByStage((current) => ({
                  ...current,
                  [viewedStageId]: stepId,
                }))
              }
              stepStatuses={stepStatuses}
              overdueStepIds={patientStepIdsByStatus('overdue')}
              warningStepIds={patientStepIdsByStatus('warning')}
            />
          </aside>

          <div className="stage-ops-steps__detail">
            <div className="stage-ops-steps__toolbar">
              <div className="stage-ops-steps__toolbar-copy">
                <h3>{selectedMicrostep?.name ?? 'Step'}</h3>
              </div>
            </div>

            {selectedStep ? (
              <ol
                className="stage-ops-step-feed"
                aria-label="Step updates"
                key={selectedStepId}
              >
                <li className="stage-ops-step-feed__day">
                  <h4 className="stage-ops-step-feed__day-header">
                    <time dateTime={when?.key}>{when?.label ?? 'Undated'}</time>
                    <span className="stage-ops-step-feed__day-count">
                      1 update
                    </span>
                  </h4>

                  <ul className="stage-ops-step-feed__rows">
                    <li className="stage-ops-step-feed__item is-open">
                      <StageFeedMessage
                        summary={selectedStep.summary}
                        patientName={journey.patientName}
                        status={selectedStep.status}
                        occurredAt={selectedStep.occurredAt}
                        detail={detailForPatientStep(
                          viewedStageId,
                          journey.patientId,
                          selectedStep.stepId,
                        )}
                        actionTimer={timerForPatientStep(
                          state.actionTimers,
                          journey.patientId,
                          selectedStep.stepId,
                        )}
                      />
                    </li>
                  </ul>
                </li>
              </ol>
            ) : (
              <p className="muted">No demo updates for this step yet.</p>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
