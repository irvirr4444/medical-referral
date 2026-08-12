import { describe, expect, it } from 'vitest'
import {
  BASELINE_METRICS,
  DEFAULT_IMPACT_ASSUMPTIONS,
  INBOX_BATCH_DELTA,
  addMetrics,
  computeImpact,
} from '../data/constants'
import {
  createInitialState,
  demoReducer,
  filterReferrals,
} from '../state/demoReducer'

describe('computeImpact', () => {
  it('computes the default capacity projection', () => {
    const projection = computeImpact(DEFAULT_IMPACT_ASSUMPTIONS)
    expect(projection.minutesReturnedPerReferral).toBe(28)
    expect(projection.reductionPercent).toBe(78)
    expect(Math.round(projection.hoursPerYear)).toBe(2100)
    expect(projection.fteEquivalent).toBeCloseTo(1.01, 2)
  })
})

describe('demoReducer', () => {
  it('starts with hybrid live metrics and a mixed spine', () => {
    const state = createInitialState()
    const inbox = state.referrals.filter((referral) => referral.inboxBatch)
    const prior = state.referrals.filter((referral) => !referral.inboxBatch)
    expect(inbox).toHaveLength(7)
    expect(prior.length).toBeGreaterThan(0)
    expect(inbox.every((referral) => referral.stage === 'received')).toBe(true)
    expect(prior.some((referral) => referral.stage !== 'received')).toBe(true)
    expect(state.batchMetrics.pdfsProcessed).toBe(BASELINE_METRICS.pdfsProcessed)
    expect(state.batchMetrics.timeReturnedMinutes).toBe(BASELINE_METRICS.timeReturnedMinutes)
  })

  it('completes inbox processing by adding to baseline metrics', () => {
    let state = createInitialState()
    state = demoReducer(state, { type: 'START_AUTOMATION' })
    state = demoReducer(state, { type: 'COMPLETE_AUTOMATION' })
    const inbox = state.referrals.filter((r) => r.inboxBatch)
    const ready = inbox.filter((r) => r.outcome === 'ready')
    const attention = inbox.filter(
      (r) => r.outcome === 'needs_information' || r.outcome === 'needs_clarification',
    )
    const blocked = inbox.filter((r) => r.outcome === 'blocked_duplicate')
    expect(ready).toHaveLength(4)
    expect(attention).toHaveLength(2)
    expect(blocked).toHaveLength(1)
    expect(state.batchMetrics).toEqual(addMetrics(BASELINE_METRICS, INBOX_BATCH_DELTA))
    expect(state.batchMetrics.destinationReady).toBe(11)
    expect(state.batchMetrics.mondayPreviewsGenerated).toBe(18)
  })

  it('rejects confirmation for blocked duplicates', () => {
    let state = createInitialState()
    state = demoReducer(state, { type: 'COMPLETE_AUTOMATION' })
    state = demoReducer(state, { type: 'CONFIRM_REFERRAL', id: 'robert-williams' })
    const robert = state.referrals.find((r) => r.id === 'robert-williams')!
    expect(robert.confirmed).toBe(false)
  })

  it('allows duplicate resolution then confirmation and one-time Monday create', () => {
    let state = createInitialState()
    state = demoReducer(state, { type: 'COMPLETE_AUTOMATION' })
    state = demoReducer(state, {
      type: 'RESOLVE_DUPLICATE',
      id: 'robert-williams',
      decision: 'different',
    })
    state = demoReducer(state, { type: 'CONFIRM_REFERRAL', id: 'robert-williams' })
    state = demoReducer(state, { type: 'SEND_TO_MONDAY', id: 'robert-williams' })
    state = demoReducer(state, {
      type: 'MONDAY_CREATED',
      id: 'robert-williams',
      itemId: 'DEMO-111111',
    })
    state = demoReducer(state, { type: 'SEND_TO_MONDAY', id: 'robert-williams' })
    const robert = state.referrals.find((r) => r.id === 'robert-williams')!
    expect(robert.confirmed).toBe(true)
    expect(robert.mondayStatus).toBe('created')
    expect(robert.mondayPreview.itemId).toBe('DEMO-111111')
  })

  it('keeps DRK in draft/assisted/face-sheet states only', () => {
    let state = createInitialState()
    state = demoReducer(state, { type: 'COMPLETE_AUTOMATION' })
    state = demoReducer(state, { type: 'CONFIRM_REFERRAL', id: 'maria-alvarez' })
    state = demoReducer(state, { type: 'MARK_DRK_ASSISTED', id: 'maria-alvarez' })
    state = demoReducer(state, { type: 'MARK_DRK_FACE_SHEET', id: 'maria-alvarez' })
    const maria = state.referrals.find((r) => r.id === 'maria-alvarez')!
    expect(['draft_ready', 'assisted_entry', 'face_sheet_ready']).toContain(maria.drkStatus)
    expect(maria.drkStatus).toBe('face_sheet_ready')
  })

  it('prepares follow-up for incomplete referrals', () => {
    let state = createInitialState()
    state = demoReducer(state, { type: 'COMPLETE_AUTOMATION' })
    state = demoReducer(state, { type: 'PREPARE_FOLLOW_UP', id: 'linda-nguyen' })
    const linda = state.referrals.find((r) => r.id === 'linda-nguyen')!
    expect(linda.followUpPrepared).toBe(true)
    expect(linda.followUpOwner).toBe('Assigned marketer')
  })

  it('resets fully to hybrid baseline', () => {
    let state = createInitialState()
    state = demoReducer(state, { type: 'COMPLETE_AUTOMATION' })
    state = demoReducer(state, { type: 'CONFIRM_REFERRAL', id: 'maria-alvarez' })
    state = demoReducer(state, { type: 'RESET' })
    expect(state.automationComplete).toBe(false)
    expect(state.referrals.filter((r) => r.inboxBatch).every((r) => !r.confirmed && r.stage === 'received')).toBe(
      true,
    )
    expect(state.batchMetrics.pdfsProcessed).toBe(BASELINE_METRICS.pdfsProcessed)
  })

  it('filters confirmed referrals', () => {
    let state = createInitialState()
    state = demoReducer(state, { type: 'COMPLETE_AUTOMATION' })
    state = demoReducer(state, { type: 'CONFIRM_REFERRAL', id: 'maria-alvarez' })
    state = demoReducer(state, { type: 'SET_QUEUE_FILTER', filter: 'confirmed' })
    expect(filterReferrals(state).map((r) => r.id)).toContain('maria-alvarez')
  })

  it('creates a scheduling handoff only after confirmed availability or completed placement', () => {
    const provider = {
      id: '59',
      name: 'Charles Cho',
      npi: '1053512566',
      city: 'Los Angeles',
    }
    let state = createInitialState()
    state = demoReducer(state, {
      type: 'CONFIRM_PROVIDER_SELECTION',
      patientId: 'thomas-reed',
      requestedAt: 'August 12, 2026 at 2:18 PM',
      deadlineAt: 'August 12, 2026 at 3:18 PM',
    })
    expect(state.schedulingHandoffUnread).toBe(false)

    const afterTimeout = demoReducer(state, {
      type: 'TIMEOUT_PROVIDER_AVAILABILITY',
      patientId: 'thomas-reed',
      resolvedAt: 'August 12, 2026 at 3:18 PM',
    })
    expect(afterTimeout.schedulingHandoffs).toHaveLength(0)
    expect(afterTimeout.providerAvailability['thomas-reed']?.outcome).toBe(
      'timeout',
    )
    expect(
      demoReducer(afterTimeout, {
        type: 'CONFIRM_PROVIDER_AVAILABILITY',
        patientId: 'thomas-reed',
        patientName: 'Thomas Reed',
        provider,
        resolvedAt: 'August 12, 2026 at 3:19 PM',
      }),
    ).toBe(afterTimeout)

    state = demoReducer(state, {
      type: 'CONFIRM_PROVIDER_AVAILABILITY',
      patientId: 'thomas-reed',
      patientName: 'Thomas Reed',
      provider,
      resolvedAt: 'August 12, 2026 at 2:31 PM',
    })
    expect(state.schedulingHandoffs[0]?.route).toBe('provider_confirmed')
    expect(state.schedulingHandoffs[0]?.samplePdf).toBe('EC - REFERRAL FORM.pdf')
    expect(state.providerRecordsUnread).toBe(true)
    expect(state.providerRecordsMessageUnread).toBe(true)
    expect(state.schedulingHandoffUnread).toBe(false)
    expect(
      demoReducer(state, {
        type: 'TIMEOUT_PROVIDER_AVAILABILITY',
        patientId: 'thomas-reed',
        resolvedAt: 'August 12, 2026 at 3:18 PM',
      }),
    ).toBe(state)

    state = demoReducer(state, { type: 'MARK_PROVIDER_RECORDS_READ' })
    expect(state.providerRecordsUnread).toBe(false)
    expect(state.providerRecordsMessageUnread).toBe(false)
    expect(state.schedulingHandoffUnread).toBe(true)
    expect(state.schedulingHandoffMessageUnread).toBe(true)

    state = demoReducer(state, { type: 'SET_ACTIVE_PAGE', page: 'scheduling' })
    expect(state.activePage).toBe('scheduling')
    expect(state.schedulingHandoffUnread).toBe(false)
    expect(state.schedulingHandoffMessageUnread).toBe(true)

    state = demoReducer(state, { type: 'MARK_SCHEDULING_HANDOFF_READ' })
    expect(state.schedulingHandoffMessageUnread).toBe(false)
  })

  it('does not create a scheduling handoff for discharged patients', () => {
    let state = createInitialState()
    state = demoReducer(state, {
      type: 'RESOLVE_PROVIDER_TERRITORY',
      patientId: 'betty-hayes',
      resolution: 'discharged',
    })
    expect(state.providerTerritoryResolutions['betty-hayes']).toBe('discharged')
    expect(state.schedulingHandoffs).toHaveLength(0)
    expect(state.schedulingHandoffUnread).toBe(false)
  })
})
