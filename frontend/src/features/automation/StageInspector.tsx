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
        className="stage-inspector__definition panel"
        aria-labelledby="stage-definition-title"
      >
        <div className="stage-inspector__definition-copy">
          <p className="caption">Stage definition</p>
          <h2 id="stage-definition-title">
            What this stage is responsible for
          </h2>
          <p>{stage.purpose}</p>
        </div>
        <dl className="stage-inspector__facts">
          <div>
            <dt>Starts when</dt>
            <dd>{stage.trigger}</dd>
          </div>
          <div>
            <dt>Successful when</dt>
            <dd>{stage.successDefinition}</dd>
          </div>
        </dl>
      </section>

      <section
        className="stage-inspector__workspace panel"
        aria-label={`${stage.shortTitle} microsteps`}
      >
        <div className="stage-inspector__rail">
          <div>
            <p className="caption">Execution order</p>
            <h2>{stage.microsteps.length} microsteps</h2>
            <p className="muted">
              Select a step to inspect progressive patient data and the output
              produced at that step.
            </p>
          </div>
          <MicrostepList
            steps={stage.microsteps}
            selectedStepId={selectedStep.id}
            onSelect={setSelectedStepId}
          />
        </div>
        <MicrostepDetail step={selectedStep} run={run} example={example} />
      </section>
    </div>
  )
}
