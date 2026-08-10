import { useState } from 'react'
import { exampleForRun } from './runFixtures'
import { MicrostepDetail } from './MicrostepDetail'
import { MicrostepList } from './MicrostepList'
import { BUTLER_RUN_FIXTURE } from './types'
import type { AutomationStageDefinition } from './types'
import './StageInspector.css'

export function StageInspector({
  stage,
}: {
  stage: AutomationStageDefinition
}) {
  const [selectedStepId, setSelectedStepId] = useState(stage.microsteps[0].id)
  const run = BUTLER_RUN_FIXTURE
  const selectedStep =
    stage.microsteps.find((item) => item.id === selectedStepId) ??
    stage.microsteps[0]
  const example = exampleForRun(run, selectedStep, stage.id)

  return (
    <div className="stage-inspector">
      <section
        className="stage-inspector__workspace panel"
        aria-label={`${stage.shortTitle} steps`}
      >
        <div className="stage-inspector__rail">
          <div>
            <h2>{stage.microsteps.length} steps</h2>
            <p className="muted">
              Choose a step to see the automation output.
            </p>
          </div>
          <MicrostepList
            steps={stage.microsteps}
            selectedStepId={selectedStep.id}
            onSelect={setSelectedStepId}
          />
        </div>
        <MicrostepDetail step={selectedStep} example={example} />
      </section>
    </div>
  )
}
