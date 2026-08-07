import { useState } from 'react'
import { ExternalLink } from 'lucide-react'
import { AUTOMATION_RUNS, exampleForRun } from './runFixtures'
import { MicrostepDetail } from './MicrostepDetail'
import { MicrostepList } from './MicrostepList'
import { RunSelector } from './RunSelector'
import type {
  AutomationRunFixture,
  AutomationStageDefinition,
  MicrostepFeedback,
} from './types'
import './StageInspector.css'

export function StageInspector({
  stage,
  onOpenReferralWorkspace,
}: {
  stage: AutomationStageDefinition
  onOpenReferralWorkspace?: () => void
}) {
  const [selectedRunId, setSelectedRunId] = useState<
    AutomationRunFixture['id']
  >(AUTOMATION_RUNS[0].id)
  const [selectedStepId, setSelectedStepId] = useState(stage.microsteps[0].id)
  const [feedback, setFeedback] = useState<MicrostepFeedback[]>([])
  const run =
    AUTOMATION_RUNS.find((item) => item.id === selectedRunId) ??
    AUTOMATION_RUNS[0]
  const selectedStep =
    stage.microsteps.find((item) => item.id === selectedStepId) ??
    stage.microsteps[0]
  const example = exampleForRun(run, selectedStep, stage.id)
  const stepFeedback = feedback.filter(
    (item) => item.runId === run.id && item.stepId === selectedStep.id,
  )

  const addFeedback = (
    category: MicrostepFeedback['category'],
    comment: string,
  ) => {
    setFeedback((current) => [
      ...current,
      {
        id: `${run.id}-${selectedStep.id}-${current.length + 1}`,
        runId: run.id,
        stepId: selectedStep.id,
        category,
        comment,
        createdAt: 'Added just now',
      },
    ])
  }

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
        {onOpenReferralWorkspace ? (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onOpenReferralWorkspace}
          >
            Open extracted referral workspace
            <ExternalLink size={16} aria-hidden="true" />
          </button>
        ) : null}
      </section>

      <RunSelector
        runs={AUTOMATION_RUNS}
        selectedRunId={selectedRunId}
        onChange={(runId) =>
          setSelectedRunId(runId as AutomationRunFixture['id'])
        }
      />

      <section
        className="stage-inspector__workspace panel"
        aria-label={`${stage.shortTitle} microsteps`}
      >
        <div className="stage-inspector__rail">
          <div>
            <p className="caption">Execution order</p>
            <h2>{stage.microsteps.length} microsteps</h2>
            <p className="muted">
              Select a step to inspect its input, output, validation, and
              feedback.
            </p>
          </div>
          <MicrostepList
            steps={stage.microsteps}
            stageId={stage.id}
            run={run}
            selectedStepId={selectedStep.id}
            onSelect={setSelectedStepId}
          />
        </div>
        <MicrostepDetail
          step={selectedStep}
          run={run}
          example={example}
          feedback={stepFeedback}
          onAddFeedback={addFeedback}
        />
      </section>
    </div>
  )
}
