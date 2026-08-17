import {
  AUTOMATION_STEPS,
  BASELINE_METRICS,
  COMPLETION_MESSAGE,
  DEFAULT_IMPACT_ASSUMPTIONS,
  INBOX_BATCH_DELTA,
  addMetrics,
} from '../data/constants'
import {
  createInitialLifecycleCases,
  LIFECYCLE_STAGES,
  type LifecycleStageId,
} from '../data/lifecycle'
import { createInitialReferrals } from '../data/referrals'
import { createInitialActivityFeed } from '../data/activityFeed'
import {
  buildPatientJourney,
  DEFAULT_JOURNEY_PATIENT_ID,
  getJourneyPatient,
  patientIdForJourneyCase,
  reopenJourneyCases,
  seedJourneyProgress,
  sumCompletedJourneyCaseMinutes,
} from '../data/patientJourney'
import { createInitialWorkflowScenarios } from '../data/workflowScenarios'
import { referralPdfForPatient } from '../features/automation/fixtures/intakeDemoPatients'
import {
  seedPatientSchedules,
  selectedSlot,
  upsertScheduleFromHandoff,
} from '../features/automation/fixtures/patientSchedules'
import {
  resolveActionTimer,
  seedActionTimers,
  startActionTimer,
  tickActionTimers,
  timerPatientName,
} from '../features/automation/confirmationTimers'
import type { ScenarioBucket } from '../data/scenarioTypes'
import type {
  AutomationStep,
  AuditEvent,
  ConfirmationActionId,
  DemoState,
  ImpactAssumptions,
  ProviderTerritoryResolution,
  QueueFilter,
  ReferralRecord,
  SchedulingBlockerReason,
  SchedulingHandoff,
  SchedulingHandoffProvider,
  WorkflowStage,
} from '../types'

export type DemoAction =
  | { type: 'RESET' }
  | { type: 'START_AUTOMATION' }
  | { type: 'ADVANCE_AUTOMATION'; step: AutomationStep }
  | { type: 'COMPLETE_AUTOMATION' }
  | { type: 'SELECT_REFERRAL'; id: string | null }
  | { type: 'SET_QUEUE_FILTER'; filter: QueueFilter }
  | { type: 'SET_SPINE_FILTER'; stage: WorkflowStage | 'all' }
  | { type: 'TOGGLE_HOW_CALCULATED' }
  | { type: 'SET_ACTIVE_PAGE'; page: string }
  | { type: 'UPDATE_IMPACT_ASSUMPTIONS'; patch: Partial<ImpactAssumptions> }
  | { type: 'PREPARE_FOLLOW_UP'; id: string }
  | { type: 'RESOLVE_DUPLICATE'; id: string; decision: 'different' | 'keep_blocked' }
  | { type: 'CONFIRM_REFERRAL'; id: string }
  | { type: 'REQUEST_CORRECTION'; id: string }
  | { type: 'SEND_TO_MONDAY'; id: string }
  | { type: 'MONDAY_CREATED'; id: string; itemId: string }
  | { type: 'MARK_DRK_ASSISTED'; id: string }
  | { type: 'MARK_DRK_FACE_SHEET'; id: string }
  | { type: 'SET_LIFECYCLE_STAGE'; stageId: LifecycleStageId }
  | { type: 'START_LIFECYCLE_STAGE' }
  | { type: 'COMPLETE_LIFECYCLE_STAGE' }
  | { type: 'RESOLVE_LIFECYCLE_CASE'; id: string }
  | { type: 'SET_SCENARIO_FILTER'; filter: ScenarioBucket | 'all' }
  | { type: 'RESOLVE_SCENARIO_CASE'; id: string }
  | { type: 'SELECT_JOURNEY_PATIENT'; patientId: string }
  | { type: 'SCOPE_OPS_PATIENT'; patientId: string; patientName: string }
  | { type: 'CLEAR_OPS_PATIENT' }
  | { type: 'SET_OPS_SELECTED_STEP'; stageId: string; stepId: string }
  | { type: 'FOCUS_JOURNEY_STEP'; caseId: string }
  | { type: 'ADVANCE_JOURNEY' }
  | { type: 'RESTART_JOURNEY' }
  | { type: 'SELECT_PROVIDER'; patientId: string; providerId: string }
  | {
      type: 'CONFIRM_PROVIDER_SELECTION'
      patientId: string
      requestedAt: string
      deadlineAt: string
    }
  | {
      type: 'RESOLVE_PROVIDER_TERRITORY'
      patientId: string
      resolution: ProviderTerritoryResolution
      requestedAt?: string
      deadlineAt?: string
    }
  | {
      type: 'CONFIRM_PROVIDER_AVAILABILITY'
      patientId: string
      patientName: string
      provider: SchedulingHandoffProvider
      resolvedAt: string
    }
  | {
      type: 'TIMEOUT_PROVIDER_AVAILABILITY'
      patientId: string
      resolvedAt: string
    }
  | {
      type: 'COMPLETE_MANUAL_PLACEMENT'
      patientId: string
      patientName: string
      provider: SchedulingHandoffProvider
      readyAt: string
    }
  | { type: 'MARK_PROVIDER_RECORDS_READ' }
  | { type: 'MARK_SCHEDULING_HANDOFF_READ' }
  | {
      type: 'SELECT_SCHEDULING_SLOT'
      patientId: string
      slotId: string
    }
  | {
      type: 'COMPLETE_PATIENT_SCHEDULE'
      patientId: string
      scheduledAt: string
    }
  | {
      type: 'RECORD_SCHEDULING_BLOCKER'
      patientId: string
      reason: SchedulingBlockerReason
      occurredAt: string
    }
  | {
      type: 'CONFIRM_ASSIGNMENT_HANDOFF'
      patientId: string
      patientName: string
      occurredAt: string
    }
  | {
      type: 'MARK_HANDOFF_STEP_READ'
      stepId:
        | 'notify-referral-source'
        | 'create-monday-record'
        | 'create-update-drk'
    }
  | { type: 'MARK_ASSIGNMENT_NOTIFY_READ' }
  | { type: 'MARK_PROVIDER_SELECT_READ' }
  | { type: 'MARK_PROVIDER_AVAILABILITY_READ' }
  | { type: 'CONFIRM_EOD_FOLLOW_UP'; patientId: string }
  | { type: 'MARK_EOD_FOLLOW_UP_READ' }
  | { type: 'CONFIRM_EOD_ESCALATION'; patientId: string }
  | { type: 'MARK_EOD_ESCALATION_READ' }
  | {
      type: 'EDIT_INTAKE_FIELD'
      patientId: string
      key: string
      value: string
    }
  | {
      type: 'REPLACE_INTAKE_SECTION_ROWS'
      patientId: string
      sectionId: string
      rows: Array<{
        label: string
        value: string
        fieldPath?: string
        rowId?: string
        meta?: string
      }>
    }
  | {
      type: 'CONFIRM_INTAKE_REVIEW'
      patientId: string
      patientName: string
      occurredAt: string
    }
  | {
      type: 'MARK_INTAKE_STEP_READ'
      stepId: 'check-monday' | 'check-drk' | 'confirm-referral-contacted'
    }
  | { type: 'REOPEN_INTAKE_REVIEW'; patientId: string }
  | {
      type: 'CONFIRM_PARTNER_CONTACTED'
      patientId: string
      patientName: string
      occurredAt: string
    }
  | { type: 'MARK_ASSIGNMENT_OWNER_READ' }
  | {
      type: 'START_ACTION_TIMER'
      patientId: string
      patientName: string
      actionId: ConfirmationActionId
      now?: number
    }
  | { type: 'TICK_ACTION_TIMERS'; now: number }
  | {
      type: 'RESOLVE_ACTION_TIMER'
      patientId: string
      actionId: ConfirmationActionId
      now?: number
    }

