import { useState } from 'react'
import { exampleForRun, runForStage } from './runFixtures'
import { MicrostepDetail } from './MicrostepDetail'
import { MicrostepHistory } from './MicrostepHistory'
import { MicrostepList } from './MicrostepList'
import { lifecycleHistoryForStep } from './fixtures/lifecycleHistory'
import type { AutomationStageDefinition } from './types'
import './StageInspector.css'

export function StageInspector({
  stage,
}: {
  stage: AutomationStageDefinition
}) {
  const [selectedStepId, setSelectedStepId] = useState(stage.microsteps[0].id)
  const run = runForStage(stage.id)
  const selectedStep =
    stage.microsteps.find((item) => item.id === selectedStepId) ??
    stage.microsteps[0]
  const example = exampleForRun(run, selectedStep, stage.id)
  const history = lifecycleHistoryForStep(stage.id, selectedStep, run, example)

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
        {history.length ? (
          <MicrostepHistory step={selectedStep} entries={history} />
        ) : (
          <MicrostepDetail step={selectedStep} run={run} example={example} />
        )}
      </section>
    </div>
  )
}
