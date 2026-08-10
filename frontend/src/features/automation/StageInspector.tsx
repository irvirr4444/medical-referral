import { useEffect, useState } from 'react'
import { StageNowBoard } from './StageNowBoard'
import { StageActivityFeed } from './StageActivityFeed'
import { StagePatientSteps } from './StagePatientSteps'
import {
  defaultNowSectionId,
  defaultPatientIdForStage,
} from './ops'
import type { AutomationStageDefinition } from './types'
import './StageInspector.css'
import './StageOps.css'

type StageOpsTab = 'steps' | 'worklist' | 'history'

export function StageInspector({
  stage,
}: {
  stage: AutomationStageDefinition
}) {
  const [tab, setTab] = useState<StageOpsTab>('steps')
  const [selectedSectionId, setSelectedSectionId] = useState(() =>
    defaultNowSectionId(stage.id),
  )
  const [selectedPatientId, setSelectedPatientId] = useState(() =>
    defaultPatientIdForStage(stage.id),
  )

  useEffect(() => {
    setTab('steps')
    setSelectedSectionId(defaultNowSectionId(stage.id))
    setSelectedPatientId(defaultPatientIdForStage(stage.id))
  }, [stage.id])

  /** Stay on this stage; open Steps focused on the patient's current microstep. */
  const openPatientOnThisStage = (patientId: string) => {
    setSelectedPatientId(patientId)
    setTab('steps')
  }

  return (
    <div className="stage-ops panel" aria-label={`${stage.shortTitle} operations`}>
      <div className="stage-ops__tabs" role="tablist" aria-label="Stage views">
        {(
          [
            ['steps', 'Steps'],
            ['worklist', 'Worklist'],
            ['history', 'History'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={tab === id ? 'is-selected' : undefined}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="stage-ops__panel" role="tabpanel">
        {tab === 'steps' ? (
          <StagePatientSteps
            stageId={stage.id}
            microsteps={stage.microsteps}
            selectedPatientId={selectedPatientId}
            onSelectPatient={(patientId) => openPatientOnThisStage(patientId)}
          />
        ) : null}

        {tab === 'worklist' ? (
          <StageNowBoard
            stageId={stage.id}
            selectedSectionId={selectedSectionId}
            onSelectSection={setSelectedSectionId}
            onSelectPatient={(patientId) => openPatientOnThisStage(patientId)}
          />
        ) : null}

        {tab === 'history' ? (
          <StageActivityFeed
            stageId={stage.id}
            onSelectPatient={(patientId) => openPatientOnThisStage(patientId)}
          />
        ) : null}
      </div>
    </div>
  )
}