function upsertSchedulingHandoff(
  handoffs: SchedulingHandoff[],
  next: SchedulingHandoff,
): SchedulingHandoff[] {
  return [next, ...handoffs.filter((item) => item.patientId !== next.patientId)]
}

function withSchedulingHandoff(
  state: DemoState,
  request: DemoState['providerAvailability'][string],
  action: {
    patientId: string
    patientName: string
    provider: SchedulingHandoffProvider
    route: SchedulingHandoff['route']
    readyAt: string
    outcome: 'confirmed' | 'placement_completed'
    resolvedAt: string
  },
): DemoState {
  return {
    ...state,
    providerAvailability: {
      ...state.providerAvailability,
      [action.patientId]: {
        ...request,
        outcome: action.outcome,
        resolvedAt: action.resolvedAt,
      },
    },
    schedulingHandoffs: upsertSchedulingHandoff(state.schedulingHandoffs, {
      patientId: action.patientId,
      patientName: action.patientName,
      provider: action.provider,
      route: action.route,
      requestedAt: request.requestedAt,
      deadlineAt: request.deadlineAt,
      readyAt: action.readyAt,
      samplePdf: referralPdfForPatient(action.patientId),
    }),
    patientSchedules: upsertScheduleFromHandoff(state.patientSchedules, {
      patientId: action.patientId,
      patientName: action.patientName,
      provider: action.provider,
      route: action.route,
    }),
    providerRecordsUnread: true,
    providerRecordsMessageUnread: true,
    schedulingHandoffUnread: false,
    schedulingHandoffMessageUnread: false,
    actionTimers: startActionTimer(
      resolveActionTimer(
        resolveActionTimer(
          state.actionTimers,
          action.patientId,
          'provider-availability',
          Date.now(),
        ),
        action.patientId,
        'manual-placement',
        Date.now(),
      ),
      {
        patientId: action.patientId,
        patientName: action.patientName,
        actionId: 'schedule-patient',
        now: Date.now(),
      },
    ),
  }
}

function resolveScenarioCase(state: DemoState, caseId: string): DemoState {
  let gained = 0
  let activityText: string | null = null
  let activityStage: DemoState['workflowScenarios'][number]['tab'] | null = null
  const workflowScenarios = state.workflowScenarios.map((scenario) => ({
    ...scenario,
    cases: scenario.cases.map((item) => {
      if (item.id !== caseId) return item
      if (
        item.status === 'completed' ||
        item.status === 'escalated' ||
        item.status === 'upcoming'
      ) {
        return item
      }
      gained = item.minutesReturned
      activityStage = scenario.tab
      const nextStatus =
        scenario.bucket === 'approval' || scenario.bucket === 'blocked'
          ? ('escalated' as const)
          : ('completed' as const)
      activityText = `${item.patientName}: ${item.resultLabel}`
      return {
        ...item,
        status: nextStatus,
        summary: item.resultLabel,
      }
    }),
  }))
  if (!activityText || !activityStage) return state
  return {
    ...state,
    workflowScenarios,
    scenarioMinutesReturned: state.scenarioMinutesReturned + gained,
    activityFeed: [
      {
        id: `activity-live-${Date.now()}`,
        time: 'Now',
        text: `${activityText} · ${gained} min returned`,
        stage: activityStage,
      },
      ...state.activityFeed,
    ].slice(0, 48),
  }
}

function focusJourneyStep(state: DemoState, caseId: string): DemoState {
  const patient = getJourneyPatient(state.selectedJourneyPatientId)
  const step = patient?.steps.find((item) => item.caseId === caseId)
  if (!step || !patient) return state
  return {
    ...state,
    journeyFocusCaseId: caseId,
    activePage: step.stage,
    scenarioFilter: 'all',
    // Do not auto-open the PDF workspace — only "Review Referral" should.
    selectedReferralId: null,
  }
}

function focusPatientCurrentStep(state: DemoState, patientId: string): DemoState {
  const withPatient = { ...state, selectedJourneyPatientId: patientId }
  const journey = buildPatientJourney(withPatient.workflowScenarios, patientId)
  const focusStep = journey.current ?? journey.steps[journey.steps.length - 1]
  if (!focusStep) return withPatient
  return focusJourneyStep(withPatient, focusStep.caseId)
}

