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
    expect(state.providerAvailabilityUnread).toBe(true)

    state = demoReducer(state, { type: 'MARK_PROVIDER_AVAILABILITY_READ' })
    expect(state.providerAvailabilityUnread).toBe(false)

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

  it('marks all automatic handoff steps unread after assignment confirm', () => {
    let state = createInitialState()
    state = demoReducer(state, {
      type: 'CONFIRM_ASSIGNMENT_HANDOFF',
      patientId: 'gloria-bennett',
      patientName: 'Gloria Bennett',
      occurredAt: 'August 13, 2026 at 11:10 AM',
    })
    expect(state.latestAssignmentHandoff?.patientId).toBe('gloria-bennett')
    expect(state.assignmentNotifyUnread).toBe(true)
    expect(state.handoffNavUnread).toBe(true)
    expect(state.handoffNotifyUnread).toBe(true)
    expect(state.handoffMondayUnread).toBe(true)
    expect(state.handoffDrkUnread).toBe(true)
    expect(state.providerNavUnread).toBe(true)
    expect(state.providerSelectUnread).toBe(true)

    state = demoReducer(state, { type: 'SET_ACTIVE_PAGE', page: 'handoff' })
    expect(state.handoffNavUnread).toBe(false)
    expect(state.handoffNotifyUnread).toBe(true)
    expect(state.assignmentNotifyUnread).toBe(true)
    expect(state.providerNavUnread).toBe(true)
    expect(state.providerSelectUnread).toBe(true)

    state = demoReducer(state, { type: 'MARK_ASSIGNMENT_NOTIFY_READ' })
    expect(state.assignmentNotifyUnread).toBe(false)

    state = demoReducer(state, {
      type: 'MARK_HANDOFF_STEP_READ',
      stepId: 'notify-referral-source',
    })
    expect(state.handoffNotifyUnread).toBe(false)
    expect(state.handoffMondayUnread).toBe(true)
    expect(state.handoffDrkUnread).toBe(true)
    expect(state.providerSelectUnread).toBe(true)

    state = demoReducer(state, { type: 'SET_ACTIVE_PAGE', page: 'provider' })
    expect(state.providerNavUnread).toBe(false)
    expect(state.providerSelectUnread).toBe(true)

    state = demoReducer(state, { type: 'MARK_PROVIDER_SELECT_READ' })
    expect(state.providerSelectUnread).toBe(false)
  })

  it('marks provider availability and end-of-day follow-up unread for stage tabs', () => {
    let state = createInitialState()
    state = demoReducer(state, {
      type: 'CONFIRM_PROVIDER_SELECTION',
      patientId: 'thomas-reed',
      requestedAt: 'August 12, 2026 at 2:18 PM',
      deadlineAt: 'August 12, 2026 at 3:18 PM',
    })
    expect(state.providerAvailabilityUnread).toBe(true)

    state = demoReducer(state, { type: 'MARK_PROVIDER_AVAILABILITY_READ' })
    expect(state.providerAvailabilityUnread).toBe(false)

    state = demoReducer(state, {
      type: 'CONFIRM_EOD_FOLLOW_UP',
      patientId: 'thomas-reed',
    })
    expect(state.eodFollowUpUnread).toBe(true)
    expect(state.latestEodFollowUpPatientId).toBe('thomas-reed')

    state = demoReducer(state, { type: 'MARK_EOD_FOLLOW_UP_READ' })
    expect(state.eodFollowUpUnread).toBe(false)

    state = demoReducer(state, {
      type: 'CONFIRM_EOD_ESCALATION',
      patientId: 'maria-alvarez',
    })
    expect(state.eodEscalationUnread).toBe(true)
    expect(state.latestEodEscalationPatientId).toBe('maria-alvarez')

    state = demoReducer(state, { type: 'MARK_EOD_ESCALATION_READ' })
    expect(state.eodEscalationUnread).toBe(false)
  })

  it('stores intake field edits until confirm, then ignores further edits', () => {
    let state = createInitialState()
    state = demoReducer(state, {
      type: 'EDIT_INTAKE_FIELD',
      patientId: 'gonzalez-eric',
      key: 'home_health_or_hospice',
      value: 'VNA of Southern California',
    })
    expect(state.intakeFieldEdits['gonzalez-eric']['home_health_or_hospice']).toBe(
      'VNA of Southern California',
    )
    expect(state.intakeVerified['gonzalez-eric']).toBeUndefined()

    const confirmed = demoReducer(state, {
      type: 'CONFIRM_INTAKE_REVIEW',
      patientId: 'gonzalez-eric',
      patientName: 'Gonzalez, Eric',
      occurredAt: 'August 13, 2026 at 12:27 PM',
    })
    expect(confirmed.intakeVerified['gonzalez-eric']).toBe(true)
    expect(confirmed.latestIntakeReview?.patientId).toBe('gonzalez-eric')
    expect(confirmed.intakeMondayUnread).toBe(true)
    expect(confirmed.intakeDrkUnread).toBe(true)
    expect(confirmed.intakePartnerUnread).toBe(true)

    const afterMondayRead = demoReducer(confirmed, {
      type: 'MARK_INTAKE_STEP_READ',
      stepId: 'check-monday',
    })
    expect(afterMondayRead.intakeMondayUnread).toBe(false)
    expect(afterMondayRead.intakeDrkUnread).toBe(true)
    expect(afterMondayRead.intakePartnerUnread).toBe(true)

    const afterDrkRead = demoReducer(afterMondayRead, {
      type: 'MARK_INTAKE_STEP_READ',
      stepId: 'check-drk',
    })
    expect(afterDrkRead.intakeDrkUnread).toBe(false)
    expect(afterDrkRead.intakePartnerUnread).toBe(true)

    const afterPartnerRead = demoReducer(afterDrkRead, {
      type: 'MARK_INTAKE_STEP_READ',
      stepId: 'confirm-referral-contacted',
    })
    expect(afterPartnerRead.intakePartnerUnread).toBe(false)

    const afterEdit = demoReducer(confirmed, {
      type: 'EDIT_INTAKE_FIELD',
      patientId: 'gonzalez-eric',
      key: 'home_health_or_hospice',
      value: 'changed after lock',
    })
    expect(afterEdit).toBe(confirmed)
    expect(afterEdit.intakeFieldEdits['gonzalez-eric']['home_health_or_hospice']).toBe(
      'VNA of Southern California',
    )

    const afterSecondConfirm = demoReducer(confirmed, {
      type: 'CONFIRM_INTAKE_REVIEW',
      patientId: 'gonzalez-eric',
      patientName: 'Gonzalez, Eric',
      occurredAt: 'August 13, 2026 at 12:28 PM',
    })
    expect(afterSecondConfirm).toBe(confirmed)

    const reopened = demoReducer(confirmed, {
      type: 'REOPEN_INTAKE_REVIEW',
      patientId: 'gonzalez-eric',
    })
    expect(reopened.intakeVerified['gonzalez-eric']).toBe(false)
    expect(reopened.intakeMondayUnread).toBe(true)

    const afterReopenEdit = demoReducer(reopened, {
      type: 'EDIT_INTAKE_FIELD',
      patientId: 'gonzalez-eric',
      key: 'home_health_or_hospice',
      value: 'Preferred Home Health',
    })
    expect(
      afterReopenEdit.intakeFieldEdits['gonzalez-eric']['home_health_or_hospice'],
    ).toBe('Preferred Home Health')

    const reconfirmed = demoReducer(afterReopenEdit, {
      type: 'CONFIRM_INTAKE_REVIEW',
      patientId: 'gonzalez-eric',
      patientName: 'Gonzalez, Eric',
      occurredAt: 'August 13, 2026 at 12:29 PM',
    })
    expect(reconfirmed.intakeVerified['gonzalez-eric']).toBe(true)
    expect(reconfirmed.intakeMondayUnread).toBe(true)
  })

  it('replaces intake section rows until confirm, then ignores until reopen', () => {
    const rows = [
      {
        label: 'Secondary',
        value: 'Blue Shield PPO · 998877',
        rowId: 'insurances.new-1',
      },
    ]
    let state = createInitialState()
    state = demoReducer(state, {
      type: 'REPLACE_INTAKE_SECTION_ROWS',
      patientId: 'gonzalez-eric',
      sectionId: 'insurance',
      rows,
    })
    expect(state.intakeSectionRows['gonzalez-eric'].insurance).toEqual(rows)

    const confirmed = demoReducer(state, {
      type: 'CONFIRM_INTAKE_REVIEW',
      patientId: 'gonzalez-eric',
      patientName: 'Gonzalez, Eric',
      occurredAt: 'August 13, 2026 at 12:27 PM',
    })
    expect(confirmed.intakeVerified['gonzalez-eric']).toBe(true)

    const afterReplace = demoReducer(confirmed, {
      type: 'REPLACE_INTAKE_SECTION_ROWS',
      patientId: 'gonzalez-eric',
      sectionId: 'insurance',
      rows: [{ label: 'Other', value: 'changed after lock', rowId: 'x' }],
    })
    expect(afterReplace).toBe(confirmed)
    expect(afterReplace.intakeSectionRows['gonzalez-eric'].insurance).toEqual(rows)

    const reopened = demoReducer(confirmed, {
      type: 'REOPEN_INTAKE_REVIEW',
      patientId: 'gonzalez-eric',
    })
    const afterReopen = demoReducer(reopened, {
      type: 'REPLACE_INTAKE_SECTION_ROWS',
      patientId: 'gonzalez-eric',
      sectionId: 'insurance',
      rows: [{ label: 'Other', value: 'Preferred payer', rowId: 'x' }],
    })
    expect(
      afterReopen.intakeSectionRows['gonzalez-eric'].insurance,
    ).toEqual([
      { label: 'Other', value: 'Preferred payer', rowId: 'x' },
    ])
  })

  it('scopes and clears the operations worklist patient', () => {
    let state = createInitialState()
    expect(state.opsScopedPatient).toBeNull()
    state = demoReducer(state, {
      type: 'SCOPE_OPS_PATIENT',
      patientId: 'frank-owens',
      patientName: 'Frank Owens',
    })
    expect(state.opsScopedPatient).toEqual({
      patientId: 'frank-owens',
      patientName: 'Frank Owens',
    })
    state = demoReducer(state, { type: 'SET_ACTIVE_PAGE', page: 'intake' })
    expect(state.opsScopedPatient?.patientId).toBe('frank-owens')
    state = demoReducer(state, { type: 'CLEAR_OPS_PATIENT' })
    expect(state.opsScopedPatient).toBeNull()
  })

  it('starts, warns, overdues, and resolves confirmation timers', () => {
    const eligibleAt = 1_000_000
    let state = createInitialState()
    state = demoReducer(state, {
      type: 'START_ACTION_TIMER',
      patientId: 'test-patient',
      patientName: 'Test Patient',
      actionId: 'confirm-intake-review',
      now: eligibleAt,
    })
    const id = 'test-patient:confirm-intake-review'
    expect(state.actionTimers[id]?.status).toBe('pending')
    expect(state.actionTimers[id]?.deadlineAt).toBe(eligibleAt + 15_000)

    const pendingAgain = demoReducer(state, {
      type: 'START_ACTION_TIMER',
      patientId: 'test-patient',
      patientName: 'Test Patient',
      actionId: 'confirm-intake-review',
      now: eligibleAt + 1_000,
    })
    expect(pendingAgain.actionTimers[id]?.eligibleAt).toBe(eligibleAt)

    state = demoReducer(state, {
      type: 'TICK_ACTION_TIMERS',
      now: eligibleAt + 11_250,
    })
    expect(state.actionTimers[id]?.status).toBe('warning')

    state = demoReducer(state, {
      type: 'TICK_ACTION_TIMERS',
      now: eligibleAt + 15_000,
    })
    expect(state.actionTimers[id]?.status).toBe('overdue')

    state = demoReducer(state, {
      type: 'RESOLVE_ACTION_TIMER',
      patientId: 'test-patient',
      actionId: 'confirm-intake-review',
      now: eligibleAt + 16_000,
    })
    expect(state.actionTimers[id]?.status).toBe('resolved')
    expect(state.actionTimers[id]?.resolvedAt).toBe(eligibleAt + 16_000)

    state = demoReducer(state, { type: 'RESET' })
    expect(state.actionTimers[id]).toBeUndefined()
    expect(state.actionTimers['butler-alva:confirm-partner-contacted']?.status).toBe(
      'overdue',
    )
  })

  it('selects a slot, toggles deselect, schedules the patient, and stays idempotent', () => {
    let state = createInitialState()
    const maria = state.patientSchedules['maria-alvarez']!
    expect(maria.status).toBe('waiting')
    expect(maria.slots.some((slot) => slot.status === 'unavailable')).toBe(true)

    const unavailable = maria.slots.find((slot) => slot.status === 'unavailable')!
    state = demoReducer(state, {
      type: 'SELECT_SCHEDULING_SLOT',
      patientId: 'maria-alvarez',
      slotId: unavailable.id,
    })
    expect(state.patientSchedules['maria-alvarez']?.selectedSlotId).toBeNull()

    state = demoReducer(state, {
      type: 'SELECT_SCHEDULING_SLOT',
      patientId: 'maria-alvarez',
      slotId: 'maria-today-1530',
    })
    expect(state.patientSchedules['maria-alvarez']?.selectedSlotId).toBe(
      'maria-today-1530',
    )

    state = demoReducer(state, {
      type: 'SELECT_SCHEDULING_SLOT',
      patientId: 'maria-alvarez',
      slotId: 'maria-today-1530',
    })
    expect(state.patientSchedules['maria-alvarez']?.selectedSlotId).toBeNull()

    state = demoReducer(state, {
      type: 'SELECT_SCHEDULING_SLOT',
      patientId: 'maria-alvarez',
      slotId: 'maria-today-1530',
    })
    expect(state.patientSchedules['maria-alvarez']?.selectedSlotId).toBe(
      'maria-today-1530',
    )

    state = demoReducer(state, {
      type: 'COMPLETE_PATIENT_SCHEDULE',
      patientId: 'maria-alvarez',
      scheduledAt: 'August 14, 2026 at 3:40 PM',
    })
    const scheduled = state.patientSchedules['maria-alvarez']
    expect(scheduled?.status).toBe('scheduled')
    expect(scheduled?.appointmentDate).toBe('August 14, 2026')
    expect(scheduled?.appointmentTime).toBe('3:30 PM')
    expect(state.actionTimers['maria-alvarez:schedule-patient']?.status).toBe(
      'resolved',
    )

    const after = demoReducer(state, {
      type: 'COMPLETE_PATIENT_SCHEDULE',
      patientId: 'maria-alvarez',
      scheduledAt: 'August 14, 2026 at 4:00 PM',
    })
    expect(after).toBe(state)

    const blockedAttempt = demoReducer(state, {
      type: 'RECORD_SCHEDULING_BLOCKER',
      patientId: 'maria-alvarez',
      reason: 'patient_declined',
      occurredAt: 'August 14, 2026 at 4:00 PM',
    })
    expect(blockedAttempt).toBe(state)
  })

  it('records a scheduling blocker without marking the patient scheduled', () => {
    let state = createInitialState()
    state = demoReducer(state, {
      type: 'RECORD_SCHEDULING_BLOCKER',
      patientId: 'thomas-reed',
      reason: 'patient_declined',
      occurredAt: 'August 14, 2026 at 4:12 PM',
    })
    expect(state.patientSchedules['thomas-reed']?.status).toBe('blocked')
    expect(state.patientSchedules['thomas-reed']?.blockerReason).toBe(
      'patient_declined',
    )
    expect(state.patientSchedules['thomas-reed']?.appointmentDate).toBeUndefined()
    expect(state.patientSchedules['maria-alvarez']?.status).toBe('waiting')
    expect(state.actionTimers['thomas-reed:schedule-patient']?.status).toBe(
      'resolved',
    )
  })
})
