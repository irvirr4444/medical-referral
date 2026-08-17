import { render, screen } from '@testing-library/react'
import { createElement } from 'react'
import { describe, expect, it } from 'vitest'
import { feedForStep } from '../features/automation/ops'
import { mergeLiveInboxFeed, isLiveInboxRow } from '../features/automation/liveInbox/feed'
import { LiveInboxStatus } from '../features/automation/liveInbox/LiveInboxStatus'
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
})