/** After resolving a journey case, jump to that patient's next open stage tab. */
function advanceJourneyAfterResolve(state: DemoState, resolvedCaseId: string): DemoState {
  const patientId = patientIdForJourneyCase(resolvedCaseId)
  if (!patientId) return state
  const nextStep = buildPatientJourney(state.workflowScenarios, patientId).current
  if (!nextStep || nextStep.status !== 'upcoming') {
    return focusPatientCurrentStep(state, patientId)
  }
  const promoted = {
    ...state,
    workflowScenarios: state.workflowScenarios.map((scenario) => ({
      ...scenario,
      cases: scenario.cases.map((item) =>
        item.id === nextStep.caseId ? { ...item, status: 'open' as const } : item,
      ),
    })),
  }
  return focusPatientCurrentStep(promoted, patientId)
}

function resolveScenarioCaseAndAdvance(state: DemoState, caseId: string): DemoState {
  const resolved = resolveScenarioCase(state, caseId)
  if (resolved === state) return state
  return advanceJourneyAfterResolve(resolved, caseId)
}

function pushEvent(referral: ReferralRecord, event: Omit<AuditEvent, 'id'>): ReferralRecord {
  return {
    ...referral,
    timeline: [
      ...referral.timeline,
      {
        id: `${referral.id}-${event.label}-${referral.timeline.length}`,
        ...event,
      },
    ],
  }
}

function processedOutcomeStage(referral: ReferralRecord): WorkflowStage {
  if (referral.outcome === 'blocked_duplicate') return 'reviewed'
  if (referral.outcome === 'needs_information' || referral.outcome === 'needs_clarification') {
    return 'reviewed'
  }
  return 'reviewed'
}

function applyProcessing(referrals: ReferralRecord[]): ReferralRecord[] {
  return referrals.map((referral) => {
    if (referral.processed || !referral.inboxBatch) return referral

    let next: ReferralRecord = {
      ...referral,
      processed: true,
      stage: processedOutcomeStage(referral),
      mondayStatus:
        referral.outcome === 'ready' && referral.duplicateStatus === 'clear'
          ? 'ready'
          : referral.mondayStatus,
      drkStatus: 'draft_ready',
    }
    next = pushEvent(next, {
      timestamp: '10:22 AM',
      label: 'PDF validated',
      result: 'Valid PDF attachment accepted',
      actor: 'Intake automation',
      humanRequired: false,
    })
    next = pushEvent(next, {
      timestamp: '10:22 AM',
      label: 'Attachment fingerprint recorded',
      result: 'Duplicate attachment processing prevented',
      actor: 'Intake automation',
      humanRequired: false,
    })
    next = pushEvent(next, {
      timestamp: '10:23 AM',
      label: 'Extraction completed',
      result: `${next.completenessScore} required fields evaluated`,
      actor: 'Intake automation',
      humanRequired: false,
    })
    next = pushEvent(next, {
      timestamp: '10:23 AM',
      label: 'Source verification completed',
      result: 'Source verified against referral PDF',
      actor: 'Intake automation',
      humanRequired: false,
    })
    next = pushEvent(next, {
      timestamp: '10:24 AM',
      label: 'Duplicate search completed',
      result:
        next.duplicateStatus === 'probable_duplicate'
          ? 'Possible duplicate blocked'
          : 'No blocking duplicate detected',
      actor: 'Monday.com read-only check',
      humanRequired: next.duplicateStatus === 'probable_duplicate',
    })
    next = pushEvent(next, {
      timestamp: '10:24 AM',
      label: 'Review prepared',
      result: 'Human-review summary ready',
      actor: 'Intake automation',
      humanRequired: true,
    })
    next = pushEvent(next, {
      timestamp: '10:25 AM',
      label: 'DRK draft prepared',
      result: 'DRK chart ready · Create Patient remains human-controlled',
      actor: 'DRK draft builder',
      humanRequired: true,
    })
    return next
  })
}

export function createInitialState(): DemoState {
  const workflowScenarios = seedJourneyProgress(createInitialWorkflowScenarios())
  const selectedJourneyPatientId = DEFAULT_JOURNEY_PATIENT_ID
  const journey = buildPatientJourney(workflowScenarios, selectedJourneyPatientId)
  const focusCaseId = journey.current?.caseId ?? journey.steps[0]?.caseId ?? null

  return {
    referrals: createInitialReferrals(),
    automationStep: 'idle',
    automationRunning: false,
    automationComplete: false,
    selectedReferralId: null,
    queueFilter: 'all',
    spineFilter: 'all',
    batchMetrics: { ...BASELINE_METRICS },
    impactAssumptions: { ...DEFAULT_IMPACT_ASSUMPTIONS },
    completionMessage: null,
    howCalculatedOpen: false,
    activePage: 'overview',
    lastInboxSyncLabel: 'just now',
    activityFeed: createInitialActivityFeed(),
    lifecycleStageId: 'assignment',
    lifecycleCases: createInitialLifecycleCases(),
    lifecycleRunning: false,
    lifecycleMessage: null,
    lifecycleMinutesReturned: 0,
    workflowScenarios,
    scenarioFilter: 'all',
    scenarioMinutesReturned: sumCompletedJourneyCaseMinutes(workflowScenarios),
    journeyFocusCaseId: focusCaseId,
    selectedJourneyPatientId,
    opsScopedPatient: null,
    opsSelectedStepByStage: {},
    providerSelectedIds: {},
    providerConfirmed: {},
    providerTerritoryResolutions: {},
    providerAvailability: {},
    latestProviderAvailabilityPatientId: null,
    schedulingHandoffs: [],
    patientSchedules: seedPatientSchedules(),
    providerRecordsUnread: false,
    providerRecordsMessageUnread: false,
    schedulingHandoffUnread: false,
    schedulingHandoffMessageUnread: false,
    latestAssignmentHandoff: null,
    assignmentNotifyUnread: false,
    handoffNavUnread: false,
    handoffNotifyUnread: false,
    handoffMondayUnread: false,
    handoffDrkUnread: false,
    providerNavUnread: false,
    providerSelectUnread: false,
    providerAvailabilityUnread: false,
    eodFollowUpUnread: false,
    eodEscalationUnread: false,
    latestEodFollowUpPatientId: null,
    latestEodEscalationPatientId: null,
    intakeFieldEdits: {},
    intakeSectionRows: {},
    intakeVerified: {},
    latestIntakeReview: null,
    intakeMondayUnread: false,
    intakeDrkUnread: false,
    intakePartnerUnread: false,
    latestPartnerContact: null,
    assignmentOwnerUnread: false,
    actionTimers: seedActionTimers(),
  }
}

