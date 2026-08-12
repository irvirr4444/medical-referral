import type {
  LiveInboxMonitorState,
  LiveInboxPayload,
  LiveInboxReferral,
} from './types'

export async function fetchLiveInbox({
  signal,
  force = false,
  limit = 10,
}: {
  signal?: AbortSignal
  force?: boolean
  limit?: number
} = {}): Promise<LiveInboxPayload> {
  const query = new URLSearchParams({ limit: String(limit) })
  if (force) query.set('refresh', '1')
  const response = await fetch(`/api/intake/inbox?${query}`, {
    signal,
    headers: { Accept: 'application/json' },
  })
  const payload: unknown = await response.json()
  if (!response.ok) {
    const message = isRecord(payload) && typeof payload.error === 'string'
      ? payload.error
      : `Testing infobox request failed (${response.status})`
    throw new Error(message)
  }
  return parseLiveInboxPayload(payload)
}

export function parseLiveInboxPayload(value: unknown): LiveInboxPayload {
  if (!isRecord(value) || value.connected !== true || !Array.isArray(value.referrals)) {
    throw new Error('Testing infobox returned an invalid response.')
  }
  return {
    connected: true,
    source: 'testing-infobox',
    fetched_at: typeof value.fetched_at === 'string' ? value.fetched_at : undefined,
    referrals: value.referrals
      .map(parseReferral)
      .filter((item): item is LiveInboxReferral => item !== null),
  }
}

export async function fetchLiveInboxMonitor({
  signal,
}: {
  signal?: AbortSignal
} = {}): Promise<LiveInboxMonitorState> {
  const response = await fetch('/api/intake/monitor', {
    signal,
    headers: { Accept: 'application/json' },
  })
  const payload: unknown = await response.json()
  if (!response.ok) throw new Error(`Monitor status request failed (${response.status})`)
  return parseLiveInboxMonitor(payload)
}

export async function setLiveInboxMonitor(
  enabled: boolean,
): Promise<LiveInboxMonitorState> {
  const response = await fetch(
    `/api/intake/monitor/${enabled ? 'start' : 'stop'}`,
    {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: '{}',
    },
  )
  const payload: unknown = await response.json()
  if (!response.ok) throw new Error(`Monitor control request failed (${response.status})`)
  return parseLiveInboxMonitor(payload)
}

export function parseLiveInboxMonitor(value: unknown): LiveInboxMonitorState {
  if (
    !isRecord(value) ||
    value.available !== true ||
    !isMonitorState(value.state) ||
    typeof value.enabled !== 'boolean' ||
    typeof value.cycle_count !== 'number' ||
    typeof value.poll_interval_seconds !== 'number' ||
    typeof value.max_messages !== 'number' ||
    !isRecord(value.safety) ||
    value.safety.monday_writes !== false ||
    value.safety.drk_writes !== false
  ) {
    throw new Error('Live monitor returned an invalid response.')
  }
  const lastCycle = isRecord(value.last_cycle)
    && typeof value.last_cycle.kind === 'string'
    && typeof value.last_cycle.status === 'string'
    && typeof value.last_cycle.completed_at === 'string'
    ? {
        kind: value.last_cycle.kind,
        status: value.last_cycle.status,
        completed_at: value.last_cycle.completed_at,
        elapsed_seconds: typeof value.last_cycle.elapsed_seconds === 'number'
          ? value.last_cycle.elapsed_seconds
          : null,
      }
    : null
  return {
    available: true,
    state: value.state,
    enabled: value.enabled,
    active_cycle: nullableString(value.active_cycle),
    started_at: nullableString(value.started_at),
    stopped_at: nullableString(value.stopped_at),
    last_heartbeat_at: nullableString(value.last_heartbeat_at),
    next_poll_at: nullableString(value.next_poll_at),
    cycle_count: value.cycle_count,
    last_cycle: lastCycle,
    error_type: nullableString(value.error_type),
    poll_interval_seconds: value.poll_interval_seconds,
    max_messages: value.max_messages,
    safety: {
      monday_writes: false,
      drk_writes: false,
      review_email: value.safety.review_email === true,
      partner_acknowledgement: value.safety.partner_acknowledgement === true,
      drk_duplicate_check: value.safety.drk_duplicate_check === true,
    },
  }
}

function parseReferral(value: unknown): LiveInboxReferral | null {
  if (
    !isRecord(value) ||
    typeof value.id !== 'string' ||
    typeof value.filename !== 'string'
  ) {
    return null
  }
  return {
    id: value.id,
    filename: value.filename,
    subject: typeof value.subject === 'string' ? value.subject : null,
    sender: typeof value.sender === 'string' ? value.sender : null,
    received_at: typeof value.received_at === 'string' ? value.received_at : null,
    source: 'testing-infobox',
    status: isWorkflowStatus(value.status) ? value.status : 'pending_extraction',
    case_id: typeof value.case_id === 'string' ? value.case_id : null,
    patient_label: typeof value.patient_label === 'string' ? value.patient_label : null,
    steps: parseSteps(value.steps),
  }
}

function parseSteps(value: unknown): LiveInboxReferral['steps'] {
  if (!isRecord(value)) return {}
  return Object.fromEntries(
    Object.entries(value).flatMap(([key, step]) => {
      if (
        !isRecord(step) ||
        typeof step.step_id !== 'string' ||
        !isStepStatus(step.status) ||
        typeof step.summary !== 'string' ||
        typeof step.occurred_at !== 'string'
      ) return []
      return [[key, {
        step_id: step.step_id,
        status: step.status,
        summary: step.summary,
        occurred_at: step.occurred_at,
        details: isRecord(step.details) ? step.details : {},
      }]]
    }),
  )
}

function isStepStatus(value: unknown): value is import('../ops/types').PatientStepStatus {
  return ['done', 'current', 'waiting', 'blocked', 'upcoming'].includes(String(value))
}

function isWorkflowStatus(value: unknown): value is LiveInboxReferral['status'] {
  return ['pending_extraction', 'discovered', 'processing', 'needs_attention', 'completed', 'failed'].includes(String(value))
}

function isMonitorState(value: unknown): value is LiveInboxMonitorState['state'] {
  return ['stopped', 'starting', 'monitoring', 'processing', 'stopping', 'error'].includes(String(value))
}

function nullableString(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
