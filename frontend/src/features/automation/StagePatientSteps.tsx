import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, Search } from 'lucide-react'
import { useEscapeDismiss } from '../../hooks/useEscapeDismiss'
import { useDemo } from '../../state/useDemo'
import { MicrostepList } from './MicrostepList'
import { StageFeedMessage } from './StageFeedMessage'
import { overlayIntakeDetail } from './overlayIntakeDetail'
import { detailForPatientStep, feedForStep, parseOpsDate, patientsForStage } from './ops'
import type { StepFeedDay, StepFeedRow } from './ops/types'
import {
  CASE_MANAGER_OPTIONS,
  caseManagerNotification,
  caseManagerSuggestion,
  drkDraftForPatient,
  drkDraftWithAssignedProvider,
  mondayRecordForPatient,
  mondayRecordWithAssignedProvider,
} from './fixtures/caseManagerAssignments'
import {
  eodSchedulingCheckForPatient,
  eodSchedulingCheckSummary,
  eodSchedulingCheckDisplaySummary,
  eodCmFollowUpSummary,
  eodEscalationEligible,
  eodEscalationSummary,
  eodEscalationConfirmLabel,
  eodCmNotifyPending,
  eodSchedulingBucket,
  eodFollowUpEligible,
} from './fixtures/eodSchedulingCheck'
import {
  weeklyVisitCheckForPatient,
  weeklyVisitCheckSummary,
  weeklyPatientSeenEligible,
  weeklyWoundHealedEligible,
  weeklyPatientExpiredEligible,
  weeklyPatientOnHoldEligible,
  weeklyMissedVisitSummary,
  weeklyHoldsClosuresSummary,
  weeklyHoldsActionComplete,
  weeklyDischargeReviewDue,
  weeklyMissedVisitPending,
} from './fixtures/weeklyVisitCheck'
import { intakeDemoPatient, referralPdfForPatient } from './fixtures/intakeDemoPatients'
import {
  PROVIDER_OPTIONS,
  providerPatientLocationDisplay,
  providerSuggestion,
  providersForPatientLocation,
} from './fixtures/providerAssignments'
import { mergeLiveInboxFeed, isLiveInboxRow } from './liveInbox/feed'
import { LiveInboxStatus } from './liveInbox/LiveInboxStatus'
import { useLiveInbox } from './liveInbox/useLiveInbox'
import { mergeWorkflowFeed, isLiveWorkflowRow } from './liveWorkflow/feed'
import { useWorkflowExecution } from './liveWorkflow/useWorkflowExecution'
import type { FlowOpsPageId } from '../../data/flowOps'
import type { PatientStepStatus } from './ops/types'
import type { AutomationMicrostep } from './types'
import './StageOps.css'

type StatusFilterOption = {
  id: string
  meaning: string
  tone?: PatientStepStatus
}

const STATUS_FILTERS: StatusFilterOption[] = [
  { id: 'waiting', meaning: 'Needs confirmation' },
  { id: 'blocked', meaning: 'Stuck' },
  { id: 'current', meaning: 'In progress' },
  { id: 'done', meaning: 'Finished' },
]

const DEFAULT_STATUSES: PatientStepStatus[] = STATUS_FILTERS.map(
  (item) => item.id as PatientStepStatus,
)

type StatusFilterValue = 'all' | string

const EOD_SCHEDULING_FILTERS: StatusFilterOption[] = [
  { id: 'scheduled', meaning: 'Scheduled', tone: 'done' },
  {
    id: 'unscheduled-over-48',
    meaning: 'Not scheduled after 48h',
    tone: 'blocked',
  },
  {
    id: 'unscheduled-under-48',
    meaning: 'Not scheduled less than 48h',
    tone: 'waiting',
  },
]
type StepDetail = ReturnType<typeof detailForPatientStep>

const WEEKLY_QUESTION_STEPS = [
  'patient-seen',
  'wound-healed',
  'patient-expired',
  'patient-on-hold',
] as const

function isWeeklyQuestionStep(
  stepId: string,
): stepId is (typeof WEEKLY_QUESTION_STEPS)[number] {
  return WEEKLY_QUESTION_STEPS.includes(
    stepId as (typeof WEEKLY_QUESTION_STEPS)[number],
  )
}

function weeklyStatusFilters(stepId: string): StatusFilterOption[] | null {
  if (stepId === 'patient-seen') {
    return [
      { id: 'done', meaning: 'Seen' },
      { id: 'waiting', meaning: 'Not seen' },
    ]
  }
  if (stepId === 'wound-healed') {
    return [
      { id: 'done', meaning: 'Healed' },
      { id: 'waiting', meaning: 'Not healed' },
    ]
  }
  if (stepId === 'patient-expired') {
    return [
      { id: 'done', meaning: 'Expired' },
      { id: 'waiting', meaning: 'Not expired' },
    ]
  }
  if (stepId === 'patient-on-hold') {
    return [
      { id: 'done', meaning: 'Hold' },
      { id: 'waiting', meaning: 'Not hold' },
    ]
  }
  return null
}

function stepStatusFilters(stepId: string): StatusFilterOption[] {
  return (
    weeklyStatusFilters(stepId) ??
    (stepId === 'check-scheduling-status' ? EOD_SCHEDULING_FILTERS : STATUS_FILTERS)
  )
}

function statusFilterTone(option: StatusFilterOption): string {
  return option.tone ?? option.id
}

function eodSchedulingStatusOption(patientId: string): StatusFilterOption {
  const bucket = eodSchedulingBucket(eodSchedulingCheckForPatient(patientId))
  return (
    EOD_SCHEDULING_FILTERS.find((item) => item.id === bucket) ??
    EOD_SCHEDULING_FILTERS[0]
  )
}

function usesCustomStatusFilter(stepId: string): boolean {
  return isWeeklyQuestionStep(stepId) || stepId === 'check-scheduling-status'
}

function weeklyStatusLabel(
  stepId: string,
  status: PatientStepStatus | string,
): string | null {
  return (
    weeklyStatusFilters(stepId)?.find((item) => item.id === status)?.meaning ??
    null
  )
}

const ASSIGNMENT_HANDOFF_STEP_IDS = [
  'notify-referral-source',
  'create-monday-record',
  'create-update-drk',
] as const

type AssignmentHandoffStepId = (typeof ASSIGNMENT_HANDOFF_STEP_IDS)[number]

function isAssignmentHandoffStep(
  stepId: string,
): stepId is AssignmentHandoffStepId {
  return ASSIGNMENT_HANDOFF_STEP_IDS.includes(stepId as AssignmentHandoffStepId)
}

function assignmentHandoffUnreadForStep(
  state: {
    handoffNotifyUnread: boolean
    handoffMondayUnread: boolean
    handoffDrkUnread: boolean
  },
  stepId: string,
): boolean {
  if (stepId === 'notify-referral-source') return state.handoffNotifyUnread
  if (stepId === 'create-monday-record') return state.handoffMondayUnread
  if (stepId === 'create-update-drk') return state.handoffDrkUnread
  return false
}

const INTAKE_FOLLOW_UP_STEP_IDS = [
  'check-monday',
  'check-drk',
  'confirm-referral-contacted',
] as const

type IntakeFollowUpStepId = (typeof INTAKE_FOLLOW_UP_STEP_IDS)[number]

function isIntakeFollowUpStep(
  stepId: string,
): stepId is IntakeFollowUpStepId {
  return INTAKE_FOLLOW_UP_STEP_IDS.includes(stepId as IntakeFollowUpStepId)
}

function intakeFollowUpUnreadForStep(
  state: {
    intakeMondayUnread: boolean
    intakeDrkUnread: boolean
    intakePartnerUnread: boolean
  },
  stepId: string,
): boolean {
  if (stepId === 'check-monday') return state.intakeMondayUnread
  if (stepId === 'check-drk') return state.intakeDrkUnread
  if (stepId === 'confirm-referral-contacted') return state.intakePartnerUnread
  return false
}

function intakeFollowUpSummary(
  patientId: string,
  stepId: IntakeFollowUpStepId,
): string {
  return (
    intakeDemoPatient(patientId)?.snapshots[stepId]?.output ??
    (stepId === 'check-monday'
      ? 'No matching Monday.com candidate found'
      : stepId === 'check-drk'
        ? 'No exact DRK chart match found'
        : 'Awaiting partner confirmation')
  )
}

function opsTimestamp(date = new Date()) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
}

function prependEodFeedRows(days: StepFeedDay[], rows: StepFeedRow[]): StepFeedDay[] {
  if (!rows.length) return days

  const existing = new Set(days.flatMap((day) => day.rows.map((row) => row.patientId)))
  const injected = rows.filter((row) => !existing.has(row.patientId))
  if (!injected.length) return days

  return [
    {
      key: `eod-injected-${injected[0].stepId}`,
      label: 'Today',
      month: '—',
      day: '—',
      rows: injected,
    },
    ...days,
  ]
}

