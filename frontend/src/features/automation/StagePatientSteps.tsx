import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, Search } from 'lucide-react'
import { useEscapeDismiss } from '../../hooks/useEscapeDismiss'
import { useDemo } from '../../state/useDemo'
import { MicrostepList } from './MicrostepList'
import { StageFeedMessage } from './StageFeedMessage'
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
  referralSourceNotification,
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
  eodIsUnscheduled,
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
import type { FlowOpsPageId } from '../../data/flowOps'
import type { PatientStepStatus } from './ops/types'
import type { AutomationMicrostep } from './types'
import './StageOps.css'

const STATUS_FILTERS: Array<{
  id: PatientStepStatus
  meaning: string
}> = [
  { id: 'waiting', meaning: 'Needs confirmation' },
  { id: 'blocked', meaning: 'Stuck' },
  { id: 'current', meaning: 'In progress' },
  { id: 'done', meaning: 'Finished' },
]

const DEFAULT_STATUSES: PatientStepStatus[] = STATUS_FILTERS.map(
  (item) => item.id,
)

type StatusFilterValue = 'all' | PatientStepStatus
type StepDetail = ReturnType<typeof detailForPatientStep>

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
  const [latestAssignmentNotification, setLatestAssignmentNotification] =
    useState<{ patientId: string; occurredAt: string } | null>(null)
  const [assignmentNotificationUnread, setAssignmentNotificationUnread] =
    useState(false)
  const [showUnreadAssignmentMessage, setShowUnreadAssignmentMessage] =
    useState(false)
  const [providerAvailabilityUnread, setProviderAvailabilityUnread] =
    useState(false)
  const [showUnreadProviderMessage, setShowUnreadProviderMessage] =
    useState(false)
  const [showUnreadHandoffMessage, setShowUnreadHandoffMessage] =
    useState(false)
  const [showUnreadProviderRecordsMessage, setShowUnreadProviderRecordsMessage] =
    useState(false)
  const [eodEscalated, setEodEscalated] = useState<Record<string, boolean>>({})
  const [eodManualCmFollowUp, setEodManualCmFollowUp] = useState<
    Record<string, boolean>
  >({})
  const [eodFollowUpNotificationUnread, setEodFollowUpNotificationUnread] =
    useState(false)
  const [showUnreadEodFollowUpMessage, setShowUnreadEodFollowUpMessage] =
    useState(false)
  const [latestEodFollowUpNotification, setLatestEodFollowUpNotification] =
    useState<{ patientId: string } | null>(null)
  const [eodEscalationNotificationUnread, setEodEscalationNotificationUnread] =
    useState(false)
  const [showUnreadEodEscalationMessage, setShowUnreadEodEscalationMessage] =
    useState(false)
  const [latestEodEscalationNotification, setLatestEodEscalationNotification] =
    useState<{ patientId: string } | null>(null)
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

  useEffect(() => {
    setSelectedStepId(microsteps[0]?.id ?? '')
    setPatientQuery('')
    setStatusFilter('all')
    setStatusMenuOpen(false)
    setPartnerConfirmed({})
    setSelectedCaseManagers({})
    setConfirmedAssignments({})
    setLatestAssignmentNotification(null)
    setAssignmentNotificationUnread(false)
    setShowUnreadAssignmentMessage(false)
    setProviderAvailabilityUnread(false)
    setShowUnreadProviderMessage(false)
    setShowUnreadHandoffMessage(false)
    setShowUnreadProviderRecordsMessage(false)
    setEodEscalated({})
    setEodManualCmFollowUp({})
    setEodFollowUpNotificationUnread(false)
    setShowUnreadEodFollowUpMessage(false)
    setLatestEodFollowUpNotification(null)
    setEodEscalationNotificationUnread(false)
    setShowUnreadEodEscalationMessage(false)
    setLatestEodEscalationNotification(null)
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

  const statuses =
    statusFilter === 'all' ? DEFAULT_STATUSES : [statusFilter]

  const selectedStatusOption =
    statusFilter === 'all'
      ? null
      : STATUS_FILTERS.find((item) => item.id === statusFilter) ?? null

  const days = useMemo(
    () =>
      selectedStepId
        ? feedForStep(stageId, selectedStepId, { patientQuery, statuses })
        : [],
    [stageId, selectedStepId, patientQuery, statuses],
  )

  const waitingPartnerCount = useMemo(() => {
    if (selectedStepId !== 'confirm-referral-contacted') return 0
    return days.reduce(
      (count, day) =>
        count + day.rows.filter((row) => row.status === 'waiting').length,
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

  const displayDays = useMemo(() => {
    const latest =
      selectedStepId === 'assign-owner'
        ? latestAssignmentNotification
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
                : latestRow.status,
          summary:
            selectedStepId === 'update-monday-drk'
              ? recordsSummary
              : selectedStepId === 'send-referral-provider'
                ? referralSummary
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
    latestAssignmentNotification,
    latestProviderAvailability,
    latestSchedulingHandoff,
    selectedStepId,
  ])

  const filteredDisplayDays = useMemo(() => {
    if (selectedStepId === 'check-scheduling-status') {
      return displayDays
        .map((day) => ({
          ...day,
          rows: day.rows.filter((row) =>
            eodIsUnscheduled(eodSchedulingCheckForPatient(row.patientId)),
          ),
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
        .map(([patientId]) => {
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
        .map(([patientId]) => {
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
          rows: day.rows.filter((row) =>
            weeklyPatientSeenEligible(
              weeklyVisitCheckForPatient(row.patientId),
            ),
          ),
        }))
        .filter((day) => day.rows.length > 0)
    }
    if (selectedStepId === 'wound-healed') {
      return displayDays
        .map((day) => ({
          ...day,
          rows: day.rows.filter((row) =>
            weeklyWoundHealedEligible(
              weeklyVisitCheckForPatient(row.patientId),
            ),
          ),
        }))
        .filter((day) => day.rows.length > 0)
    }
    if (selectedStepId === 'patient-expired') {
      return displayDays
        .map((day) => ({
          ...day,
          rows: day.rows.filter((row) =>
            weeklyPatientExpiredEligible(
              weeklyVisitCheckForPatient(row.patientId),
            ),
          ),
        }))
        .filter((day) => day.rows.length > 0)
    }
    if (selectedStepId === 'patient-on-hold') {
      return displayDays
        .map((day) => ({
          ...day,
          rows: day.rows.filter((row) =>
            weeklyPatientOnHoldEligible(
              weeklyVisitCheckForPatient(row.patientId),
            ),
          ),
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
      setShowUnreadAssignmentMessage(assignmentNotificationUnread)
    }
    if (
      selectedStepId === 'confirm-provider-availability' &&
      stepId !== 'confirm-provider-availability'
    ) {
      setShowUnreadProviderMessage(false)
    }
    if (stepId === 'confirm-provider-availability') {
      setShowUnreadProviderMessage(providerAvailabilityUnread)
      setProviderAvailabilityUnread(false)
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
      setShowUnreadEodFollowUpMessage(eodFollowUpNotificationUnread)
      setEodFollowUpNotificationUnread(false)
    }
    if (
      selectedStepId === 'escalate-unresolved-cases' &&
      stepId !== 'escalate-unresolved-cases'
    ) {
      setShowUnreadEodEscalationMessage(false)
    }
    if (stepId === 'escalate-unresolved-cases') {
      setShowUnreadEodEscalationMessage(eodEscalationNotificationUnread)
      setEodEscalationNotificationUnread(false)
    }
    setSelectedStepId(stepId)
    if (stepId === 'assign-owner') {
      setAssignmentNotificationUnread(false)
    }
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
          <h2>{microsteps.length} steps</h2>
          <p className="muted">Select a step to see patient updates.</p>
        </div>
        <MicrostepList
          steps={microsteps}
          selectedStepId={selectedStepId}
          onSelect={selectStep}
          attentionStepIds={[
            ...(assignmentNotificationUnread ? ['assign-owner'] : []),
            ...(providerAvailabilityUnread
              ? ['confirm-provider-availability']
              : []),
            ...(state.providerRecordsUnread ? ['update-monday-drk'] : []),
            ...(eodFollowUpNotificationUnread
              ? ['follow-up-case-manager']
              : []),
            ...(eodEscalationNotificationUnread
              ? ['escalate-unresolved-cases']
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
                className={`stage-ops-steps__status-trigger${statusMenuOpen ? ' is-open' : ''}${selectedStatusOption ? ` is-${selectedStatusOption.id}` : ''}`}
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
                      aria-selected={statusFilter === 'all'}
                      className={`stage-ops-steps__status-option${statusFilter === 'all' ? ' is-selected' : ''}`}
                      onClick={() => pickStatus('all')}
                    >
                      All statuses
                    </button>
                  </li>
                  {STATUS_FILTERS.map((status) => (
                    <li key={status.id}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={statusFilter === status.id}
                        className={`stage-ops-steps__status-option is-${status.id}${statusFilter === status.id ? ' is-selected' : ''}`}
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
                    const detail = detailForRow(row.patientId)
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
                      selectedStepId === 'determine-owner'
                        ? suggestedCaseManager
                        : undefined
                    const assignmentConfirmed =
                      Boolean(confirmedAssignments[row.patientId])
                    const selectedCaseManagerEmail =
                      selectedCaseManagers[row.patientId] ??
                      suggestedCaseManager.email
                    const selectedCaseManager =
                      CASE_MANAGER_OPTIONS.find(
                        (manager) =>
                          manager.email === selectedCaseManagerEmail,
                      ) ?? suggestedCaseManager
                    const notification =
                      selectedStepId === 'assign-owner'
                        ? caseManagerNotification(
                            row.patientId,
                            row.patientName,
                            selectedCaseManager,
                          )
                        : undefined
                    const referralNotification =
                      stageId === 'handoff' &&
                      selectedStepId === 'notify-referral-source'
                        ? referralSourceNotification(
                            row.patientId,
                            row.patientName,
                            canonical,
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
                        selectedStepId === 'create-monday-record'
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
                        selectedStepId === 'create-update-drk'
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
                    return (
                      <li
                        key={`${row.patientId}-${row.stepId}`}
                        className="stage-ops-step-feed__item is-open"
                      >
                        <StageFeedMessage
                          summary={
                            noProviderLocationMatch
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
                              : referralNotification
                              ? `Referral source notified · ${referralNotification.ccName} CCd`
                              : selectedStepId === 'assign-owner'
                              ? `${selectedCaseManager.name} notified`
                              : selectedStepId === 'determine-owner'
                                ? assignmentConfirmed
                                  ? `${selectedCaseManager.name} confirmed as Case Manager`
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
                            noProviderLocationMatch
                              ? providerTerritoryResolution
                                ? 'done'
                                : 'waiting'
                              : selectedStepId === 'check-scheduling-status' &&
                                  eodSchedulingCheck &&
                                  (eodManualCmFollowUpForPatient ||
                                    eodEscalatedForPatient)
                                ? 'done'
                              : selectedStepId === 'follow-up-case-manager' &&
                                  eodSchedulingCheck
                                ? 'done'
                              : selectedStepId === 'escalate-unresolved-cases' &&
                                  eodSchedulingCheck
                                ? row.status === 'blocked'
                                  ? 'blocked'
                                  : eodEscalatedForPatient
                                    ? 'done'
                                    : row.status
                              : selectedStepId === 'patient-seen' &&
                                  weeklyVisitCheck
                                ? weeklyVisitCheck.visitOutcome === 'seen' ||
                                  weeklyRescheduleForPatient ||
                                  weeklyDischargeForPatient ||
                                  weeklyAppointmentRescheduledForPatient
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
                            selectedStepId === 'confirm-referral-contacted'
                              ? () =>
                                  setPartnerConfirmed((current) => ({
                                    ...current,
                                    [row.patientId]: true,
                                  }))
                              : undefined
                          }
                          assignmentSuggestion={assignmentSuggestion}
                          caseManagerOptions={CASE_MANAGER_OPTIONS}
                          selectedCaseManagerEmail={selectedCaseManagerEmail}
                          isAssignmentConfirmed={assignmentConfirmed}
                          onCaseManagerChange={
                            assignmentSuggestion
                              ? (email) =>
                                  setSelectedCaseManagers((current) => ({
                                    ...current,
                                    [row.patientId]: email,
                                  }))
                              : undefined
                          }
                          onConfirmAssignment={
                            assignmentSuggestion
                              ? () => {
                                  setConfirmedAssignments((current) => ({
                                    ...current,
                                    [row.patientId]: true,
                                  }))
                                  setLatestAssignmentNotification({
                                    patientId: row.patientId,
                                    occurredAt: opsTimestamp(),
                                  })
                                  setAssignmentNotificationUnread(true)
                                }
                              : undefined
                          }
                          caseManagerNotification={notification}
                          referralNotification={referralNotification}
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
                                  setProviderAvailabilityUnread(true)
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
                                  setProviderAvailabilityUnread(true)
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
                                  setLatestEodFollowUpNotification({
                                    patientId: row.patientId,
                                  })
                                  setEodFollowUpNotificationUnread(true)
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
                                  setLatestEodEscalationNotification({
                                    patientId: row.patientId,
                                  })
                                  setEodEscalationNotificationUnread(true)
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
                                latestAssignmentNotification?.patientId) ||
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
                                latestEodFollowUpNotification?.patientId) ||
                            (showUnreadEodEscalationMessage &&
                              selectedStepId === 'escalate-unresolved-cases' &&
                              row.patientId ===
                                latestEodEscalationNotification?.patientId)
                          }
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
