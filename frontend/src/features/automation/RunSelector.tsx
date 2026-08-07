import type { AutomationRunFixture } from './types'

export function RunSelector({
  runs,
  selectedRunId,
  onChange,
}: {
  runs: AutomationRunFixture[]
  selectedRunId: string
  onChange: (runId: string) => void
}) {
  const selected = runs.find((run) => run.id === selectedRunId) ?? runs[0]

  return (
    <section className="automation-run-selector" aria-label="Workflow run">
      <div>
        <label htmlFor="automation-run">Inspect workflow run</label>
        <select
          id="automation-run"
          value={selectedRunId}
          onChange={(event) => onChange(event.target.value)}
        >
          {runs.map((run) => (
            <option key={run.id} value={run.id}>
              {run.label}
            </option>
          ))}
        </select>
      </div>
      <div className="automation-run-selector__summary">
        <strong>{selected.source}</strong>
        <span>{selected.startedAt}</span>
        <p>{selected.summary}</p>
      </div>
    </section>
  )
}
