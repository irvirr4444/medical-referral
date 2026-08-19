import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { createElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { feedForStep } from '../features/automation/ops'
import { mergeLiveInboxFeed, isLiveInboxRow } from '../features/automation/liveInbox/feed'
import { LiveInboxStatus } from '../features/automation/liveInbox/LiveInboxStatus'
import { useLiveInbox } from '../features/automation/liveInbox/useLiveInbox'
import {
  parseLiveInboxMonitor,
  parseLiveInboxPayload,
} from '../features/automation/liveInbox/api'
import type { LiveInboxReferral } from '../features/automation/liveInbox/types'

const LIVE_REFERRAL: LiveInboxReferral = {
  id: 'live-1',
  filename: 'new-referral.pdf',
  subject: 'Wound care referral',
  sender: 'sender@example.test',
  received_at: '2026-08-12T08:30:00Z',
  source: 'testing-infobox',
  status: 'pending_extraction',
  case_id: null,
  patient_label: null,
  steps: {},
}

describe('live intake inbox', () => {
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    vi.mocked(fetch).mockReset()
    vi.mocked(fetch).mockImplementation(() =>
      Promise.reject(new Error('unmocked network request in tests')),
    )
  })

  it('adds live arrivals while retaining every demo referral', () => {
    const demoDays = feedForStep('intake', 'receive-referral')
    const demoCount = demoDays.flatMap((day) => day.rows).length
    const merged = mergeLiveInboxFeed({
      demoDays,
      referrals: [LIVE_REFERRAL],
      statuses: ['done', 'current', 'waiting', 'blocked'],
      selectedStepId: 'receive-referral',
    })
    const rows = merged.flatMap((day) => day.rows)

    expect(rows).toHaveLength(demoCount + 1)
    const live = rows.find(isLiveInboxRow)
    expect(live?.summary).toBe('Referral email identified')
    expect(live?.inbox.sender).toBe('sender@example.test')
    expect(rows.some((row) => row.patientId === 'butler-alva')).toBe(true)
  })

  it('applies the existing search and status filters to live arrivals', () => {
    const merged = mergeLiveInboxFeed({
      demoDays: [],
      referrals: [LIVE_REFERRAL],
      patientQuery: 'sender@example.test',
      statuses: ['done'],
      selectedStepId: 'receive-referral',
    })
    expect(merged.flatMap((day) => day.rows)).toHaveLength(1)

    const waiting = mergeLiveInboxFeed({
      demoDays: [],
      referrals: [LIVE_REFERRAL],
      statuses: ['waiting'],
      selectedStepId: 'receive-referral',
    })
    expect(waiting).toEqual([])
  })

  it('rejects malformed API payloads', () => {
    expect(() => parseLiveInboxPayload({ connected: true })).toThrow(
      'invalid response',
    )
  })

  it('treats stale as an optional backward-compatible payload flag', () => {
    const stale = parseLiveInboxPayload({
      connected: true,
      source: 'testing-infobox',
      fetched_at: '2026-08-18T08:00:00Z',
      stale: true,
      referrals: [LIVE_REFERRAL],
    })
    const fresh = parseLiveInboxPayload({
      connected: true,
      source: 'testing-infobox',
      referrals: [LIVE_REFERRAL],
    })
    expect(stale.stale).toBe(true)
    expect(fresh.stale).toBe(false)
  })

  it('projects persisted workflow output into the matching Stage 1 step', () => {
    const referral: LiveInboxReferral = {
      ...LIVE_REFERRAL,
      case_id: 'case_live_1',
      patient_label: 'TEST Patient',
      status: 'processing',
      steps: {
        'check-monday': {
          step_id: 'check-monday',
          status: 'done',
          summary: 'Monday duplicate check complete',
          occurred_at: '2026-08-12T08:35:00Z',
          details: { status: 'no_candidates_found' },
        },
      },
    }
    const merged = mergeLiveInboxFeed({
      demoDays: [],
      referrals: [referral],
      statuses: ['done'],
      selectedStepId: 'check-monday',
    })
    const row = merged.flatMap((day) => day.rows)[0]
    expect(row.patientName).toBe('TEST Patient')
    expect(row.summary).toBe('Monday duplicate check complete')
    expect(isLiveInboxRow(row) && row.workflowStep?.details.status).toBe(
      'no_candidates_found',
    )
  })

  it('distinguishes active extraction from later queued work', () => {
    const referral: LiveInboxReferral = {
      ...LIVE_REFERRAL,
      status: 'processing',
    }
    const extraction = mergeLiveInboxFeed({
      demoDays: [],
      referrals: [referral],
      statuses: ['current'],
      selectedStepId: 'extract-and-verify',
    }).flatMap((day) => day.rows)[0]
    const monday = mergeLiveInboxFeed({
      demoDays: [],
      referrals: [referral],
      statuses: ['waiting'],
      selectedStepId: 'check-monday',
    }).flatMap((day) => day.rows)[0]

    expect(extraction.status).toBe('current')
    expect(extraction.summary).toBe('Extracting referral details')
    expect(monday.status).toBe('waiting')
    expect(monday.summary).toBe('Queued for Monday duplicate check')
  })

  it('labels the DRK check disabled only when monitor configuration disables it', () => {
    const disabled = mergeLiveInboxFeed({
      demoDays: [],
      referrals: [LIVE_REFERRAL],
      drkDuplicateCheckEnabled: false,
      statuses: ['waiting'],
      selectedStepId: 'check-drk',
    }).flatMap((day) => day.rows)[0]
    const enabled = mergeLiveInboxFeed({
      demoDays: [],
      referrals: [LIVE_REFERRAL],
      drkDuplicateCheckEnabled: true,
      statuses: ['waiting'],
      selectedStepId: 'check-drk',
    }).flatMap((day) => day.rows)[0]
    const unknown = mergeLiveInboxFeed({
      demoDays: [],
      referrals: [LIVE_REFERRAL],
      statuses: ['waiting'],
      selectedStepId: 'check-drk',
    }).flatMap((day) => day.rows)[0]

    expect(disabled.summary).toBe('DRK chart check disabled')
    expect(enabled.summary).toBe('Queued for DRK chart check')
    expect(unknown.summary).toBe('Queued for DRK chart check')
  })

  it('does not describe an absent check as queued after Stage 1 completed', () => {
    const referral: LiveInboxReferral = {
      ...LIVE_REFERRAL,
      status: 'completed',
      case_id: 'case-completed',
    }
    const row = mergeLiveInboxFeed({
      demoDays: [],
      referrals: [referral],
      drkDuplicateCheckEnabled: true,
      statuses: ['waiting'],
      selectedStepId: 'check-drk',
    }).flatMap((day) => day.rows)[0]

    expect(row.summary).toBe('DRK chart check not recorded')
  })

  it('shows a persisted DRK result even if the current monitor has checking disabled', () => {
    const referral: LiveInboxReferral = {
      ...LIVE_REFERRAL,
      steps: {
        'check-drk': {
          step_id: 'check-drk',
          status: 'done',
          summary: 'DRK chart check complete',
          occurred_at: '2026-08-12T08:36:00Z',
          details: { status: 'clear_to_create' },
        },
      },
    }
    const row = mergeLiveInboxFeed({
      demoDays: [],
      referrals: [referral],
      drkDuplicateCheckEnabled: false,
      statuses: ['done'],
      selectedStepId: 'check-drk',
    }).flatMap((day) => day.rows)[0]

    expect(row.summary).toBe('DRK chart check complete')
  })

  it('validates the autonomous monitor status separately from mailbox connectivity', () => {
    const monitor = parseLiveInboxMonitor({
      available: true,
      state: 'processing',
      enabled: true,
      active_cycle: 'poll',
      started_at: '2026-08-12T08:30:00Z',
      stopped_at: null,
      last_heartbeat_at: '2026-08-12T08:31:00Z',
      next_poll_at: null,
      cycle_count: 2,
      last_cycle: null,
      error_type: null,
      poll_interval_seconds: 60,
      max_messages: 10,
      safety: {
        monday_writes: false,
        drk_writes: false,
        review_email: true,
        partner_acknowledgement: false,
        drk_duplicate_check: false,
      },
    })

    expect(monitor.state).toBe('processing')
    expect(monitor.safety.monday_writes).toBe(false)
    expect(() => parseLiveInboxMonitor({ available: true })).toThrow('invalid response')
  })

  it('shows monitor health without exposing worker start or stop controls', () => {
    const monitor = parseLiveInboxMonitor({
      available: true,
      state: 'monitoring',
      enabled: true,
      active_cycle: null,
      started_at: '2026-08-14T08:30:00Z',
      stopped_at: null,
      last_heartbeat_at: '2026-08-14T08:31:00Z',
      next_poll_at: '2026-08-14T08:32:00Z',
      cycle_count: 1,
      last_cycle: null,
      error_type: null,
      poll_interval_seconds: 60,
      max_messages: 1,
      safety: {
        monday_writes: false,
        drk_writes: false,
        review_email: true,
        partner_acknowledgement: true,
        drk_duplicate_check: true,
      },
    })

    render(createElement(LiveInboxStatus, {
      state: { status: 'connected', referrals: [LIVE_REFERRAL], monitor },
      onRefresh: () => undefined,
    }))

    expect(screen.getByText('Monitoring test infobox - 1 PDF')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Refresh test infobox' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /live monitoring/i })).not.toBeInTheDocument()
  })

  it('describes approval polling without presenting inbox PDFs as reply work', () => {
    const monitor = parseLiveInboxMonitor({
      available: true,
      state: 'processing',
      enabled: true,
      active_cycle: 'approvals',
      started_at: '2026-08-14T08:30:00Z',
      stopped_at: null,
      last_heartbeat_at: '2026-08-14T08:31:00Z',
      next_poll_at: null,
      cycle_count: 2,
      last_cycle: null,
      error_type: null,
      poll_interval_seconds: 60,
      max_messages: 10,
      safety: {
        monday_writes: false,
        drk_writes: false,
        review_email: true,
        partner_acknowledgement: false,
        drk_duplicate_check: false,
      },
    })

    render(createElement(LiveInboxStatus, {
      state: { status: 'connected', referrals: [LIVE_REFERRAL], monitor },
      onRefresh: () => undefined,
    }))

    expect(screen.getByText('Checking review replies')).toBeInTheDocument()
    expect(screen.queryByText(/10 PDFs/)).not.toBeInTheDocument()
  })

  it('does not treat seeded demo rows as live Outlook referrals', () => {
    const demoDays = feedForStep('intake', 'receive-referral')
    const merged = mergeLiveInboxFeed({
      demoDays,
      referrals: [],
      statuses: ['done', 'current', 'waiting', 'blocked'],
      selectedStepId: 'receive-referral',
    })
    const rows = merged.flatMap((day) => day.rows)

    expect(rows.length).toBeGreaterThan(0)
    expect(rows.every((row) => !isLiveInboxRow(row))).toBe(true)
    expect(rows.some((row) => row.patientId === 'butler-alva')).toBe(true)
  })

  it('keeps connecting copy only before monitor status arrives', () => {
    render(createElement(LiveInboxStatus, {
      state: { status: 'loading', referrals: [] },
      onRefresh: () => undefined,
    }))
    expect(screen.getByText('Connecting test infobox...')).toBeInTheDocument()
  })

  it('shows syncing rather than connecting once monitor status is available', () => {
    const monitor = parseLiveInboxMonitor({
      available: true,
      state: 'monitoring',
      enabled: true,
      active_cycle: null,
      started_at: '2026-08-14T08:30:00Z',
      stopped_at: null,
      last_heartbeat_at: '2026-08-14T08:31:00Z',
      next_poll_at: '2026-08-14T08:32:00Z',
      cycle_count: 1,
      last_cycle: null,
      error_type: null,
      poll_interval_seconds: 60,
      max_messages: 1,
      safety: {
        monday_writes: false,
        drk_writes: false,
        review_email: true,
        partner_acknowledgement: false,
        drk_duplicate_check: false,
      },
    })

    render(createElement(LiveInboxStatus, {
      state: { status: 'syncing', referrals: [], monitor },
      onRefresh: () => undefined,
    }))

    expect(screen.getByText('Monitoring test infobox · syncing referrals')).toBeInTheDocument()
    expect(screen.queryByText('Connecting test infobox...')).not.toBeInTheDocument()
  })
})

