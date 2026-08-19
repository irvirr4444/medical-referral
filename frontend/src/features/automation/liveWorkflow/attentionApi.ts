import type { AttentionPayload, AttentionSignal } from './attention'

export async function fetchWorkflowAttention(signal?: AbortSignal): Promise<AttentionPayload> {
  const response = await fetch('/api/workflow/attention?limit=200', {
    signal,
    headers: { Accept: 'application/json' },
  })
  const payload: unknown = await response.json()
  if (!response.ok || !isAttentionPayload(payload)) {
    throw new Error('Workflow attention is unavailable.')
  }
  return payload
}

function isAttentionPayload(value: unknown): value is AttentionPayload {
  if (!isRecord(value) || !Array.isArray(value.items) || !isRecord(value.summary)) {
    return false
  }
  return value.items.every(isAttentionSignal)
}

function isAttentionSignal(value: unknown): value is AttentionSignal {
  return (
    isRecord(value)
    && typeof value.signal_id === 'string'
    && typeof value.case_id === 'string'
    && typeof value.patient_label === 'string'
    && typeof value.stage === 'number'
    && typeof value.step_id === 'string'
    && typeof value.severity === 'string'
    && typeof value.status === 'string'
    && typeof value.action_label === 'string'
    && typeof value.source === 'string'
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