function shiftedOpsTimestamp(timestamp: string, minutes: number) {
  const parsed = parseOpsDate(timestamp)
  if (!parsed) return timestamp
  return opsTimestamp(new Date(parsed.timeMs + minutes * 60 * 1000))
}

function availabilityRequestTimes(requestedAt = new Date()) {
  return {
    requestedAt: opsTimestamp(requestedAt),
    deadlineAt: opsTimestamp(new Date(requestedAt.getTime() + 60 * 60 * 1000)),
  }
}

export function StagePatientSteps({
  stageId,
  microsteps,
}: {
  stageId: FlowOpsPageId
  microsteps: AutomationMicrostep[]
}) {
  const { state, dispatch } = useDemo()
  const [selectedStepId, setSelectedStepId] = useState(microsteps[0]?.id ?? '')
  const [patientQuery, setPatientQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilterValue>('all')
  const [statusMenuOpen, setStatusMenuOpen] = useState(false)
  const [partnerConfirmed, setPartnerConfirmed] = useState<Record<string, boolean>>(
    {},
  )
  const [selectedCaseManagers, setSelectedCaseManagers] = useState<
    Record<string, string>
  >({})
  const [confirmedAssignments, setConfirmedAssignments] = useState<
    Record<string, boolean>
  >({})
  const [workflowActionError, setWorkflowActionError] = useState<string | null>(null)
  const [showUnreadAssignmentMessage, setShowUnreadAssignmentMessage] =
    useState(false)
  const [showUnreadProviderMessage, setShowUnreadProviderMessage] =
    useState(false)
  const [showUnreadHandoffMessage, setShowUnreadHandoffMessage] =
    useState(false)
  const [showUnreadProviderRecordsMessage, setShowUnreadProviderRecordsMessage] =
    useState(false)
  const [showUnreadAssignmentHandoff, setShowUnreadAssignmentHandoff] =
    useState(false)
  const [showUnreadProviderSelect, setShowUnreadProviderSelect] =
    useState(false)
  const [showUnreadIntakeDuplicate, setShowUnreadIntakeDuplicate] =
    useState(false)
  const [eodEscalated, setEodEscalated] = useState<Record<string, boolean>>({})
  const [eodManualCmFollowUp, setEodManualCmFollowUp] = useState<
    Record<string, boolean>
  >({})
  const [showUnreadEodFollowUpMessage, setShowUnreadEodFollowUpMessage] =
    useState(false)
  const [showUnreadEodEscalationMessage, setShowUnreadEodEscalationMessage] =
    useState(false)
  const [weeklyRescheduleConfirmed, setWeeklyRescheduleConfirmed] = useState<
    Record<string, boolean>
  >({})
  const [weeklyDischargeReview, setWeeklyDischargeReview] = useState<
    Record<string, boolean>
  >({})
  const [weeklyHoldsActionTaken, setWeeklyHoldsActionTaken] = useState<
    Record<string, boolean>
  >({})
  const [weeklyAppointmentRescheduled, setWeeklyAppointmentRescheduled] =
    useState<Record<string, boolean>>({})
  const statusMenuRef = useRef<HTMLDivElement>(null)
  const liveInbox = useLiveInbox(stageId === 'intake')
  const liveWorkflow = useWorkflowExecution(
    stageId === 'assignment' || stageId === 'handoff',
  )

  useEffect(() => {
    setSelectedStepId(microsteps[0]?.id ?? '')
    setPatientQuery('')
    setStatusFilter('all')
    setStatusMenuOpen(false)
    setPartnerConfirmed({})
    setSelectedCaseManagers({})
    setConfirmedAssignments({})
    setWorkflowActionError(null)
    setShowUnreadAssignmentMessage(false)
    setShowUnreadProviderMessage(false)
    setShowUnreadHandoffMessage(false)
    setShowUnreadProviderRecordsMessage(false)
    setShowUnreadAssignmentHandoff(false)
    setShowUnreadProviderSelect(false)
    setShowUnreadIntakeDuplicate(false)
    setEodEscalated({})
    setEodManualCmFollowUp({})
    setShowUnreadEodFollowUpMessage(false)
    setShowUnreadEodEscalationMessage(false)
    setWeeklyRescheduleConfirmed({})
    setWeeklyDischargeReview({})
    setWeeklyHoldsActionTaken({})
    setWeeklyAppointmentRescheduled({})
  }, [stageId, microsteps[0]?.id])

  useEffect(() => {
    if (!statusMenuOpen) return
    const onPointerDown = (event: MouseEvent) => {
      if (
        statusMenuRef.current &&
        !statusMenuRef.current.contains(event.target as Node)
      ) {
        setStatusMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [statusMenuOpen])

  useEscapeDismiss(statusMenuOpen, () => setStatusMenuOpen(false))

  const selectedStep =
    microsteps.find((step) => step.id === selectedStepId) ?? microsteps[0]

  const statusFilters = stepStatusFilters(selectedStepId)
  const activeStatusFilter =
    statusFilter === 'all' ||
    statusFilters.some((item) => item.id === statusFilter)
      ? statusFilter
      : 'all'

  const statuses =
    usesCustomStatusFilter(selectedStepId) || activeStatusFilter === 'all'
      ? DEFAULT_STATUSES
      : [activeStatusFilter as PatientStepStatus]

  const selectedStatusOption =
    activeStatusFilter === 'all'
      ? null
      : statusFilters.find((item) => item.id === activeStatusFilter) ?? null

  const days = useMemo(() => {
    const demoDays = selectedStepId
      ? feedForStep(stageId, selectedStepId, { patientQuery, statuses })
      : []
    if (stageId === 'intake') {
      return mergeLiveInboxFeed({
        demoDays,
        referrals: liveInbox.referrals,
        drkDuplicateCheckEnabled:
          liveInbox.monitor?.safety.drk_duplicate_check,
        patientQuery,
        statuses,
        selectedStepId,
      })
    }
    if (stageId === 'assignment' || stageId === 'handoff') {
      return mergeWorkflowFeed({
        demoDays,
        assignments: liveWorkflow.assignments,
        handoffs: liveWorkflow.handoffs,
        stageId,
        selectedStepId,
        patientQuery,
        statuses,
      })
    }
    return demoDays
  }, [
    liveInbox.monitor?.safety.drk_duplicate_check,
    liveInbox.referrals,
    liveWorkflow.assignments,
    liveWorkflow.handoffs,
    patientQuery,
    selectedStepId,
    stageId,
    statuses,
  ])

  const waitingPartnerCount = useMemo(() => {
    if (selectedStepId !== 'confirm-referral-contacted') return 0
    return days.reduce(
      (count, day) =>
        count + day.rows.filter(
          (row) =>
            row.status === 'waiting' &&
            isLiveInboxRow(row) &&
            row.workflowStep?.step_id === 'confirm-referral-contacted',
        ).length,
      0,
    )
  }, [days, selectedStepId])

  const latestProviderAvailability = useMemo(() => {
    const patientId = state.latestProviderAvailabilityPatientId
    const request = patientId ? state.providerAvailability[patientId] : undefined
    if (!patientId || !request) return null
    return {
      patientId,
      occurredAt: request.requestedAt,
      deadlineAt: request.deadlineAt,
    }
  }, [
    state.latestProviderAvailabilityPatientId,
    state.providerAvailability,
  ])

  const latestSchedulingHandoff = state.schedulingHandoffs[0] ?? null
  const latestAssignmentHandoff = state.latestAssignmentHandoff
  const latestIntakeReview = state.latestIntakeReview

  const displayDays = useMemo(() => {
    const latest =
      selectedStepId === 'assign-owner' ||
      selectedStepId === 'select-provider' ||
      isAssignmentHandoffStep(selectedStepId)
        ? latestAssignmentHandoff
        : selectedStepId === 'confirm-provider-availability'
          ? latestProviderAvailability
          : selectedStepId === 'update-monday-drk' ||
              selectedStepId === 'send-referral-provider'
            ? latestSchedulingHandoff
              ? {
                  patientId: latestSchedulingHandoff.patientId,
                  occurredAt: latestSchedulingHandoff.readyAt,
                }
              : null
            : isIntakeFollowUpStep(selectedStepId)
              ? latestIntakeReview
              : null
    if (!latest) return days

    const latestRow = days
      .flatMap((day) => day.rows)
      .find((row) => row.patientId === latest.patientId)
    const recordsSummary = latestSchedulingHandoff
      ? `Monday.com and DRK updated with ${latestSchedulingHandoff.provider.name}`
      : ''
    const referralSummary =
      latestSchedulingHandoff?.route === 'provider_confirmed'
        ? `Referral sent to ${latestSchedulingHandoff.provider.name}`
        : 'Referral ready to send'
    const referralStatus =
      latestSchedulingHandoff?.route === 'provider_confirmed'
        ? ('done' as const)
        : ('waiting' as const)
    const injectedRow = latestRow
      ? {
          ...latestRow,
          occurredAt: latest.occurredAt,
          status:
            selectedStepId === 'update-monday-drk'
              ? ('done' as const)
              : selectedStepId === 'send-referral-provider'
                ? referralStatus
                : selectedStepId === 'confirm-referral-contacted'
                  ? ('waiting' as const)
                  : isIntakeFollowUpStep(selectedStepId)
                    ? ('done' as const)
                    : latestRow.status,
          summary:
            selectedStepId === 'update-monday-drk'
              ? recordsSummary
              : selectedStepId === 'send-referral-provider'
                ? referralSummary
                : isIntakeFollowUpStep(selectedStepId)
                  ? intakeFollowUpSummary(latest.patientId, selectedStepId)
                  : latestRow.summary,
        }
      : selectedStepId === 'update-monday-drk' && latestSchedulingHandoff
        ? {
            patientId: latestSchedulingHandoff.patientId,
            patientName: latestSchedulingHandoff.patientName,
            stepId: 'update-monday-drk',
            status: 'done' as const,
            summary: recordsSummary,
            occurredAt: latestSchedulingHandoff.readyAt,
          }
        : selectedStepId === 'send-referral-provider' && latestSchedulingHandoff
        ? {
            patientId: latestSchedulingHandoff.patientId,
            patientName: latestSchedulingHandoff.patientName,
            stepId: 'send-referral-provider',
            status: referralStatus,
            summary: referralSummary,
            occurredAt: latestSchedulingHandoff.readyAt,
          }
        : selectedStepId === 'assign-owner' && latestAssignmentHandoff
          ? {
              patientId: latestAssignmentHandoff.patientId,
              patientName: latestAssignmentHandoff.patientName,
              stepId: 'assign-owner',
              status: 'done' as const,
              summary: 'Case manager notified of the new assignment',
              occurredAt: latestAssignmentHandoff.occurredAt,
            }
        : selectedStepId === 'select-provider' && latestAssignmentHandoff
          ? {
              patientId: latestAssignmentHandoff.patientId,
              patientName: latestAssignmentHandoff.patientName,
              stepId: 'select-provider',
              status: 'waiting' as const,
              summary: 'Case manager assigned · ready to select provider',
              occurredAt: latestAssignmentHandoff.occurredAt,
            }
        : isAssignmentHandoffStep(selectedStepId) && latestAssignmentHandoff
          ? {
              patientId: latestAssignmentHandoff.patientId,
              patientName: latestAssignmentHandoff.patientName,
              stepId: selectedStepId,
              status: 'done' as const,
              summary:
                selectedStepId === 'notify-referral-source'
                  ? 'Referral source notified · assigned case manager CCd'
                  : selectedStepId === 'create-monday-record'
                    ? 'Monday.com record created from canonical referral'
                    : 'DRK chart created from approved intake data',
              occurredAt: latestAssignmentHandoff.occurredAt,
            }
        : isIntakeFollowUpStep(selectedStepId) && latestIntakeReview
          ? {
              patientId: latestIntakeReview.patientId,
              patientName: latestIntakeReview.patientName,
              stepId: selectedStepId,
              status:
                selectedStepId === 'confirm-referral-contacted'
                  ? ('waiting' as const)
                  : ('done' as const),
              summary: intakeFollowUpSummary(
                latestIntakeReview.patientId,
                selectedStepId,
              ),
              occurredAt: latestIntakeReview.occurredAt,
            }
        : null
    if (!injectedRow) return days

    const remainingDays = days
      .map((day) => ({
        ...day,
        rows: day.rows.filter(
          (row) => row.patientId !== latest.patientId,
        ),
      }))
      .filter((day) => day.rows.length > 0)

    return [
      {
        key: `latest-${selectedStepId}`,
        label: 'Today',
        month: '—',
        day: '—',
        rows: [injectedRow],
      },
      ...remainingDays,
    ]
  }, [
    days,
    latestAssignmentHandoff,
    latestIntakeReview,
    latestProviderAvailability,
    latestSchedulingHandoff,
    selectedStepId,
  ])

  const filteredDisplayDays = useMemo(() => {
    if (selectedStepId === 'check-scheduling-status') {
      return displayDays
        .map((day) => ({
          ...day,
          rows: day.rows.filter((row) => {
            const bucket = eodSchedulingBucket(
              eodSchedulingCheckForPatient(row.patientId),
            )
            if (activeStatusFilter === 'all') return true
            return bucket === activeStatusFilter
          }),
        }))
        .filter((day) => day.rows.length > 0)
    }
    if (selectedStepId === 'follow-up-case-manager') {
      const filtered = displayDays
        .map((day) => ({
          ...day,
          rows: day.rows.filter((row) =>
            eodFollowUpEligible(
              eodSchedulingCheckForPatient(row.patientId),
              Boolean(eodManualCmFollowUp[row.patientId]),
            ),
          ),
        }))
        .filter((day) => day.rows.length > 0)

      const manualRows = Object.entries(eodManualCmFollowUp)
        .filter(([, sent]) => sent)
        .map(([patientId]): StepFeedRow | null => {
          const patient = patientsForStage(stageId).find(
            (entry) => entry.patientId === patientId,
          )
          if (!patient) return null
          const record = eodSchedulingCheckForPatient(patientId)
          return {
            patientId,
            patientName: patient.patientName,
            stepId: 'follow-up-case-manager',
            status: 'done' as const,
            summary: eodCmFollowUpSummary(record, true),
            occurredAt: opsTimestamp(),
          }
        })
        .filter((row): row is StepFeedRow => row !== null)

      return prependEodFeedRows(filtered, manualRows)
    }
    if (selectedStepId === 'escalate-unresolved-cases') {
      const filtered = displayDays
        .map((day) => ({
          ...day,
          rows: day.rows.filter((row) => {
            const record = eodSchedulingCheckForPatient(row.patientId)
            return eodEscalationEligible(
              record,
              Boolean(
                eodEscalated[row.patientId] || record.escalatedToManagement,
              ),
            )
          }),
        }))
        .filter((day) => day.rows.length > 0)

      const escalatedRows = Object.entries(eodEscalated)
        .filter(([, escalated]) => escalated)
        .map(([patientId]): StepFeedRow | null => {
          const patient = patientsForStage(stageId).find(
            (entry) => entry.patientId === patientId,
          )
          if (!patient) return null
          const record = eodSchedulingCheckForPatient(patientId)
          return {
            patientId,
            patientName: patient.patientName,
            stepId: 'escalate-unresolved-cases',
            status: 'done' as const,
            summary: eodEscalationConfirmLabel(record),
            occurredAt: opsTimestamp(),
          }
        })
        .filter((row): row is StepFeedRow => row !== null)

      return prependEodFeedRows(filtered, escalatedRows)
    }
    if (selectedStepId === 'patient-seen') {
      return displayDays
        .map((day) => ({
          ...day,
          rows: day.rows.filter((row) => {
            const record = weeklyVisitCheckForPatient(row.patientId)
            if (!weeklyPatientSeenEligible(record)) return false
            if (activeStatusFilter === 'done') {
              return record?.visitOutcome === 'seen'
            }
            if (activeStatusFilter === 'waiting') {
              return record?.visitOutcome === 'not_seen'
            }
            return true
          }),
        }))
        .filter((day) => day.rows.length > 0)
    }
    if (selectedStepId === 'wound-healed') {
      return displayDays
        .map((day) => ({
          ...day,
          rows: day.rows.filter((row) => {
            const record = weeklyVisitCheckForPatient(row.patientId)
            if (!weeklyWoundHealedEligible(record)) return false
            const actionDone = weeklyHoldsActionComplete(
              record,
              Boolean(weeklyHoldsActionTaken[row.patientId]),
            )
            if (activeStatusFilter === 'done') return actionDone
            if (activeStatusFilter === 'waiting') return !actionDone
            return true
          }),
        }))
        .filter((day) => day.rows.length > 0)
    }
    if (selectedStepId === 'patient-expired') {
      return displayDays
        .map((day) => ({
          ...day,
          rows: day.rows.filter((row) => {
            const record = weeklyVisitCheckForPatient(row.patientId)
            if (!weeklyPatientExpiredEligible(record)) return false
            const actionDone = weeklyHoldsActionComplete(
              record,
              Boolean(weeklyHoldsActionTaken[row.patientId]),
            )
            if (activeStatusFilter === 'done') return actionDone
            if (activeStatusFilter === 'waiting') return !actionDone
            return true
          }),
        }))
        .filter((day) => day.rows.length > 0)
    }
    if (selectedStepId === 'patient-on-hold') {
      return displayDays
        .map((day) => ({
          ...day,
          rows: day.rows.filter((row) => {
            const record = weeklyVisitCheckForPatient(row.patientId)
            if (!weeklyPatientOnHoldEligible(record)) return false
            const actionDone = weeklyHoldsActionComplete(
              record,
              Boolean(weeklyHoldsActionTaken[row.patientId]),
            )
            if (activeStatusFilter === 'done') return actionDone
            if (activeStatusFilter === 'waiting') return !actionDone
            return true
          }),
        }))
        .filter((day) => day.rows.length > 0)
    }
    return displayDays
  }, [
    displayDays,
    eodEscalated,
    eodManualCmFollowUp,
    selectedStepId,
    stageId,
    activeStatusFilter,
    weeklyHoldsActionTaken,
  ])

  useEffect(() => {
    if (
      stageId !== 'assignment' ||
      selectedStepId !== 'assign-owner' ||
      !state.assignmentNotifyUnread
    ) {
      return
    }
    setShowUnreadAssignmentMessage(true)
  }, [selectedStepId, stageId, state.assignmentNotifyUnread])

  useEffect(() => {
    if (
      stageId !== 'provider' ||
      selectedStepId !== 'confirm-provider-availability' ||
      !state.providerAvailabilityUnread
    ) {
      return
    }
    setShowUnreadProviderMessage(true)
  }, [selectedStepId, stageId, state.providerAvailabilityUnread])

  useEffect(() => {
    if (
      stageId !== 'end-of-day' ||
      selectedStepId !== 'follow-up-case-manager' ||
      !state.eodFollowUpUnread
    ) {
      return
    }
    setShowUnreadEodFollowUpMessage(true)
  }, [selectedStepId, stageId, state.eodFollowUpUnread])

  useEffect(() => {
    if (
      stageId !== 'end-of-day' ||
      selectedStepId !== 'escalate-unresolved-cases' ||
      !state.eodEscalationUnread
    ) {
      return
    }
    setShowUnreadEodEscalationMessage(true)
  }, [selectedStepId, stageId, state.eodEscalationUnread])

  useEffect(() => {
    if (
      stageId !== 'handoff' ||
      !isAssignmentHandoffStep(selectedStepId) ||
      !assignmentHandoffUnreadForStep(state, selectedStepId)
    ) {
      return
    }
    setShowUnreadAssignmentHandoff(true)
  }, [
    selectedStepId,
    stageId,
    state.handoffDrkUnread,
    state.handoffMondayUnread,
    state.handoffNotifyUnread,
  ])

  useEffect(() => {
    if (
      stageId !== 'provider' ||
      selectedStepId !== 'select-provider' ||
      !state.providerSelectUnread
    ) {
      return
    }
    setShowUnreadProviderSelect(true)
  }, [selectedStepId, stageId, state.providerSelectUnread])

  useEffect(() => {
    if (
      stageId !== 'intake' ||
      !isIntakeFollowUpStep(selectedStepId) ||
      !intakeFollowUpUnreadForStep(state, selectedStepId)
    ) {
      return
    }
    setShowUnreadIntakeDuplicate(true)
  }, [
    selectedStepId,
    stageId,
    state.intakeDrkUnread,
    state.intakeMondayUnread,
    state.intakePartnerUnread,
  ])

  useEffect(() => {
    if (
      stageId !== 'scheduling' ||
      selectedStepId !== 'send-referral-provider' ||
      !state.schedulingHandoffMessageUnread
    ) {
      return
    }
    setShowUnreadHandoffMessage(true)
    dispatch({ type: 'MARK_SCHEDULING_HANDOFF_READ' })
  }, [
    dispatch,
    selectedStepId,
    stageId,
    state.schedulingHandoffMessageUnread,
  ])

  useEffect(() => {
    if (
      stageId !== 'provider' ||
      selectedStepId !== 'update-monday-drk' ||
      !state.providerRecordsMessageUnread
    ) {
      return
    }
    setShowUnreadProviderRecordsMessage(true)
    dispatch({ type: 'MARK_PROVIDER_RECORDS_READ' })
  }, [
    dispatch,
    selectedStepId,
    stageId,
    state.providerRecordsMessageUnread,
  ])

  const selectStep = (stepId: string) => {
    if (selectedStepId === 'assign-owner' && stepId !== 'assign-owner') {
      setShowUnreadAssignmentMessage(false)
    }
    if (stepId === 'assign-owner') {
      const unread = state.assignmentNotifyUnread
      setShowUnreadAssignmentMessage(unread)
      if (unread) {
        dispatch({ type: 'MARK_ASSIGNMENT_NOTIFY_READ' })
      }
    }
    if (
      selectedStepId === 'confirm-provider-availability' &&
      stepId !== 'confirm-provider-availability'
    ) {
      setShowUnreadProviderMessage(false)
    }
    if (stepId === 'confirm-provider-availability') {
      const unread = state.providerAvailabilityUnread
      setShowUnreadProviderMessage(unread)
      if (unread) {
        dispatch({ type: 'MARK_PROVIDER_AVAILABILITY_READ' })
      }
    }
    if (
      selectedStepId === 'send-referral-provider' &&
      stepId !== 'send-referral-provider'
    ) {
      setShowUnreadHandoffMessage(false)
    }
    if (stepId === 'send-referral-provider') {
      setShowUnreadHandoffMessage(state.schedulingHandoffMessageUnread)
      if (state.schedulingHandoffMessageUnread) {
        dispatch({ type: 'MARK_SCHEDULING_HANDOFF_READ' })
      }
    }
    if (
      selectedStepId === 'update-monday-drk' &&
      stepId !== 'update-monday-drk'
    ) {
      setShowUnreadProviderRecordsMessage(false)
    }
    if (stepId === 'update-monday-drk') {
      setShowUnreadProviderRecordsMessage(state.providerRecordsMessageUnread)
      if (state.providerRecordsUnread || state.providerRecordsMessageUnread) {
        dispatch({ type: 'MARK_PROVIDER_RECORDS_READ' })
      }
    }
    if (
      selectedStepId === 'follow-up-case-manager' &&
      stepId !== 'follow-up-case-manager'
    ) {
      setShowUnreadEodFollowUpMessage(false)
    }
    if (stepId === 'follow-up-case-manager') {
      const unread = state.eodFollowUpUnread
      setShowUnreadEodFollowUpMessage(unread)
      if (unread) {
        dispatch({ type: 'MARK_EOD_FOLLOW_UP_READ' })
      }
    }
    if (
      selectedStepId === 'escalate-unresolved-cases' &&
      stepId !== 'escalate-unresolved-cases'
    ) {
      setShowUnreadEodEscalationMessage(false)
    }
    if (stepId === 'escalate-unresolved-cases') {
      const unread = state.eodEscalationUnread
      setShowUnreadEodEscalationMessage(unread)
      if (unread) {
        dispatch({ type: 'MARK_EOD_ESCALATION_READ' })
      }
    }
    if (
      isAssignmentHandoffStep(selectedStepId) &&
      !isAssignmentHandoffStep(stepId)
    ) {
      setShowUnreadAssignmentHandoff(false)
    }
    if (isAssignmentHandoffStep(stepId)) {
      const unread = assignmentHandoffUnreadForStep(state, stepId)
      setShowUnreadAssignmentHandoff(unread)
      if (unread) {
        dispatch({ type: 'MARK_HANDOFF_STEP_READ', stepId })
      }
    }
    if (
      selectedStepId === 'select-provider' &&
      stepId !== 'select-provider'
    ) {
      setShowUnreadProviderSelect(false)
    }
    if (stepId === 'select-provider') {
      const unread = state.providerSelectUnread
      setShowUnreadProviderSelect(unread)
      if (unread) {
        dispatch({ type: 'MARK_PROVIDER_SELECT_READ' })
      }
    }
    if (
      isIntakeFollowUpStep(selectedStepId) &&
      !isIntakeFollowUpStep(stepId)
    ) {
      setShowUnreadIntakeDuplicate(false)
    }
    if (isIntakeFollowUpStep(stepId)) {
      const unread = intakeFollowUpUnreadForStep(state, stepId)
      setShowUnreadIntakeDuplicate(unread)
      if (unread) {
        dispatch({ type: 'MARK_INTAKE_STEP_READ', stepId })
      }
    }
    setSelectedStepId(stepId)
  }

  const pickStatus = (value: StatusFilterValue) => {
    setStatusFilter(value)
    setStatusMenuOpen(false)
  }

  const detailForRow = (patientId: string): StepDetail | null => {
    if (!selectedStepId) return null
    return detailForPatientStep(stageId, patientId, selectedStepId)
  }

  return (
    <div className="stage-ops-steps" aria-label="Patient steps">
      <aside className="stage-ops-steps__rail">
        <div className="stage-ops-steps__rail-copy">
          <h2>
            {microsteps.length} {microsteps.length === 1 ? 'step' : 'steps'}
          </h2>
          <p className="muted">Select a step to see patient updates.</p>
        </div>
        <MicrostepList
          steps={microsteps}
          selectedStepId={selectedStepId}
          onSelect={selectStep}
          attentionStepIds={[
            ...(state.assignmentNotifyUnread ? ['assign-owner'] : []),
            ...(state.providerAvailabilityUnread
              ? ['confirm-provider-availability']
              : []),
            ...(state.providerRecordsUnread ? ['update-monday-drk'] : []),
            ...(state.eodFollowUpUnread ? ['follow-up-case-manager'] : []),
            ...(state.eodEscalationUnread ? ['escalate-unresolved-cases'] : []),
            ...(state.handoffNotifyUnread ? ['notify-referral-source'] : []),
            ...(state.handoffMondayUnread ? ['create-monday-record'] : []),
            ...(state.handoffDrkUnread ? ['create-update-drk'] : []),
            ...(state.providerSelectUnread ? ['select-provider'] : []),
            ...(state.intakeMondayUnread ? ['check-monday'] : []),
            ...(state.intakeDrkUnread ? ['check-drk'] : []),
            ...(state.intakePartnerUnread
              ? ['confirm-referral-contacted']
              : []),
          ]}
        />
      </aside>

      <div className="stage-ops-steps__detail">
        <div className="stage-ops-steps__toolbar">
          <div className="stage-ops-steps__toolbar-copy">
            <h3>{selectedStep?.name ?? 'Step'}</h3>
            {waitingPartnerCount > 0 ? (
              <p className="stage-ops-steps__queue-hint">
                {waitingPartnerCount}{' '}
                {waitingPartnerCount === 1 ? 'patient' : 'patients'} need partner
                confirmation
              </p>
            ) : null}
          </div>

          {stageId === 'intake' ? (
            <LiveInboxStatus
              state={liveInbox}
              onRefresh={liveInbox.refresh}
            />
          ) : null}

          <div
            className="stage-ops-steps__filter-bar"
            aria-label="Feed filters"
          >
            <div
              className="stage-ops-steps__status-menu"
              ref={statusMenuRef}
            >
              <button
                type="button"
                className={`stage-ops-steps__status-trigger${statusMenuOpen ? ' is-open' : ''}${selectedStatusOption ? ` is-${statusFilterTone(selectedStatusOption)}` : ''}`}
                aria-label="Filter by status"
                aria-haspopup="listbox"
                aria-expanded={statusMenuOpen}
                onClick={() => setStatusMenuOpen((current) => !current)}
              >
                <span className="stage-ops-steps__status-trigger-label">
                  {selectedStatusOption
                    ? selectedStatusOption.meaning
                    : 'All statuses'}
                </span>
                <ChevronDown
                  size={14}
                  className="stage-ops-steps__status-trigger-icon"
                  aria-hidden="true"
                />
              </button>

              {statusMenuOpen ? (
                <ul
                  className="stage-ops-steps__status-options"
                  role="listbox"
                  aria-label="Status options"
                >
                  <li>
                    <button
                      type="button"
                      role="option"
                      aria-selected={activeStatusFilter === 'all'}
                      className={`stage-ops-steps__status-option${activeStatusFilter === 'all' ? ' is-selected' : ''}`}
                      onClick={() => pickStatus('all')}
                    >
                      All statuses
                    </button>
                  </li>
                  {statusFilters.map((status) => (
                    <li key={status.id}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={activeStatusFilter === status.id}
                        className={`stage-ops-steps__status-option is-${statusFilterTone(status)}${activeStatusFilter === status.id ? ' is-selected' : ''}`}
                        onClick={() => pickStatus(status.id)}
                      >
                        {status.meaning}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>

            <label className="stage-ops-steps__patient-search">
              <Search size={15} aria-hidden="true" />
              <input
                type="search"
                value={patientQuery}
                onChange={(event) => setPatientQuery(event.target.value)}
                placeholder="Search patients"
                aria-label="Search patients"
              />
            </label>
          </div>
        </div>

        {filteredDisplayDays.length ? (
          <ol
            className="stage-ops-step-feed"
            aria-label="Step updates"
            key={selectedStepId}
          >
            {filteredDisplayDays.map((day) => (
              <li key={day.key} className="stage-ops-step-feed__day">
                <h4 className="stage-ops-step-feed__day-header">
                  <time
                    dateTime={day.key === 'undated' ? undefined : day.key}
                  >
                    {day.label}
                  </time>
                  <span className="stage-ops-step-feed__day-count">
                    {day.rows.length}{' '}
                    {day.rows.length === 1 ? 'update' : 'updates'}
                  </span>
                </h4>

                <ul className="stage-ops-step-feed__rows">
                  {day.rows.map((row) => {
                    const rawDetail = detailForRow(row.patientId)
                    const detail =
                      selectedStepId === 'extract-and-verify' && rawDetail
                        ? overlayIntakeDetail(
                            rawDetail,
                            state.intakeFieldEdits[row.patientId],
                            state.intakeSectionRows[row.patientId],
                          )
                        : rawDetail
                    const canonical = intakeDemoPatient(row.patientId)?.canonical
                    const suggestedCaseManager = caseManagerSuggestion(
                      row.patientId,
                    )
                    const suggestedProvider = providerSuggestion(row.patientId)
                    const patientLocation =
                      providerPatientLocationDisplay(row.patientId)
                    const locationMatchedProviders =
                      providersForPatientLocation(row.patientId)
                    const locationMatchedSuggestion =
                      locationMatchedProviders.find(
                        (provider) => provider.id === suggestedProvider.id,
                      ) ?? locationMatchedProviders[0]
                    const recommendedProvider =
                      selectedStepId === 'select-provider'
                        ? locationMatchedSuggestion
                        : undefined
                    const selectedProviderId =
                      state.providerSelectedIds[row.patientId] ??
                      locationMatchedSuggestion?.id ??
                      suggestedProvider.id
                    const selectedProvider =
                      locationMatchedProviders.find(
                        (provider) => provider.id === selectedProviderId,
                      ) ??
                      PROVIDER_OPTIONS.find(
                        (provider) => provider.id === selectedProviderId,
                      ) ??
                      locationMatchedSuggestion ??
                      suggestedProvider
                    const noProviderLocationMatch =
                      selectedStepId === 'select-provider' &&
                      locationMatchedProviders.length === 0
                    const providerTerritoryResolution =
                      state.providerTerritoryResolutions[row.patientId]
                    const providerConfirmed = Boolean(
                      state.providerConfirmed[row.patientId],
                    )
                    const liveAvailability =
                      state.providerAvailability[row.patientId]
                    const isLatestProviderAvailability =
                      row.patientId === latestProviderAvailability?.patientId
                    const historicalAvailabilityOutcome:
                      | 'waiting'
                      | 'confirmed'
                      | 'timeout' =
                      row.status === 'done'
                        ? 'confirmed'
                        : row.status === 'blocked'
                          ? 'timeout'
                          : 'waiting'
                    const showProviderAvailability =
                      selectedStepId === 'confirm-provider-availability' &&
                      (Boolean(liveAvailability) ||
                        row.status === 'done' ||
                        row.status === 'blocked' ||
                        row.status === 'waiting' ||
                        row.status === 'current')
                    const providerAvailability = showProviderAvailability
                      ? liveAvailability
                        ? {
                            provider: selectedProvider,
                            requestedAt: liveAvailability.requestedAt,
                            deadlineAt: liveAvailability.deadlineAt,
                            outcome: liveAvailability.outcome,
                            resolvedAt: liveAvailability.resolvedAt,
                            responseDuration:
                              liveAvailability.outcome === 'confirmed'
                                ? '13 minutes'
                                : liveAvailability.outcome === 'timeout' ||
                                    liveAvailability.outcome ===
                                      'placement_completed'
                                  ? '1 hour'
                                  : undefined,
                          }
                        : {
                            provider: selectedProvider,
                            requestedAt:
                              historicalAvailabilityOutcome === 'confirmed'
                                ? shiftedOpsTimestamp(row.occurredAt, -13)
                                : historicalAvailabilityOutcome === 'timeout'
                                  ? shiftedOpsTimestamp(row.occurredAt, -60)
                                  : row.occurredAt,
                            deadlineAt:
                              historicalAvailabilityOutcome === 'timeout'
                                ? row.occurredAt
                                : historicalAvailabilityOutcome ===
                                    'confirmed'
                                  ? shiftedOpsTimestamp(row.occurredAt, 47)
                                  : shiftedOpsTimestamp(row.occurredAt, 60),
                            outcome: historicalAvailabilityOutcome,
                            resolvedAt:
                              historicalAvailabilityOutcome === 'confirmed'
                                ? row.occurredAt
                                : undefined,
                            responseDuration:
                              historicalAvailabilityOutcome === 'confirmed'
                                ? '13 minutes'
                                : historicalAvailabilityOutcome === 'timeout'
                                  ? '1 hour'
                                  : undefined,
                          }
                      : undefined
                    const liveSchedulingHandoff =
                      selectedStepId === 'send-referral-provider'
                        ? state.schedulingHandoffs.find(
                            (handoff) => handoff.patientId === row.patientId,
                          )
                        : undefined
                    const schedulingHandoff =
                      liveSchedulingHandoff ??
                      (selectedStepId === 'send-referral-provider'
                        ? {
                            patientId: row.patientId,
                            patientName: row.patientName,
                            provider: selectedProvider,
                            route:
                              row.status === 'done'
                                ? ('provider_confirmed' as const)
                                : ('manual_placement' as const),
                            requestedAt: row.occurredAt,
                            deadlineAt: row.occurredAt,
                            readyAt: row.occurredAt,
                            samplePdf: referralPdfForPatient(row.patientId),
                          }
                        : undefined)
                    const assignmentSuggestion =
                      selectedStepId === 'determine-owner' && !isLiveWorkflowRow(row)
                        ? suggestedCaseManager
                        : undefined
                    const liveAssignment = isLiveWorkflowRow(row)
                      ? row.assignment
                      : undefined
                    const liveHandoff = isLiveWorkflowRow(row)
                      ? row.handoff
                      : undefined
                    const caseManagerOptions = liveAssignment
                      ? liveWorkflow.caseManagers
                      : CASE_MANAGER_OPTIONS
                    const assignmentConfirmed =
                      liveAssignment?.status === 'completed' ||
                      Boolean(confirmedAssignments[row.patientId])
                    const selectedCaseManagerEmail =
                      selectedCaseManagers[row.patientId] ??
                      liveAssignment?.assigned_case_manager?.email ??
                      liveAssignment?.recommended_assignee ??
                      (liveAssignment ? '' : suggestedCaseManager.email)
                    const selectedCaseManager =
                      caseManagerOptions.find(
                        (manager) =>
                          manager.email === selectedCaseManagerEmail,
                      ) ?? (liveAssignment ? undefined : suggestedCaseManager)
                    const notification =
                      selectedCaseManager &&
                      ((selectedStepId === 'assign-owner' && !liveAssignment) ||
                        (stageId === 'handoff' &&
                          selectedStepId === 'notify-referral-source' &&
                          !liveHandoff))
                        ? caseManagerNotification(
                            row.patientId,
                            row.patientName,
                            selectedCaseManager,
                          )
                        : undefined
                    const recordsHandoff =
                      selectedStepId === 'update-monday-drk'
                        ? state.schedulingHandoffs.find(
                            (handoff) => handoff.patientId === row.patientId,
                          )
                        : undefined
                    const assignedProvider =
                      selectedStepId === 'update-monday-drk'
                        ? recordsHandoff?.provider ?? selectedProvider
                        : undefined
                    const mondayRecord = (() => {
                      if (
                        stageId === 'handoff' &&
                        selectedStepId === 'create-monday-record' &&
                        !liveHandoff
                      ) {
                        return mondayRecordForPatient(
                          row.patientId,
                          row.patientName,
                          canonical,
                        )
                      }
                      if (selectedStepId !== 'update-monday-drk' || !assignedProvider) {
                        return undefined
                      }
                      return mondayRecordWithAssignedProvider(
                        mondayRecordForPatient(
                          row.patientId,
                          row.patientName,
                          canonical,
                        ),
                        assignedProvider,
                        recordsHandoff?.route === 'manual_placement'
                          ? 'Provider placed'
                          : 'Provider confirmed',
                      )
                    })()
                    const eodSchedulingCheck =
                      selectedStepId === 'check-scheduling-status' ||
                      selectedStepId === 'follow-up-case-manager' ||
                      selectedStepId === 'escalate-unresolved-cases'
                        ? eodSchedulingCheckForPatient(row.patientId)
                        : undefined
                    const eodEscalatedForPatient = Boolean(
                      eodEscalated[row.patientId] ||
                        eodSchedulingCheck?.escalatedToManagement,
                    )
                    const eodManualCmFollowUpForPatient = Boolean(
                      eodManualCmFollowUp[row.patientId],
                    )
                    const weeklyVisitCheck =
                      selectedStepId === 'patient-seen' ||
                      selectedStepId === 'wound-healed' ||
                      selectedStepId === 'patient-expired' ||
                      selectedStepId === 'patient-on-hold'
                        ? weeklyVisitCheckForPatient(row.patientId)
                        : undefined
                    const weeklyRescheduleForPatient = Boolean(
                      weeklyRescheduleConfirmed[row.patientId],
                    )
                    const weeklyDischargeForPatient = Boolean(
                      weeklyDischargeReview[row.patientId] ||
                        weeklyVisitCheck?.dischargeReviewQueued,
                    )
                    const weeklyHoldsActionForPatient = Boolean(
                      weeklyHoldsActionTaken[row.patientId] ||
                        weeklyVisitCheck?.movedToHolds ||
                        weeklyVisitCheck?.closureActionTaken,
                    )
                    const weeklyAppointmentRescheduledForPatient = Boolean(
                      weeklyAppointmentRescheduled[row.patientId],
                    )
                    const drkDraft = (() => {
                      if (
                        stageId === 'handoff' &&
                        selectedStepId === 'create-update-drk' &&
                        !liveHandoff
                      ) {
                        return drkDraftForPatient(
                          row.patientId,
                          row.patientName,
                          canonical,
                        )
                      }
                      if (selectedStepId !== 'update-monday-drk' || !assignedProvider) {
                        return undefined
                      }
                      return drkDraftWithAssignedProvider(
                        drkDraftForPatient(
                          row.patientId,
                          row.patientName,
                          canonical,
                        ),
                        assignedProvider,
                      )
                    })()
                    const liveInboxReferral = isLiveInboxRow(row)
                      ? row.inbox
                      : undefined
                    const liveInboxStep = isLiveInboxRow(row)
                      ? row.workflowStep
                      : undefined
                    return (
                      <li
                        key={`${row.patientId}-${row.stepId}`}
                        className="stage-ops-step-feed__item is-open"
                      >
                        <StageFeedMessage
                          summary={
                            liveInboxReferral
                              ? row.summary
                              : noProviderLocationMatch
                              ? providerTerritoryResolution === 'assigned'
                                ? `${selectedProvider.name} selected by Nicole`
                                : providerTerritoryResolution === 'discharged'
                                  ? 'Patient discharged after Nicole review'
                                  : 'Patient sent for review to Nicole'
                              : recommendedProvider && selectedProvider
                              ? providerConfirmed
                                ? `${selectedProvider.name} selected as Provider`
                                : 'Provider needs to be selected'
                              : selectedStepId ===
                                    'confirm-provider-availability' &&
                                  providerAvailability
                                ? providerAvailability.outcome === 'confirmed'
                                  ? `${selectedProvider.name} confirmed availability`
                                  : providerAvailability.outcome ===
                                      'placement_completed'
                                    ? `${selectedProvider.name} placed manually`
                                    : providerAvailability.outcome === 'timeout'
                                      ? `${selectedProvider.name} did not respond · CM placement needed`
                                      : `${selectedProvider.name} availability confirmation requested`
                              : selectedStepId === 'update-monday-drk' &&
                                  assignedProvider
                                ? `Monday.com and DRK updated with ${assignedProvider.name}`
                              : schedulingHandoff
                              ? schedulingHandoff.route === 'provider_confirmed'
                                ? `Referral sent to ${schedulingHandoff.provider.name}`
                                : 'Referral ready to send'
                              : drkDraft
                              ? drkDraft.readyForFill
                                ? 'DRK chart created'
                                : 'DRK chart draft needs review'
                              : mondayRecord
                              ? 'Monday.com record created'
                              : stageId === 'handoff' && notification
                              ? `${notification.managerName} notified`
                              : selectedStepId === 'assign-owner'
                              ? `${selectedCaseManager?.name ?? 'Case manager'} notified`
                              : selectedStepId === 'determine-owner'
                                ? assignmentConfirmed
                                  ? `${selectedCaseManager?.name ?? 'Case manager'} confirmed as Case Manager`
                                  : 'Case Manager needs to be confirmed'
                              : selectedStepId === 'check-scheduling-status' &&
                                  eodSchedulingCheck
                                ? eodSchedulingCheckDisplaySummary(
                                    eodSchedulingCheck,
                                    {
                                      manualCmFollowUp:
                                        eodManualCmFollowUpForPatient,
                                      escalatedToManagement:
                                        eodEscalatedForPatient,
                                    },
                                  )
                              : selectedStepId === 'follow-up-case-manager' &&
                                  eodSchedulingCheck
                                ? eodCmFollowUpSummary(
                                    eodSchedulingCheck,
                                    eodManualCmFollowUpForPatient,
                                  )
                              : selectedStepId === 'escalate-unresolved-cases' &&
                                  eodSchedulingCheck
                                ? row.status === 'blocked'
                                  ? eodEscalationSummary(eodSchedulingCheck)
                                  : eodEscalatedForPatient
                                    ? eodEscalationConfirmLabel(eodSchedulingCheck)
                                    : eodEscalationSummary(eodSchedulingCheck)
                              : selectedStepId === 'patient-seen' &&
                                  weeklyVisitCheck
                                ? weeklyAppointmentRescheduledForPatient
                                  ? weeklyMissedVisitSummary(weeklyVisitCheck, {
                                      appointmentRescheduled: true,
                                    })
                                  : weeklyDischargeForPatient
                                    ? weeklyMissedVisitSummary(
                                        weeklyVisitCheck,
                                        {
                                          dischargeReviewSent: true,
                                        },
                                      )
                                    : weeklyRescheduleForPatient
                                      ? weeklyMissedVisitSummary(
                                          weeklyVisitCheck,
                                        )
                                      : weeklyVisitCheckSummary(
                                          weeklyVisitCheck,
                                        )
                              : (selectedStepId === 'wound-healed' ||
                                    selectedStepId === 'patient-expired' ||
                                    selectedStepId === 'patient-on-hold') &&
                                  weeklyVisitCheck
                                ? weeklyHoldsClosuresSummary(
                                    weeklyVisitCheck,
                                    weeklyHoldsActionForPatient,
                                  )
                              : eodSchedulingCheck
                                ? eodSchedulingCheckSummary(eodSchedulingCheck)
                                : row.summary
                          }
                          patientName={row.patientName}
                          status={
                            liveInboxReferral
                              ? row.status
                              : noProviderLocationMatch
                              ? providerTerritoryResolution
                                ? 'done'
                                : 'waiting'
                              : selectedStepId === 'check-scheduling-status' ||
                                  selectedStepId === 'follow-up-case-manager' ||
                                  selectedStepId === 'escalate-unresolved-cases'
                                ? (eodSchedulingStatusOption(row.patientId)
                                    .tone ?? 'done')
                              : selectedStepId === 'patient-seen' &&
                                  weeklyVisitCheck
                                ? weeklyVisitCheck.visitOutcome === 'seen'
                                  ? 'done'
                                  : 'waiting'
                              : (selectedStepId === 'wound-healed' ||
                                    selectedStepId === 'patient-expired' ||
                                    selectedStepId === 'patient-on-hold') &&
                                  weeklyVisitCheck
                                ? weeklyHoldsActionForPatient
                                  ? 'done'
                                  : 'waiting'
                              : selectedStepId === 'select-provider'
                              ? providerConfirmed
                                ? 'done'
                                : 'waiting'
                              : selectedStepId ===
                                    'confirm-provider-availability' &&
                                  providerAvailability
                                ? providerAvailability.outcome === 'confirmed' ||
                                  providerAvailability.outcome ===
                                    'placement_completed'
                                  ? 'done'
                                  : providerAvailability.outcome === 'timeout'
                                    ? 'blocked'
                                    : 'waiting'
                              : selectedStepId === 'update-monday-drk'
                              ? 'done'
                              : schedulingHandoff
                              ? schedulingHandoff.route === 'provider_confirmed'
                                ? 'done'
                                : 'waiting'
                              : selectedStepId === 'determine-owner'
                              ? assignmentConfirmed
                                ? 'done'
                                : 'waiting'
                              : row.status
                          }
                          statusLabel={
                            selectedStepId === 'check-scheduling-status' ||
                            selectedStepId === 'follow-up-case-manager' ||
                            selectedStepId === 'escalate-unresolved-cases'
                              ? eodSchedulingStatusOption(row.patientId).meaning
                              : weeklyStatusLabel(
                                  selectedStepId,
                                  selectedStepId === 'patient-seen' &&
                                    weeklyVisitCheck
                                    ? weeklyVisitCheck.visitOutcome === 'seen'
                                      ? 'done'
                                      : 'waiting'
                                    : (selectedStepId === 'wound-healed' ||
                                          selectedStepId === 'patient-expired' ||
                                          selectedStepId === 'patient-on-hold') &&
                                        weeklyVisitCheck
                                      ? weeklyHoldsActionForPatient
                                        ? 'done'
                                        : 'waiting'
                                      : '',
                                ) ?? undefined
                          }
                          occurredAt={row.occurredAt}
                          detail={
                            (eodSchedulingCheck &&
                              (selectedStepId === 'check-scheduling-status' ||
                                selectedStepId === 'follow-up-case-manager' ||
                                selectedStepId ===
                                  'escalate-unresolved-cases')) ||
                            (weeklyVisitCheck &&
                              (selectedStepId === 'patient-seen' ||
                                selectedStepId === 'wound-healed' ||
                                selectedStepId === 'patient-expired' ||
                                selectedStepId === 'patient-on-hold'))
                              ? null
                              : detail
                          }
                          showPdf={selectedStepId === 'receive-referral'}
                          isPartnerConfirmed={
                            row.status === 'done' ||
                            Boolean(partnerConfirmed[row.patientId])
                          }
                          onConfirmPartner={
                            selectedStepId === 'confirm-referral-contacted' &&
                            !liveInboxReferral
                              ? () =>
                                  setPartnerConfirmed((current) => ({
                                    ...current,
                                    [row.patientId]: true,
                                  }))
                              : undefined
                          }
                          assignmentSuggestion={assignmentSuggestion}
                          assignmentManualSelection={Boolean(liveAssignment)}
                          caseManagerOptions={caseManagerOptions}
                          selectedCaseManagerEmail={selectedCaseManagerEmail}
                          isAssignmentConfirmed={assignmentConfirmed}
                          onCaseManagerChange={
                            assignmentSuggestion || liveAssignment
                              ? (email) =>
                                  setSelectedCaseManagers((current) => ({
                                    ...current,
                                    [row.patientId]: email,
                                  }))
                              : undefined
                          }
                          onConfirmAssignment={
                            assignmentSuggestion || liveAssignment
                              ? () => {
                                  if (liveAssignment) {
                                    if (!selectedCaseManagerEmail) return
                                    setWorkflowActionError(null)
                                    void liveWorkflow
                                      .confirm(
                                        liveAssignment.case_id,
                                        selectedCaseManagerEmail,
                                      )
                                      .catch((error) =>
                                        setWorkflowActionError(
                                          error instanceof Error
                                            ? error.message
                                            : 'Assignment could not be confirmed.',
                                        ),
                                      )
                                    return
                                  }
                                  const occurredAt = opsTimestamp()
                                  setConfirmedAssignments((current) => ({
                                    ...current,
                                    [row.patientId]: true,
                                  }))
                                  dispatch({
                                    type: 'CONFIRM_ASSIGNMENT_HANDOFF',
                                    patientId: row.patientId,
                                    patientName: row.patientName,
                                    occurredAt,
                                  })
                                }
                              : undefined
                          }
                          intakeEditable={selectedStepId === 'extract-and-verify'}
                          isIntakeConfirmed={Boolean(
                            state.intakeVerified[row.patientId],
                          )}
                          onIntakeFieldChange={
                            selectedStepId === 'extract-and-verify'
                              ? (key, value) =>
                                  dispatch({
                                    type: 'EDIT_INTAKE_FIELD',
                                    patientId: row.patientId,
                                    key,
                                    value,
                                  })
                              : undefined
                          }
                          onIntakeSectionRowsReplace={
                            selectedStepId === 'extract-and-verify'
                              ? (sectionId, rows) =>
                                  dispatch({
                                    type: 'REPLACE_INTAKE_SECTION_ROWS',
                                    patientId: row.patientId,
                                    sectionId,
                                    rows,
                                  })
                              : undefined
                          }
                          onConfirmIntakeReview={
                            selectedStepId === 'extract-and-verify'
                              ? () =>
                                  dispatch({
                                    type: 'CONFIRM_INTAKE_REVIEW',
                                    patientId: row.patientId,
                                    patientName: row.patientName,
                                    occurredAt: opsTimestamp(),
                                  })
                              : undefined
                          }
                          onReopenIntakeReview={
                            selectedStepId === 'extract-and-verify'
                              ? () =>
                                  dispatch({
                                    type: 'REOPEN_INTAKE_REVIEW',
                                    patientId: row.patientId,
                                  })
                              : undefined
                          }
                          actionError={liveAssignment ? workflowActionError : null}
                          caseManagerNotification={notification}
                          mondayRecord={mondayRecord}
                          drkDraft={drkDraft}
                          providerRecommendation={recommendedProvider}
                          providerOptions={locationMatchedProviders}
                          providerSelectionLocation={
                            selectedStepId === 'select-provider'
                              ? patientLocation
                              : undefined
                          }
                          fallbackProviderOptions={
                            noProviderLocationMatch ? PROVIDER_OPTIONS : undefined
                          }
                          providerTerritoryResolution={
                            providerTerritoryResolution
                          }
                          selectedProviderId={selectedProviderId}
                          isProviderConfirmed={providerConfirmed}
                          onProviderChange={
                            recommendedProvider || noProviderLocationMatch
                              ? (providerId) =>
                                  dispatch({
                                    type: 'SELECT_PROVIDER',
                                    patientId: row.patientId,
                                    providerId,
                                  })
                              : undefined
                          }
                          onAssignFallbackProvider={
                            noProviderLocationMatch &&
                            !providerTerritoryResolution
                              ? () => {
                                  const times = availabilityRequestTimes()
                                  dispatch({
                                    type: 'RESOLVE_PROVIDER_TERRITORY',
                                    patientId: row.patientId,
                                    resolution: 'assigned',
                                    requestedAt: times.requestedAt,
                                    deadlineAt: times.deadlineAt,
                                  })
                                }
                              : undefined
                          }
                          onDischargePatient={
                            noProviderLocationMatch &&
                            !providerTerritoryResolution
                              ? () =>
                                  dispatch({
                                    type: 'RESOLVE_PROVIDER_TERRITORY',
                                    patientId: row.patientId,
                                    resolution: 'discharged',
                                  })
                              : undefined
                          }
                          onConfirmProvider={
                            recommendedProvider
                              ? () => {
                                  const times = availabilityRequestTimes()
                                  dispatch({
                                    type: 'CONFIRM_PROVIDER_SELECTION',
                                    patientId: row.patientId,
                                    requestedAt: times.requestedAt,
                                    deadlineAt: times.deadlineAt,
                                  })
                                }
                              : undefined
                          }
                          providerAvailability={providerAvailability}
                          schedulingHandoff={schedulingHandoff}
                          eodSchedulingCheck={eodSchedulingCheck}
                          eodFollowUp={selectedStepId === 'follow-up-case-manager'}
                          eodEscalation={
                            selectedStepId === 'escalate-unresolved-cases'
                          }
                          eodManualFollowUp={
                            selectedStepId === 'follow-up-case-manager' &&
                            eodManualCmFollowUpForPatient
                          }
                          eodEscalatedToManagement={eodEscalatedForPatient}
                          eodManualCmFollowUpSent={eodManualCmFollowUpForPatient}
                          onEodFollowUpWithCaseManager={
                            eodSchedulingCheck &&
                            selectedStepId === 'check-scheduling-status' &&
                            eodCmNotifyPending(eodSchedulingCheck)
                              ? () => {
                                  setEodManualCmFollowUp((current) => ({
                                    ...current,
                                    [row.patientId]: true,
                                  }))
                                  dispatch({
                                    type: 'CONFIRM_EOD_FOLLOW_UP',
                                    patientId: row.patientId,
                                  })
                                }
                              : undefined
                          }
                          onEodEscalateToManagement={
                            eodSchedulingCheck &&
                            selectedStepId === 'check-scheduling-status'
                              ? () => {
                                  setEodEscalated((current) => ({
                                    ...current,
                                    [row.patientId]: true,
                                  }))
                                  dispatch({
                                    type: 'CONFIRM_EOD_ESCALATION',
                                    patientId: row.patientId,
                                  })
                                }
                              : undefined
                          }
                          weeklyVisitCheck={weeklyVisitCheck}
                          weeklyHoldsClosures={
                            selectedStepId === 'wound-healed' ||
                            selectedStepId === 'patient-expired' ||
                            selectedStepId === 'patient-on-hold'
                          }
                          weeklyRescheduleConfirmed={weeklyRescheduleForPatient}
                          weeklyDischargeReviewSent={weeklyDischargeForPatient}
                          weeklyHoldsActionTaken={weeklyHoldsActionForPatient}
                          weeklyAppointmentRescheduled={
                            weeklyAppointmentRescheduledForPatient
                          }
                          onWeeklyConfirmReschedule={
                            weeklyVisitCheck &&
                            selectedStepId === 'patient-seen' &&
                            weeklyMissedVisitPending(weeklyVisitCheck) &&
                            !weeklyRescheduleForPatient &&
                            !weeklyAppointmentRescheduledForPatient
                              ? () =>
                                  setWeeklyRescheduleConfirmed((current) => ({
                                    ...current,
                                    [row.patientId]: true,
                                  }))
                              : undefined
                          }
                          onWeeklyConfirmAppointmentRescheduled={
                            weeklyVisitCheck &&
                            selectedStepId === 'patient-seen' &&
                            weeklyRescheduleForPatient &&
                            !weeklyDischargeForPatient &&
                            !weeklyAppointmentRescheduledForPatient
                              ? () =>
                                  setWeeklyAppointmentRescheduled((current) => ({
                                    ...current,
                                    [row.patientId]: true,
                                  }))
                              : undefined
                          }
                          onWeeklyEscalateDischargeReview={
                            weeklyVisitCheck &&
                            selectedStepId === 'patient-seen' &&
                            weeklyDischargeReviewDue(weeklyVisitCheck) &&
                            !weeklyDischargeForPatient
                              ? () =>
                                  setWeeklyDischargeReview((current) => ({
                                    ...current,
                                    [row.patientId]: true,
                                  }))
                              : undefined
                          }
                          onWeeklyHoldsAction={
                            weeklyVisitCheck &&
                            (selectedStepId === 'wound-healed' ||
                              selectedStepId === 'patient-expired' ||
                              selectedStepId === 'patient-on-hold') &&
                            !weeklyHoldsActionForPatient
                              ? () =>
                                  setWeeklyHoldsActionTaken((current) => ({
                                    ...current,
                                    [row.patientId]: true,
                                  }))
                              : undefined
                          }
                          referralPacketPdf={
                            selectedStepId === 'send-referral-provider'
                              ? schedulingHandoff?.samplePdf ??
                                referralPdfForPatient(row.patientId)
                              : undefined
                          }
                          onProviderAvailabilityConfirmed={
                            liveAvailability?.outcome === 'waiting'
                              ? () =>
                                  dispatch({
                                    type: 'CONFIRM_PROVIDER_AVAILABILITY',
                                    patientId: row.patientId,
                                    patientName: row.patientName,
                                    provider: selectedProvider,
                                    resolvedAt: opsTimestamp(),
                                  })
                              : undefined
                          }
                          onProviderAvailabilityTimeout={
                            liveAvailability?.outcome === 'waiting'
                              ? () =>
                                  dispatch({
                                    type: 'TIMEOUT_PROVIDER_AVAILABILITY',
                                    patientId: row.patientId,
                                    resolvedAt: opsTimestamp(),
                                  })
                              : undefined
                          }
                          onManualPlacementCompleted={
                            liveAvailability?.outcome === 'timeout'
                              ? () =>
                                  dispatch({
                                    type: 'COMPLETE_MANUAL_PLACEMENT',
                                    patientId: row.patientId,
                                    patientName: row.patientName,
                                    provider: selectedProvider,
                                    readyAt: opsTimestamp(),
                                  })
                              : undefined
                          }
                          isUnread={
                            (showUnreadAssignmentMessage &&
                              selectedStepId === 'assign-owner' &&
                              row.patientId ===
                                latestAssignmentHandoff?.patientId) ||
                            (showUnreadProviderMessage &&
                              selectedStepId ===
                                'confirm-provider-availability' &&
                              isLatestProviderAvailability) ||
                            (showUnreadHandoffMessage &&
                              selectedStepId === 'send-referral-provider' &&
                              row.patientId ===
                                latestSchedulingHandoff?.patientId) ||
                            (showUnreadProviderRecordsMessage &&
                              selectedStepId === 'update-monday-drk' &&
                              row.patientId ===
                                latestSchedulingHandoff?.patientId) ||
                            (showUnreadEodFollowUpMessage &&
                              selectedStepId === 'follow-up-case-manager' &&
                              row.patientId ===
                                state.latestEodFollowUpPatientId) ||
                            (showUnreadEodEscalationMessage &&
                              selectedStepId === 'escalate-unresolved-cases' &&
                              row.patientId ===
                                state.latestEodEscalationPatientId) ||
                            (showUnreadAssignmentHandoff &&
                              isAssignmentHandoffStep(selectedStepId) &&
                              row.patientId ===
                                latestAssignmentHandoff?.patientId) ||
                            (showUnreadProviderSelect &&
                              selectedStepId === 'select-provider' &&
                              row.patientId ===
                                latestAssignmentHandoff?.patientId) ||
                            (showUnreadIntakeDuplicate &&
                              isIntakeFollowUpStep(selectedStepId) &&
                              row.patientId === latestIntakeReview?.patientId)
                          }
                          liveInboxReferral={liveInboxReferral}
                          liveInboxStep={liveInboxStep}
                        />
                      </li>
                    )
                  })}
                </ul>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted stage-ops-steps__empty">
            No patients match this step with the current filters.
          </p>
        )}
      </div>
    </div>
  )
}