const MONITOR_BODY = {
  available: true,
  state: 'monitoring',
  enabled: true,
  active_cycle: null,
  started_at: '2026-08-14T08:30:00Z',
  stopped_at: null,
  last_heartbeat_at: '2026-08-14T08:31:00Z',
  next_poll_at: '2026-08-14T08:32:00Z',
  cycle_count: 1,
  last_cycle: null,
  error_type: null,
  poll_interval_seconds: 60,
  max_messages: 1,
  safety: {
    monday_writes: false,
    drk_writes: false,
    review_email: true,
    partner_acknowledgement: false,
    drk_duplicate_check: false,
  },
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function inboxBody() {
  return {
    connected: true,
    source: 'testing-infobox',
    fetched_at: '2026-08-18T08:00:00Z',
    referrals: [LIVE_REFERRAL],
  }
}

function createDeferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

type InboxRequest = {
  url: string
  signal: AbortSignal | undefined
  deferred: ReturnType<typeof createDeferred<Response>>
}

function mockLiveApis() {
  const inboxRequests: InboxRequest[] = []
  const monitorRequests: string[] = []
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.includes('/api/intake/monitor')) {
      monitorRequests.push(url)
      return Promise.resolve(jsonResponse(MONITOR_BODY))
    }
    if (url.includes('/api/intake/inbox')) {
      const deferred = createDeferred<Response>()
      const signal = init?.signal ?? undefined
      inboxRequests.push({ url, signal, deferred })
      if (signal?.aborted) {
        deferred.reject(Object.assign(new Error('Aborted'), { name: 'AbortError' }))
      } else {
        signal?.addEventListener('abort', () => {
          deferred.reject(Object.assign(new Error('Aborted'), { name: 'AbortError' }))
        })
      }
      return deferred.promise
    }
    return Promise.reject(new Error(`unmocked ${url}`))
  })
  return { inboxRequests, monitorRequests }
}

