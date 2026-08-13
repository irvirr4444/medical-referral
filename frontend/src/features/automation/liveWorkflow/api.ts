import type {
  CaseManagerChoice,
  LiveAssignment,
  LiveHandoff,
} from './types'

export async function fetchAssignments(signal?: AbortSignal) {
  const response = await fetch('/api/workflow/assignments?limit=100', {
    signal,
    headers: { Accept: 'application/json' },
  })
  const payload: unknown = await response.json()
  if (!response.ok || !isRecord(payload) || !Array.isArray(payload.items)) {
    throw new Error('Assignment workflow is unavailable.')
  }
  return {
    assignments: payload.items.filter(isAssignment) as LiveAssignment[],
    caseManagers: Array.isArray(payload.case_managers)
      ? payload.case_managers.filter(isCaseManager) as CaseManagerChoice[]
      : [],
  }
}

export async function fetchHandoffs(signal?: AbortSignal) {
  const response = await fetch('/api/workflow/handoffs?limit=100', {
    signal,
    headers: { Accept: 'application/json' },
  })
  const payload: unknown = await response.json()
  if (!response.ok || !isRecord(payload) || !Array.isArray(payload.items)) {
    throw new Error('Handoff workflow is unavailable.')
  }
  return payload.items.filter(isHandoff) as LiveHandoff[]
}

export async function confirmAssignment({
  caseId,
  caseManagerEmail,
}: {
  caseId: string
  caseManagerEmail: string
}) {
  const response = await fetch(
    `/api/workflow/assignments/${encodeURIComponent(caseId)}/confirm`,
    {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        case_manager_email: caseManagerEmail,
        decided_by: 'demo-operator',
      }),
    },
  )
  const payload: unknown = await response.json()
  if (!response.ok) {
    const message = isRecord(payload) && typeof payload.error === 'string'
      ? payload.error
      : 'Assignment could not be confirmed.'
    throw new Error(message)
  }
}

function isCaseManager(value: unknown): value is CaseManagerChoice {
  return isRecord(value)
    && typeof value.name === 'string'
    && typeof value.email === 'string'
}

function isAssignment(value: unknown): value is LiveAssignment {
  return isRecord(value)
    && typeof value.work_item_id === 'string'
    && typeof value.case_id === 'string'
    && typeof value.status === 'string'
    && typeof value.owner_role === 'string'
    && typeof value.updated_at === 'string'
}

function isHandoff(value: unknown): value is LiveHandoff {
  return isRecord(value)
    && typeof value.case_id === 'string'
    && typeof value.status === 'string'
    && Array.isArray(value.operations)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