export function demoReducer(state: DemoState, action: DemoAction): DemoState {
  switch (action.type) {
    case 'RESET':
      return createInitialState()

    case 'START_AUTOMATION':
      if (state.automationRunning || state.automationComplete) return state
      return {
        ...state,
        automationRunning: true,
        automationStep: 'connecting',
        completionMessage: null,
        lastInboxSyncLabel: 'syncing…',
      }

    case 'ADVANCE_AUTOMATION':
      return { ...state, automationStep: action.step }

    case 'COMPLETE_AUTOMATION':
      return {
        ...state,
        automationRunning: false,
        automationComplete: true,
        automationStep: 'complete',
        referrals: applyProcessing(state.referrals),
        batchMetrics: addMetrics(BASELINE_METRICS, INBOX_BATCH_DELTA),
        completionMessage: COMPLETION_MESSAGE,
        lastInboxSyncLabel: 'just now',
        activityFeed: [
          {
            id: `activity-inbox-${Date.now()}`,
            time: '10:25 AM',
            text: 'Processed 7 inbox referrals · 4 ready for confirmation',
          },
          ...state.activityFeed,
        ].slice(0, 8),
      }

    case 'SELECT_REFERRAL':
      return { ...state, selectedReferralId: action.id }

    case 'SET_QUEUE_FILTER':
      return { ...state, queueFilter: action.filter }

    case 'SET_SPINE_FILTER':
      return { ...state, spineFilter: action.stage }

    case 'TOGGLE_HOW_CALCULATED':
      return { ...state, howCalculatedOpen: !state.howCalculatedOpen }

    case 'SET_ACTIVE_PAGE':
      return {
        ...state,
        activePage: action.page,
        scenarioFilter: 'all',
        selectedReferralId: null,
        schedulingHandoffUnread:
          action.page === 'scheduling' ? false : state.schedulingHandoffUnread,
        handoffNavUnread:
          action.page === 'handoff' ? false : state.handoffNavUnread,
        providerNavUnread:
          action.page === 'provider' ? false : state.providerNavUnread,
      }

    case 'SET_SCENARIO_FILTER':
      return { ...state, scenarioFilter: action.filter }

    case 'RESOLVE_SCENARIO_CASE':
      return resolveScenarioCaseAndAdvance(state, action.id)

    case 'SELECT_JOURNEY_PATIENT':
      return focusPatientCurrentStep(state, action.patientId)

    case 'SCOPE_OPS_PATIENT':
      return {
        ...state,
        opsScopedPatient: {
          patientId: action.patientId,
          patientName: action.patientName,
        },
      }

    case 'CLEAR_OPS_PATIENT':
      return { ...state, opsScopedPatient: null }

    case 'SET_OPS_SELECTED_STEP':
      if (state.opsSelectedStepByStage[action.stageId] === action.stepId) {
        return state
      }
      return {
        ...state,
        opsSelectedStepByStage: {
          ...state.opsSelectedStepByStage,
          [action.stageId]: action.stepId,
        },
      }

    case 'FOCUS_JOURNEY_STEP':
      return focusJourneyStep(state, action.caseId)

    case 'ADVANCE_JOURNEY': {
      const journey = buildPatientJourney(
        state.workflowScenarios,
        state.selectedJourneyPatientId,
      )
      if (journey.current) {
        return resolveScenarioCaseAndAdvance(state, journey.current.caseId)
      }
      const focusStep = journey.steps[journey.steps.length - 1]
      if (!focusStep) return state
      return focusJourneyStep(state, focusStep.caseId)
    }

    case 'RESTART_JOURNEY': {
      const patientId = state.selectedJourneyPatientId
      const patient = getJourneyPatient(patientId)
      if (!patient) return state
      const beforeMinutes = sumCompletedJourneyCaseMinutes(state.workflowScenarios, patientId)
      const workflowScenarios = reopenJourneyCases(state.workflowScenarios, patientId)
      const afterMinutes = sumCompletedJourneyCaseMinutes(workflowScenarios, patientId)
      const refund = Math.max(0, beforeMinutes - afterMinutes)
      return focusPatientCurrentStep(
        {
          ...state,
          workflowScenarios,
          scenarioMinutesReturned: Math.max(0, state.scenarioMinutesReturned - refund),
        },
        patientId,
      )
    }

    case 'SELECT_PROVIDER':
      if (state.providerConfirmed[action.patientId]) return state
      if (state.providerTerritoryResolutions[action.patientId] === 'discharged') {
        return state
      }
      return {
        ...state,
        providerSelectedIds: {
          ...state.providerSelectedIds,
          [action.patientId]: action.providerId,
        },
      }

    case 'CONFIRM_PROVIDER_SELECTION': {
      if (state.providerConfirmed[action.patientId]) return state
      if (state.providerTerritoryResolutions[action.patientId] === 'discharged') {
        return state
      }
      return {
        ...state,
        providerConfirmed: {
          ...state.providerConfirmed,
          [action.patientId]: true,
        },
        latestProviderAvailabilityPatientId: action.patientId,
        providerAvailability: {
          ...state.providerAvailability,
          [action.patientId]: {
            requestedAt: action.requestedAt,
            deadlineAt: action.deadlineAt,
            outcome: 'waiting',
          },
        },
        providerAvailabilityUnread: true,
        actionTimers: startActionTimer(
          resolveActionTimer(
            resolveActionTimer(
              state.actionTimers,
              action.patientId,
              'confirm-provider',
              Date.now(),
            ),
            action.patientId,
            'use-fallback-provider',
            Date.now(),
          ),
          {
            patientId: action.patientId,
            patientName: timerPatientName(
              state.actionTimers,
              action.patientId,
              action.patientId,
            ),
            actionId: 'provider-availability',
            now: Date.now(),
          },
        ),
      }
    }

    case 'RESOLVE_PROVIDER_TERRITORY': {
      if (state.providerTerritoryResolutions[action.patientId]) return state
      if (action.resolution === 'discharged') {
        return {
          ...state,
          providerTerritoryResolutions: {
            ...state.providerTerritoryResolutions,
            [action.patientId]: 'discharged',
          },
          actionTimers: resolveActionTimer(
            resolveActionTimer(
              state.actionTimers,
              action.patientId,
              'confirm-provider',
              Date.now(),
            ),
            action.patientId,
            'use-fallback-provider',
            Date.now(),
          ),
        }
      }
      if (!action.requestedAt || !action.deadlineAt) return state
      return {
        ...state,
        providerTerritoryResolutions: {
          ...state.providerTerritoryResolutions,
          [action.patientId]: 'assigned',
        },
        providerConfirmed: {
          ...state.providerConfirmed,
          [action.patientId]: true,
        },
        latestProviderAvailabilityPatientId: action.patientId,
        providerAvailability: {
          ...state.providerAvailability,
          [action.patientId]: {
            requestedAt: action.requestedAt,
            deadlineAt: action.deadlineAt,
            outcome: 'waiting',
          },
        },
        providerAvailabilityUnread: true,
        actionTimers: startActionTimer(
          resolveActionTimer(
            resolveActionTimer(
              state.actionTimers,
              action.patientId,
              'confirm-provider',
              Date.now(),
            ),
            action.patientId,
            'use-fallback-provider',
            Date.now(),
          ),
          {
            patientId: action.patientId,
            patientName: timerPatientName(
              state.actionTimers,
              action.patientId,
              action.patientId,
            ),
            actionId: 'provider-availability',
            now: Date.now(),
          },
        ),
      }
    }

    case 'CONFIRM_PROVIDER_AVAILABILITY': {
      const request = state.providerAvailability[action.patientId]
      if (!request || request.outcome !== 'waiting') return state
      return withSchedulingHandoff(state, request, {
        patientId: action.patientId,
        patientName: action.patientName,
        provider: action.provider,
        route: 'provider_confirmed',
        readyAt: action.resolvedAt,
        outcome: 'confirmed',
        resolvedAt: action.resolvedAt,
      })
    }

    case 'TIMEOUT_PROVIDER_AVAILABILITY': {
      const request = state.providerAvailability[action.patientId]
      if (!request || request.outcome !== 'waiting') return state
      return {
        ...state,
        providerAvailability: {
          ...state.providerAvailability,
          [action.patientId]: {
            ...request,
            outcome: 'timeout',
            resolvedAt: action.resolvedAt,
          },
        },
        actionTimers: startActionTimer(
          resolveActionTimer(
            state.actionTimers,
            action.patientId,
            'provider-availability',
            Date.now(),
          ),
          {
            patientId: action.patientId,
            patientName: timerPatientName(
              state.actionTimers,
              action.patientId,
              action.patientId,
            ),
            actionId: 'manual-placement',
            now: Date.now(),
          },
        ),
      }
    }

    case 'COMPLETE_MANUAL_PLACEMENT': {
      const request = state.providerAvailability[action.patientId]
      if (!request || request.outcome !== 'timeout') return state
      return withSchedulingHandoff(state, request, {
        patientId: action.patientId,
        patientName: action.patientName,
        provider: action.provider,
        route: 'manual_placement',
        readyAt: action.readyAt,
        outcome: 'placement_completed',
        resolvedAt: action.readyAt,
      })
    }

    case 'MARK_PROVIDER_RECORDS_READ': {
      if (!state.providerRecordsMessageUnread && !state.providerRecordsUnread) {
        return state
      }
      return {
        ...state,
        providerRecordsUnread: false,
        providerRecordsMessageUnread: false,
        schedulingHandoffUnread: true,
        schedulingHandoffMessageUnread: true,
      }
    }

    case 'MARK_SCHEDULING_HANDOFF_READ':
      if (!state.schedulingHandoffMessageUnread) return state
      return {
        ...state,
        schedulingHandoffMessageUnread: false,
      }

    case 'SELECT_SCHEDULING_SLOT': {
      const record = state.patientSchedules[action.patientId]
      const slot = record?.slots.find((item) => item.id === action.slotId)
      if (
        !record ||
        record.status !== 'waiting' ||
        !slot ||
        slot.status !== 'open' ||
        record.selectedSlotId === action.slotId
      ) {
        return state
      }
      return {
        ...state,
        patientSchedules: {
          ...state.patientSchedules,
          [action.patientId]: { ...record, selectedSlotId: action.slotId },
        },
      }
    }

    case 'COMPLETE_PATIENT_SCHEDULE': {
      const record = state.patientSchedules[action.patientId]
      const slot = record ? selectedSlot(record) : null
      if (
        !record ||
        record.status !== 'waiting' ||
        !slot ||
        slot.status !== 'open'
      ) {
        return state
      }
      return {
        ...state,
        patientSchedules: {
          ...state.patientSchedules,
          [action.patientId]: {
            ...record,
            status: 'scheduled',
            appointmentDate: slot.appointmentDate,
            appointmentTime: slot.appointmentTime,
            scheduledAt: action.scheduledAt,
          },
        },
        actionTimers: resolveActionTimer(
          state.actionTimers,
          action.patientId,
          'schedule-patient',
          Date.now(),
        ),
      }
    }

    case 'RECORD_SCHEDULING_BLOCKER': {
      const record = state.patientSchedules[action.patientId]
      if (!record || record.status !== 'waiting') return state
      return {
        ...state,
        patientSchedules: {
          ...state.patientSchedules,
          [action.patientId]: {
            ...record,
            status: 'blocked',
            selectedSlotId: null,
            blockerReason: action.reason,
            scheduledAt: action.occurredAt,
          },
        },
        actionTimers: resolveActionTimer(
          state.actionTimers,
          action.patientId,
          'schedule-patient',
          Date.now(),
        ),
      }
    }

    case 'CONFIRM_ASSIGNMENT_HANDOFF':
      return {
        ...state,
        latestAssignmentHandoff: {
          patientId: action.patientId,
          patientName: action.patientName,
          occurredAt: action.occurredAt,
        },
        assignmentNotifyUnread: true,
        handoffNavUnread: true,
        handoffNotifyUnread: true,
        handoffMondayUnread: true,
        handoffDrkUnread: true,
        providerNavUnread: true,
        providerSelectUnread: true,
        actionTimers: startActionTimer(
          resolveActionTimer(
            state.actionTimers,
            action.patientId,
            'confirm-assignment',
            Date.now(),
          ),
          {
            patientId: action.patientId,
            patientName: action.patientName,
            actionId: 'confirm-provider',
            now: Date.now(),
          },
        ),
      }

    case 'MARK_ASSIGNMENT_NOTIFY_READ':
      if (!state.assignmentNotifyUnread) return state
      return { ...state, assignmentNotifyUnread: false }

    case 'MARK_HANDOFF_STEP_READ': {
      if (action.stepId === 'notify-referral-source') {
        if (!state.handoffNotifyUnread) return state
        return { ...state, handoffNotifyUnread: false }
      }
      if (action.stepId === 'create-monday-record') {
        if (!state.handoffMondayUnread) return state
        return { ...state, handoffMondayUnread: false }
      }
      if (!state.handoffDrkUnread) return state
      return { ...state, handoffDrkUnread: false }
    }

    case 'MARK_PROVIDER_SELECT_READ':
      if (!state.providerSelectUnread) return state
      return { ...state, providerSelectUnread: false }

    case 'MARK_PROVIDER_AVAILABILITY_READ':
      if (!state.providerAvailabilityUnread) return state
      return { ...state, providerAvailabilityUnread: false }

    case 'CONFIRM_EOD_FOLLOW_UP':
      return {
        ...state,
        latestEodFollowUpPatientId: action.patientId,
        eodFollowUpUnread: true,
        actionTimers: resolveActionTimer(
          state.actionTimers,
          action.patientId,
          'eod-follow-up-cm',
          Date.now(),
        ),
      }

    case 'MARK_EOD_FOLLOW_UP_READ':
      if (!state.eodFollowUpUnread) return state
      return { ...state, eodFollowUpUnread: false }

    case 'CONFIRM_EOD_ESCALATION':
      return {
        ...state,
        latestEodEscalationPatientId: action.patientId,
        eodEscalationUnread: true,
        actionTimers: resolveActionTimer(
          resolveActionTimer(
            state.actionTimers,
            action.patientId,
            'eod-escalate',
            Date.now(),
          ),
          action.patientId,
          'eod-follow-up-cm',
          Date.now(),
        ),
      }

    case 'MARK_EOD_ESCALATION_READ':
      if (!state.eodEscalationUnread) return state
      return { ...state, eodEscalationUnread: false }

    case 'EDIT_INTAKE_FIELD': {
      if (state.intakeVerified[action.patientId]) return state
      const current = state.intakeFieldEdits[action.patientId] ?? {}
      if (current[action.key] === action.value) return state
      return {
        ...state,
        intakeFieldEdits: {
          ...state.intakeFieldEdits,
          [action.patientId]: {
            ...current,
            [action.key]: action.value,
          },
        },
      }
    }

    case 'REPLACE_INTAKE_SECTION_ROWS': {
      if (state.intakeVerified[action.patientId]) return state
      const current = state.intakeSectionRows[action.patientId] ?? {}
      const previous = current[action.sectionId]
      if (
        previous &&
        previous.length === action.rows.length &&
        previous.every(
          (row, index) =>
            row.label === action.rows[index]?.label &&
            row.value === action.rows[index]?.value &&
            row.rowId === action.rows[index]?.rowId,
        )
      ) {
        return state
      }
      return {
        ...state,
        intakeSectionRows: {
          ...state.intakeSectionRows,
          [action.patientId]: {
            ...current,
            [action.sectionId]: action.rows,
          },
        },
      }
    }

    case 'CONFIRM_INTAKE_REVIEW': {
      if (state.intakeVerified[action.patientId]) return state
      const alreadyAnnounced =
        state.latestIntakeReview?.patientId === action.patientId
      return {
        ...state,
        intakeVerified: {
          ...state.intakeVerified,
          [action.patientId]: true,
        },
        latestIntakeReview: {
          patientId: action.patientId,
          patientName: action.patientName,
          occurredAt: action.occurredAt,
        },
        intakeMondayUnread: alreadyAnnounced
          ? state.intakeMondayUnread
          : true,
        intakeDrkUnread: alreadyAnnounced ? state.intakeDrkUnread : true,
        intakePartnerUnread: alreadyAnnounced
          ? state.intakePartnerUnread
          : true,
        actionTimers: resolveActionTimer(
          state.actionTimers,
          action.patientId,
          'confirm-intake-review',
          Date.now(),
        ),
      }
    }

    case 'REOPEN_INTAKE_REVIEW':
      if (!state.intakeVerified[action.patientId]) return state
      return {
        ...state,
        intakeVerified: {
          ...state.intakeVerified,
          [action.patientId]: false,
        },
        actionTimers: startActionTimer(state.actionTimers, {
          patientId: action.patientId,
          patientName: timerPatientName(
            state.actionTimers,
            action.patientId,
            action.patientId,
          ),
          actionId: 'confirm-intake-review',
          now: Date.now(),
        }),
      }

    case 'CONFIRM_PARTNER_CONTACTED':
      return {
        ...state,
        latestPartnerContact: {
          patientId: action.patientId,
          patientName: action.patientName,
          occurredAt: action.occurredAt,
        },
        assignmentOwnerUnread: true,
        actionTimers: startActionTimer(
          resolveActionTimer(
            state.actionTimers,
            action.patientId,
            'confirm-partner-contacted',
            Date.now(),
          ),
          {
            patientId: action.patientId,
            patientName: action.patientName,
            actionId: 'confirm-assignment',
            now: Date.now(),
          },
        ),
      }

    case 'MARK_ASSIGNMENT_OWNER_READ':
      if (!state.assignmentOwnerUnread) return state
      return { ...state, assignmentOwnerUnread: false }

    case 'MARK_INTAKE_STEP_READ':
      if (action.stepId === 'check-monday') {
        if (!state.intakeMondayUnread) return state
        return { ...state, intakeMondayUnread: false }
      }
      if (action.stepId === 'check-drk') {
        if (!state.intakeDrkUnread) return state
        return { ...state, intakeDrkUnread: false }
      }
      if (!state.intakePartnerUnread) return state
      return { ...state, intakePartnerUnread: false }

    case 'UPDATE_IMPACT_ASSUMPTIONS':
      return {
        ...state,
        impactAssumptions: { ...state.impactAssumptions, ...action.patch },
      }

    case 'PREPARE_FOLLOW_UP': {
      const referrals = state.referrals.map((referral) => {
        if (referral.id !== action.id) return referral
        if (
          referral.outcome !== 'needs_information' &&
          referral.outcome !== 'needs_clarification'
        ) {
          return referral
        }
        const owner =
          referral.outcome === 'needs_information' ? 'Assigned marketer' : 'Intake team'
        const message =
          referral.outcome === 'needs_information'
            ? `Hello — we received the referral for ${referral.patientName}. Please confirm insurance information so intake can proceed.`
            : `Hello — we received the referral for ${referral.patientName}. Please confirm the correct contact number; two conflicting values were found.`
        return pushEvent(
          {
            ...referral,
            followUpPrepared: true,
            followUpOwner: owner,
            followUpMessage: message,
            stage: 'reviewed',
          },
          {
            timestamp: '10:31 AM',
            label: 'Follow-up prepared',
            result: `Assigned to ${owner}`,
            actor: 'Intake automation',
            humanRequired: true,
          },
        )
      })
      return { ...state, referrals }
    }

    case 'RESOLVE_DUPLICATE': {
      const referrals = state.referrals.map((referral) => {
        if (referral.id !== action.id) return referral
        if (referral.duplicateStatus !== 'probable_duplicate') return referral
        if (action.decision === 'keep_blocked') {
          return pushEvent(referral, {
            timestamp: '10:32 AM',
            label: 'Duplicate kept blocked',
            result: 'Creation remains blocked pending further review',
            actor: 'Intake team',
            humanRequired: true,
          })
        }
        return pushEvent(
          {
            ...referral,
            duplicateStatus: 'resolved_different',
            outcome: 'ready',
            mondayPreview: { ...referral.mondayPreview, blockers: [] },
            mondayStatus: 'ready',
            drkStatus: 'draft_ready',
            nextAction: 'Ready for human confirmation',
          },
          {
            timestamp: '10:32 AM',
            label: 'Duplicate resolved as different patient',
            result: 'Destination actions unlocked for confirmation',
            actor: 'Intake team',
            humanRequired: true,
          },
        )
      })
      return { ...state, referrals }
    }

    case 'CONFIRM_REFERRAL': {
      const referrals = state.referrals.map((referral) => {
        if (referral.id !== action.id) return referral
        if (!referral.processed) return referral
        if (referral.confirmed) return referral
        if (referral.duplicateStatus === 'probable_duplicate') return referral
        if (referral.outcome === 'needs_information' || referral.outcome === 'needs_clarification') {
          return referral
        }
        if (referral.outcome !== 'ready' && referral.duplicateStatus !== 'resolved_different') {
          return referral
        }
        return pushEvent(
          {
            ...referral,
            confirmed: true,
            stage: 'confirmed',
            mondayStatus: 'ready',
            drkStatus: 'draft_ready',
          },
          {
            timestamp: '10:35 AM',
            label: 'Confirmation received',
            result: 'Authorized sender and thread validated',
            actor: 'Original referral sender',
            humanRequired: true,
          },
        )
      })
      return { ...state, referrals }
    }

    case 'REQUEST_CORRECTION': {
      const referrals = state.referrals.map((referral) => {
        if (referral.id !== action.id) return referral
        return pushEvent(referral, {
          timestamp: '10:36 AM',
          label: 'Correction requested',
          result: 'Referral remains under human review',
          actor: 'Reviewer',
          humanRequired: true,
        })
      })
      return { ...state, referrals }
    }

    case 'SEND_TO_MONDAY': {
      const referrals = state.referrals.map((referral) => {
        if (referral.id !== action.id) return referral
        if (!referral.confirmed) return referral
        if (referral.duplicateStatus === 'probable_duplicate') return referral
        if (referral.mondayStatus === 'created' || referral.mondayStatus === 'creating') {
          return referral
        }
        if (referral.mondayPreview.blockers.length > 0) return referral
        return {
          ...referral,
          mondayStatus: 'creating' as const,
        }
      })
      return { ...state, referrals }
    }

    case 'MONDAY_CREATED': {
      const referrals = state.referrals.map((referral) => {
        if (referral.id !== action.id) return referral
        if (referral.mondayStatus !== 'creating') return referral
        return pushEvent(
          {
            ...referral,
            mondayStatus: 'created',
            stage: 'monday_ready',
            mondayPreview: {
              ...referral.mondayPreview,
              itemId: action.itemId,
              demoUrl: `https://wcw-demo.monday.example/boards/18422325133/pulses/${action.itemId}`,
            },
          },
          {
            timestamp: '10:37 AM',
            label: 'Monday.com record created',
            result: `Item ${action.itemId} created once`,
            actor: 'Guarded Monday create',
            humanRequired: false,
          },
        )
      })
      return { ...state, referrals }
    }

    case 'MARK_DRK_ASSISTED': {
      const referrals = state.referrals.map((referral) => {
        if (referral.id !== action.id) return referral
        if (!referral.confirmed) return referral
        return pushEvent(
          {
            ...referral,
            drkStatus: 'assisted_entry',
            stage: referral.mondayStatus === 'created' ? 'drk_ready' : referral.stage,
          },
          {
            timestamp: '10:38 AM',
            label: 'DRK assisted entry opened',
            result: 'DRK chart ready · Create Patient remains human-controlled',
            actor: 'Face-sheet workflow',
            humanRequired: true,
          },
        )
      })
      return { ...state, referrals }
    }

    case 'MARK_DRK_FACE_SHEET': {
      const referrals = state.referrals.map((referral) => {
        if (referral.id !== action.id) return referral
        if (!referral.confirmed) return referral
        return pushEvent(
          {
            ...referral,
            drkStatus: 'face_sheet_ready',
            stage: 'drk_ready',
          },
          {
            timestamp: '10:39 AM',
            label: 'Marked ready for face-sheet team',
            result: 'DRK chart ready for human-controlled entry',
            actor: 'Intake team',
            humanRequired: true,
          },
        )
      })
      return { ...state, referrals }
    }

    case 'SET_LIFECYCLE_STAGE':
      return {
        ...state,
        lifecycleStageId: action.stageId,
        lifecycleRunning: false,
        lifecycleMessage: null,
      }

    case 'START_LIFECYCLE_STAGE':
      if (state.lifecycleRunning) return state
      return {
        ...state,
        lifecycleRunning: true,
        lifecycleMessage: `Running ${
          LIFECYCLE_STAGES.find((stage) => stage.id === state.lifecycleStageId)?.label ??
          'lifecycle stage'
        }…`,
      }

    case 'COMPLETE_LIFECYCLE_STAGE': {
      const stage = LIFECYCLE_STAGES.find((item) => item.id === state.lifecycleStageId)
      let gained = 0
      const lifecycleCases = state.lifecycleCases.map((item) => {
        if (item.stageId !== state.lifecycleStageId) return item
        if (item.status === 'completed' || item.status === 'escalated') return item
        gained += item.minutesReturned
        return {
          ...item,
          status:
            item.stageId === 'end_of_day' || item.stageId === 'not_seen' || item.stageId === 'qa_discharge'
              ? ('escalated' as const)
              : ('completed' as const),
          summary: item.resultLabel,
        }
      })
      const activityText = stage
        ? `${stage.runLabel} · ${gained} min returned`
        : 'Lifecycle stage complete'
      return {
        ...state,
        lifecycleRunning: false,
        lifecycleCases,
        lifecycleMinutesReturned: state.lifecycleMinutesReturned + gained,
        lifecycleMessage: stage
          ? `${stage.afterVerb[0].toUpperCase()}${stage.afterVerb.slice(1)} for this stage. ${gained} minutes returned.`
          : 'Lifecycle stage complete.',
        activityFeed: [
          {
            id: `activity-life-${Date.now()}`,
            time: 'Now',
            text: activityText,
          },
          ...state.activityFeed,
        ].slice(0, 8),
      }
    }

    case 'RESOLVE_LIFECYCLE_CASE': {
      let gained = 0
      const lifecycleCases = state.lifecycleCases.map((item) => {
        if (item.id !== action.id) return item
        if (item.status === 'completed' || item.status === 'escalated') return item
        gained = item.minutesReturned
        return {
          ...item,
          status:
            item.stageId === 'end_of_day' || item.stageId === 'not_seen' || item.stageId === 'qa_discharge'
              ? ('escalated' as const)
              : ('completed' as const),
          summary: item.resultLabel,
        }
      })
      return {
        ...state,
        lifecycleCases,
        lifecycleMinutesReturned: state.lifecycleMinutesReturned + gained,
        lifecycleMessage: gained
          ? `Case updated · ${gained} minutes returned`
          : state.lifecycleMessage,
      }
    }

    case 'START_ACTION_TIMER':
      return {
        ...state,
        actionTimers: startActionTimer(state.actionTimers, {
          patientId: action.patientId,
          patientName: action.patientName,
          actionId: action.actionId,
          now: action.now ?? Date.now(),
        }),
      }

    case 'TICK_ACTION_TIMERS': {
      const nextTimers = tickActionTimers(state.actionTimers, action.now)
      if (!nextTimers) return state
      return { ...state, actionTimers: nextTimers }
    }

    case 'RESOLVE_ACTION_TIMER':
      return {
        ...state,
        actionTimers: resolveActionTimer(
          state.actionTimers,
          action.patientId,
          action.actionId,
          action.now ?? Date.now(),
        ),
      }

    default:
      return state
  }
}

export function getAutomationStepIndex(step: AutomationStep): number {
  if (step === 'idle') return -1
  return AUTOMATION_STEPS.findIndex((item) => item.id === step)
}

export function filterReferrals(state: DemoState): ReferralRecord[] {
  return state.referrals.filter((referral) => {
    if (state.spineFilter !== 'all' && referral.stage !== state.spineFilter) return false
    switch (state.queueFilter) {
      case 'ready':
        return (
          referral.processed &&
          (referral.outcome === 'ready' || referral.duplicateStatus === 'resolved_different') &&
          !referral.confirmed
        )
      case 'needs_information':
        return (
          referral.outcome === 'needs_information' || referral.outcome === 'needs_clarification'
        )
      case 'possible_duplicate':
        return (
          referral.duplicateStatus === 'probable_duplicate' ||
          referral.outcome === 'blocked_duplicate'
        )
      case 'confirmed':
        return referral.confirmed
      default:
        return true
    }
  })
}
