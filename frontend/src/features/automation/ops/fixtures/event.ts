import type { FlowOpsPageId } from '../../../../data/flowOps'
import type { OpsEvent, OpsEventStatus } from '../types'

export function ev(
  stageId: FlowOpsPageId,
  eventType: string,
  patientId: string,
  patientName: string,
  occurredAt: string,
  summary: string,
  status: OpsEventStatus,
  ageLabel?: string,
): OpsEvent {
  return {
    id: `${stageId}-${eventType}-${patientId}-${occurredAt}`,
    stageId,
    eventType,
    patientId,
    patientName,
    occurredAt,
    summary,
    status,
    ageLabel,
  }
}
