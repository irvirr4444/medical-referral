import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, Search } from 'lucide-react'
import { useEscapeDismiss } from '../../hooks/useEscapeDismiss'
import { MicrostepList } from './MicrostepList'
import { StageFeedMessage } from './StageFeedMessage'
import { detailForPatientStep, feedForStep } from './ops'
import {
  CASE_MANAGER_OPTIONS,
  caseManagerNotification,
  caseManagerSuggestion,
  drkDraftForPatient,
  mondayRecordForPatient,
  referralSourceNotification,
} from './fixtures/caseManagerAssignments'
import { intakeDemoPatient } from './fixtures/intakeDemoPatients'
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

function currentOpsTimestamp() {
  return new Intl.DateTimeFormat('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date())
}

export function StagePatientSteps({
  stageId,
  microsteps,
}: {
  stageId: FlowOpsPageId
  microsteps: AutomationMicrostep[]
}) {
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

  const displayDays = useMemo(() => {
    if (
      selectedStepId !== 'assign-owner' ||
      !latestAssignmentNotification
    ) {
      return days
    }

    const latestRow = days
      .flatMap((day) => day.rows)
      .find(
        (row) => row.patientId === latestAssignmentNotification.patientId,
      )
    if (!latestRow) return days

    const remainingDays = days
      .map((day) => ({
        ...day,
        rows: day.rows.filter(
          (row) => row.patientId !== latestAssignmentNotification.patientId,
        ),
      }))
      .filter((day) => day.rows.length > 0)

    return [
      {
        key: 'latest-assignment-notification',
        label: 'Today',
        month: '—',
        day: '—',
        rows: [
          {
            ...latestRow,
            occurredAt: latestAssignmentNotification.occurredAt,
          },
        ],
      },
      ...remainingDays,
    ]
  }, [days, latestAssignmentNotification, selectedStepId])

  const selectStep = (stepId: string) => {
    if (selectedStepId === 'assign-owner' && stepId !== 'assign-owner') {
      setShowUnreadAssignmentMessage(false)
    }
    if (stepId === 'assign-owner') {
      setShowUnreadAssignmentMessage(assignmentNotificationUnread)
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
          attentionStepIds={
            assignmentNotificationUnread ? ['assign-owner'] : []
          }
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

        {displayDays.length ? (
          <ol
            className="stage-ops-step-feed"
            aria-label="Step updates"
            key={selectedStepId}
          >
            {displayDays.map((day) => (
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
                    const mondayRecord =
                      stageId === 'handoff' &&
                        selectedStepId === 'create-monday-record'
                        ? mondayRecordForPatient(
                          row.patientId,
                          row.patientName,
                          canonical,
                        )
                        : undefined
                    const drkDraft =
                      stageId === 'handoff' &&
                        selectedStepId === 'create-update-drk'
                        ? drkDraftForPatient(
                          row.patientId,
                          row.patientName,
                          canonical,
                        )
                        : undefined
                    return (
                      <li
                        key={`${row.patientId}-${row.stepId}`}
                        className="stage-ops-step-feed__item is-open"
                      >
                        <StageFeedMessage
                          summary={
                            drkDraft
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
                                      : row.summary
                          }
                          patientName={row.patientName}
                          status={
                            selectedStepId === 'determine-owner'
                              ? assignmentConfirmed
                                ? 'done'
                                : 'waiting'
                              : row.status
                          }
                          occurredAt={row.occurredAt}
                          detail={detail}
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
                                  occurredAt: currentOpsTimestamp(),
                                })
                                setAssignmentNotificationUnread(true)
                              }
                              : undefined
                          }
                          caseManagerNotification={notification}
                          referralNotification={referralNotification}
                          mondayRecord={mondayRecord}
                          drkDraft={drkDraft}
                          isUnread={
                            showUnreadAssignmentMessage &&
                            selectedStepId === 'assign-owner' &&
                            row.patientId ===
                            latestAssignmentNotification?.patientId
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