async function flushMicrotasks() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

async function resolveInbox(request: InboxRequest, body: unknown, status = 200) {
  await act(async () => {
    request.deferred.resolve(jsonResponse(body, status))
    await Promise.resolve()
    await Promise.resolve()
  })
}

function LiveInboxHarness({ pollIntervalMs = 1000 }: { pollIntervalMs?: number }) {
  const state = useLiveInbox(true, pollIntervalMs)
  return createElement(
    'div',
    null,
    createElement(LiveInboxStatus, { state, onRefresh: state.refresh }),
    createElement('span', { 'data-testid': 'inbox-status' }, state.status),
    createElement('span', { 'data-testid': 'inbox-filenames' },
      state.referrals.map((referral) => referral.filename).join(',')),
    createElement('span', { 'data-testid': 'inbox-error' }, state.error ?? ''),
  )
}

describe('useLiveInbox single-flight polling', () => {
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    vi.mocked(fetch).mockReset()
    vi.mocked(fetch).mockImplementation(() =>
      Promise.reject(new Error('unmocked network request in tests')),
    )
  })

  it('does not abort a slow inbox request or start a second one when the poll interval fires', async () => {
    vi.useFakeTimers()
    const { inboxRequests, monitorRequests } = mockLiveApis()
    render(createElement(LiveInboxHarness, { pollIntervalMs: 1000 }))
    await flushMicrotasks()

    expect(inboxRequests).toHaveLength(1)
    expect(monitorRequests.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Monitoring test infobox · syncing referrals')).toBeInTheDocument()
    expect(screen.queryByText('Connecting test infobox...')).not.toBeInTheDocument()

    await act(async () => {
      vi.advanceTimersByTime(3500)
    })

    expect(inboxRequests).toHaveLength(1)
    expect(inboxRequests[0].signal?.aborted).toBe(false)
    expect(monitorRequests.length).toBeGreaterThan(1)

    await resolveInbox(inboxRequests[0], inboxBody())
    expect(screen.getByTestId('inbox-status')).toHaveTextContent('connected')
    expect(screen.getByTestId('inbox-filenames')).toHaveTextContent('new-referral.pdf')
    expect(screen.getByText('Monitoring test infobox - 1 PDF')).toBeInTheDocument()
  })

  it('queues exactly one forced refresh while an inbox request is already running', async () => {
    vi.useFakeTimers()
    const { inboxRequests } = mockLiveApis()
    render(createElement(LiveInboxHarness, { pollIntervalMs: 10_000 }))
    await flushMicrotasks()
    expect(inboxRequests).toHaveLength(1)
    expect(inboxRequests[0].url).not.toContain('refresh=1')

    fireEvent.click(screen.getByRole('button', { name: 'Refresh test infobox' }))
    fireEvent.click(screen.getByRole('button', { name: 'Refresh test infobox' }))
    fireEvent.click(screen.getByRole('button', { name: 'Refresh test infobox' }))
    expect(inboxRequests).toHaveLength(1)

    await resolveInbox(inboxRequests[0], inboxBody())
    expect(inboxRequests).toHaveLength(2)
    expect(inboxRequests[1].url).toContain('refresh=1')

    await resolveInbox(inboxRequests[1], inboxBody())
    expect(inboxRequests).toHaveLength(2)
  })

  it('aborts the outstanding inbox request on unmount', async () => {
    const { inboxRequests } = mockLiveApis()
    const { unmount } = render(createElement(LiveInboxHarness, { pollIntervalMs: 10_000 }))
    await flushMicrotasks()
    expect(inboxRequests).toHaveLength(1)
    const signal = inboxRequests[0].signal
    unmount()
    expect(signal?.aborted).toBe(true)
  })

  it('preserves live rows when a later refresh fails', async () => {
    vi.useFakeTimers()
    const { inboxRequests } = mockLiveApis()
    render(createElement(LiveInboxHarness, { pollIntervalMs: 1000 }))
    await flushMicrotasks()
    await resolveInbox(inboxRequests[0], inboxBody())
    expect(screen.getByTestId('inbox-status')).toHaveTextContent('connected')
    expect(screen.getByTestId('inbox-filenames')).toHaveTextContent('new-referral.pdf')

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    expect(inboxRequests).toHaveLength(2)

    await resolveInbox(inboxRequests[1], { error: 'Graph timeout' }, 503)
    expect(screen.getByTestId('inbox-status')).toHaveTextContent('connected')
    expect(screen.getByTestId('inbox-filenames')).toHaveTextContent('new-referral.pdf')
    expect(screen.getByTestId('inbox-error')).toHaveTextContent('Graph timeout')
  })
})
