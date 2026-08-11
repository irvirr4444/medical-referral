import { useEffect, useState } from 'react'
import type { FlowOpsPageId } from '../../data/flowOps'
import type { HumanDecisionRecord } from './ops/types'
import type { HumanGateDefinition } from './ops/humanGates'

const STORAGE_KEY = 'wcw-demo-human-decisions-v1'

export function useHumanDecisions() {
  const [decisions, setDecisions] = useState<HumanDecisionRecord[]>(readStored)

  useEffect(() => {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(decisions))
    } catch {
      // The demo still works when browser storage is unavailable.
    }
  }, [decisions])

  const recordDecision = ({
    stageId,
    patientId,
    patientName,
    stepId,
    gate,
  }: {
    stageId: FlowOpsPageId
    patientId: string
    patientName: string
    stepId: string
    gate: HumanGateDefinition
  }) => {
    setDecisions((current) => {
      if (
        current.some(
          (decision) =>
            decision.stageId === stageId &&
            decision.patientId === patientId &&
            decision.stepId === stepId,
        )
      ) {
        return current
      }

      return [
        ...current,
        {
          id: `decision-${stageId}-${patientId}-${stepId}`,
          stageId,
          patientId,
          patientName,
          stepId,
          actionLabel: gate.confirmedLabel,
          summary: gate.decisionSummary,
          occurredAt: new Date().toISOString(),
        },
      ]
    })
  }

  return { decisions, recordDecision }
}

function readStored(): HumanDecisionRecord[] {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as HumanDecisionRecord[]) : []
  } catch {
    return []
  }
}
