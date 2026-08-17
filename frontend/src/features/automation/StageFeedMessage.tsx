import { useEffect, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { ArtifactFieldInput, ArtifactSections } from './ArtifactSections'
import type { ArtifactField } from './types'
import {
  actionLabel,
  overdueLabel,
  remainingLabel,
  slaLabel,
} from './confirmationTimers'
import type { ActionTimer } from '../../types'
import {
  intakeEditKey,
  isMultilineIntakeField,
  overlayIntakeFieldValues,
} from './overlayIntakeDetail'
import { IntakePdfPreview } from './IntakePdfPreview'
import { statusMeaning } from './StagePatientStepDetail'
import { parseOpsDate, type detailForPatientStep } from './ops'
import {
  referralPatientSummary,
  type CaseManagerNotification,
  type CaseManagerOption,
  type CaseManagerSuggestion,
  type DrkDraftRecord,
  type MondayRecord,
  type ReferralSourceNotification,
} from './fixtures/caseManagerAssignments'
import { intakeDemoPatient } from './fixtures/intakeDemoPatients'
import type { EodSchedulingCheckRecord } from './fixtures/eodSchedulingCheck'
import {
  eodCmAutoNotifyDue,
  eodCmFollowUpMessage,
  eodCmNotifyPending,
  eodEscalationConfirmLabel,
  eodEscalationDue,
  eodManagementEscalationMessage,
  eodSchedulingHoursMeta,
  eodSchedulingStatusLabel,
} from './fixtures/eodSchedulingCheck'
import type { WeeklyVisitCheckRecord } from './fixtures/weeklyVisitCheck'
import {
  weeklyDischargeReviewDue,
  weeklyHoldsClosuresActionLabel,
  weeklyHoldsClosuresMessage,
  weeklyHoldsClosuresSummary,
  weeklyMissedVisitMessage,
  weeklyMissedVisitPending,
  weeklyOutcomePanelLabel,
} from './fixtures/weeklyVisitCheck'
import type { ProviderOption } from './fixtures/providerAssignments'
import type {
  PatientSchedulingRecord,
  SchedulingBlockerReason,
  SchedulingHandoff,
  SchedulingSlot,
} from '../../types'
import {
  SCHEDULING_BLOCKER_LABEL,
  openSlotCount,
  schedulingBlockerLabel,
  selectedSlot,
} from './fixtures/patientSchedules'
import './StageOps.css'

type StepDetail = ReturnType<typeof detailForPatientStep>

function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs)
    return () => window.clearInterval(id)
  }, [intervalMs])
  return now
}

export function actionTimerAriaSuffix(timer?: ActionTimer | null) {
  if (!timer || timer.status === 'resolved') return ''
  if (timer.status === 'overdue') return ' · Immediate attention · overdue'
  if (timer.status === 'warning') return ' · Due soon'
  return ''
}

function ActionSlaAlert({
  timer,
  patientName,
}: {
  timer: ActionTimer
  patientName: string
}) {
  const now = useNow()
  if (timer.status === 'resolved') return null

  const action = actionLabel(timer.actionId)
  const sla = slaLabel(timer.actionId)

  if (timer.status === 'overdue') {
    return (
      <div
        className="stage-ops-step-feed__sla is-overdue"
        aria-label={`Immediate attention: ${action} for ${patientName} is overdue`}
      >
        <p className="stage-ops-step-feed__sla-flag">
          <span className="stage-ops-step-feed__sla-badge">
            Immediate attention
          </span>
          <span className="stage-ops-step-feed__sla-clock">
            {overdueLabel(timer, now)} overdue
          </span>
        </p>
        <p className="stage-ops-step-feed__sla-action">
          {action} · {patientName}
        </p>
        <p className="stage-ops-step-feed__sla-meta">
          {sla} SLA missed · confirm now to clear the alert
        </p>
      </div>
    )
  }

  const dueSoon = timer.status === 'warning'
  return (
    <div className={`stage-ops-step-feed__sla is-${timer.status}`}>
      <p className="stage-ops-step-feed__sla-flag">
        {dueSoon ? (
          <span className="stage-ops-step-feed__sla-badge is-warning">
            Due soon
          </span>
        ) : null}
        <span className="stage-ops-step-feed__sla-clock">
          {remainingLabel(timer, now)} left
        </span>
      </p>
      <p className="stage-ops-step-feed__sla-meta">
        {action} · {sla} SLA
      </p>
    </div>
  )
}

function TimerRemainingValue({ timer }: { timer: ActionTimer }) {
  const now = useNow()
  if (timer.status === 'overdue') return <>Overdue</>
  return <>{remainingLabel(timer, now)}</>
}

function isHiddenProofField(label: string) {
  return (
    /attachment|pdf|file name|filename|message id|attachment id|received|result/i.test(
      label,
    ) || /^(outcome|status|timestamp)$/i.test(label.trim())
  )
}

function InlineExpandableText({
  text,
  limit = 220,
}: {
  text: string
  limit?: number
}) {
  const [expanded, setExpanded] = useState(false)
  const needsLimit = text.length > limit
  const visibleText =
    needsLimit && !expanded
      ? `${text.slice(0, limit).trimEnd()}…`
      : text

  return (
    <>
      {visibleText}
      {needsLimit ? (
        <>
          {' '}
          <button
            type="button"
            className="stage-ops-step-feed__inline-expand"
            aria-expanded={expanded}
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded ? 'less' : 'more'}
          </button>
        </>
      ) : null}
    </>
  )
}

function MondayRecordView({ record }: { record: MondayRecord }) {
  const fields: Array<[string, string, boolean?]> = [
    ['Patient name', record.data.patient_name],
    ['Date of birth', record.data.date_of_birth],
    ['Contact number', record.data.contact_number],
    ['Patient address', record.data.patient_address],
    [
      'Home health or hospice agency',
      record.data.home_health_or_hospice_agency,
    ],
    [
      'Wound or clinical information',
      record.data.wound_or_clinical_information,
    ],
    ['Insurance information', record.data.insurance_information],
    [
      'Case manager',
      `${record.data.case_manager.name} · ${record.data.case_manager.email}`,
    ],
    ['Sent by', record.data.sent_by],
    ['Referral status', record.data.referral_status, Boolean(record.data.assigned_provider)],
  ]
  if (record.data.assigned_provider) {
    fields.push(
      ['Assigned provider', record.data.assigned_provider, true],
      ['Provider NPI', record.data.provider_npi ?? 'Not documented', true],
      ['Provider city', record.data.provider_city ?? 'Not documented', true],
    )
  }

  return (
    <div
      className="stage-ops-step-feed__monday-record"
      aria-label="Monday.com record details"
    >
      <dl className="stage-ops-step-feed__monday-fields">
        {fields.map(([label, value, updated]) => (
          <div
            key={label}
            className={`stage-ops-step-feed__decision-item${
              /^(Home health|Wound|Insurance|Case manager|Assigned provider)/i.test(
                label,
              )
                ? ' is-wide'
                : ''
            }${updated ? ' is-updated' : ''}`}
          >
            <dt>{label}</dt>
            <dd>
              {label === 'Wound or clinical information' ? (
                <InlineExpandableText text={value} />
              ) : (
                value
              )}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

function DrkDraftView({
  draft,
  detailsOpen,
  onToggleDetails,
}: {
  draft: DrkDraftRecord
  detailsOpen: boolean
  onToggleDetails: () => void
}) {
  const assignedProvider = draft.referral.find(
    (field) => field.label === 'Assigned provider',
  )?.value
  const providerNpi = draft.referral.find(
    (field) => field.label === 'Provider NPI',
  )?.value

  return (
    <div
      className="stage-ops-step-feed__drk"
      aria-label="DRK chart draft details"
    >
      <dl className="stage-ops-step-feed__drk-summary">
        {[
          [
            'Patient',
            [
              draft.demographics.find((field) => field.label === 'First name')
                ?.value,
              draft.demographics.find((field) => field.label === 'Last name')
                ?.value,
            ]
              .filter(Boolean)
              .join(' '),
          ],
          [
            'Date of birth',
            draft.demographics.find((field) => field.label === 'Date of birth')
              ?.value ?? 'Not documented',
          ],
          [
            'Primary phone',
            draft.contact.find((field) => field.label === 'Primary phone')
              ?.value ?? 'Not documented',
          ],
          [
            'Address',
            draft.primaryAddress.find((field) => field.label === 'Address')
              ?.value ?? 'Not documented',
          ],
          [
            'Home health',
            draft.admission.find((field) => field.label === 'Home health query')
              ?.value ?? 'Not documented',
          ],
          [
            'Insurance',
            draft.insurance.find((field) => field.label === 'Payer query')
              ?.value ?? 'Not documented',
          ],
          ...(assignedProvider
            ? [
                ['Assigned provider', assignedProvider],
                ['Provider NPI', providerNpi ?? 'Not documented'],
              ]
            : []),
        ].map(([label, value]) => (
          <div
            key={label}
            className={
              label === 'Assigned provider' || label === 'Provider NPI'
                ? 'is-updated'
                : undefined
            }
          >
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <button
        type="button"
        className={`stage-ops-step-feed__details-toggle${
          detailsOpen ? ' is-open' : ''
        }`}
        aria-expanded={detailsOpen}
        onClick={onToggleDetails}
      >
        <span>
          {detailsOpen ? 'Hide full DRK details' : 'Show full DRK details'}
        </span>
        <ChevronDown size={16} aria-hidden="true" />
      </button>
      {detailsOpen ? (
        <div className="stage-ops-step-feed__drk-sections">
          {[
            ['Demographics', draft.demographics],
            ['Primary address', draft.primaryAddress],
            ['Contact', draft.contact],
            ['Admission', draft.admission],
            ['Referral', draft.referral],
            ['Insurance', draft.insurance],
          ].map(([title, fields]) => (
            <section key={title as string}>
              <h5>{title as string}</h5>
              <dl>
                {(fields as Array<{ label: string; value: string }>).map(
                  (field) => (
                    <div key={field.label}>
                      <dt>{field.label}</dt>
                      <dd>
                        {field.label === 'Clinical information' ? (
                          <InlineExpandableText
                            text={field.value}
                            limit={180}
                          />
                        ) : (
                          field.value
                        )}
                      </dd>
                    </div>
                  ),
                )}
              </dl>
            </section>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function ReferralHandoffPanel({
  patientId,
  patientName,
  provider,
  samplePdf,
}: {
  patientId: string
  patientName: string
  provider: SchedulingHandoff['provider']
  samplePdf?: string
}) {
  const patient = referralPatientSummary(
    patientId,
    patientName,
    intakeDemoPatient(patientId)?.canonical,
  )
  const providerMeta = [
    provider.city,
    provider.npi ? `NPI ${provider.npi}` : undefined,
    provider.phone,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <div className="stage-ops-step-feed__referral-handoff">
      <div className="stage-ops-step-feed__referral-handoff-details">
        <section
          className="stage-ops-step-feed__referral-handoff-row"
          aria-label="Patient referral details"
        >
          <p className="stage-ops-step-feed__partner-label">Patient</p>
          <p className="stage-ops-step-feed__referral-handoff-name">
            {patient.name}
          </p>
          <p className="stage-ops-step-feed__referral-handoff-meta">
            DOB {patient.dateOfBirth} · {patient.location} · {patient.phone}
          </p>
        </section>

        <section className="stage-ops-step-feed__referral-handoff-row">
          <p className="stage-ops-step-feed__partner-label">Provider</p>
          <p className="stage-ops-step-feed__referral-handoff-name">
            {provider.name}
          </p>
          {providerMeta ? (
            <p className="stage-ops-step-feed__referral-handoff-meta">
              {providerMeta}
            </p>
          ) : null}
        </section>
      </div>

      {samplePdf ? (
        <div className="stage-ops-step-feed__referral-handoff-pdf">
          <p className="stage-ops-step-feed__partner-label">Referral</p>
          <IntakePdfPreview samplePdf={samplePdf} />
        </div>
      ) : null}
    </div>
  )
}

const BLOCKER_REASONS: SchedulingBlockerReason[] = [
  'patient_declined',
  'patient_unavailable',
  'slots_exhausted',
]

function groupSlots(slots: SchedulingSlot[]) {
  const groups: { dateLabel: string; slots: SchedulingSlot[] }[] = []
  for (const item of slots) {
    const last = groups[groups.length - 1]
    if (last && last.dateLabel === item.dateLabel) last.slots.push(item)
    else groups.push({ dateLabel: item.dateLabel, slots: [item] })
  }
  return groups
}

function SchedulingPanel({
  record,
  onSelectSlot,
  onSchedule,
  onRecordBlocker,
}: {
  record: PatientSchedulingRecord
  onSelectSlot?: (slotId: string) => void
  onSchedule?: () => void
  onRecordBlocker?: (reason: SchedulingBlockerReason) => void
}) {
  const [showReasons, setShowReasons] = useState(false)
  const chosen = selectedSlot(record)
  const openCount = openSlotCount(record)
  const providerMeta = [
    record.provider.city,
    record.provider.npi ? `NPI ${record.provider.npi}` : undefined,
    record.provider.phone,
  ]
    .filter(Boolean)
    .join(' · ')
  const routeLabel =
    record.route === 'manual_placement' ? 'Placed manually' : 'Provider confirmed'
  const canSchedule = Boolean(onSchedule && chosen && chosen.status === 'open')

  return (
    <div
      className={`stage-ops-step-feed__schedule is-${record.status}`}
      role="region"
      aria-label="Schedule patient"
    >
      <ol className="stage-ops-step-feed__schedule-strip">
        <li className={record.referralSent ? 'is-done' : 'is-pending'}>
          {record.referralSent ? 'Referral sent' : 'Referral ready'}
        </li>
        <li className="is-done">{routeLabel}</li>
        <li
          className={
            record.status === 'scheduled'
              ? 'is-done'
              : record.status === 'blocked'
                ? 'is-blocked'
                : 'is-current'
          }
        >
          {record.status === 'scheduled'
            ? 'Patient scheduled'
            : record.status === 'blocked'
              ? 'Scheduling blocked'
              : 'Schedule within 24–48h'}
        </li>
      </ol>

      <section className="stage-ops-step-feed__schedule-provider">
        <p className="stage-ops-step-feed__partner-label">Provider</p>
        <strong>{record.provider.name}</strong>
        {providerMeta ? <p>{providerMeta}</p> : null}
        <p className="stage-ops-step-feed__schedule-sync">
          Availability synced {record.syncedAt}
        </p>
      </section>

      {record.status === 'scheduled' ? (
        <div className="stage-ops-step-feed__schedule-receipt">
          <p className="stage-ops-step-feed__schedule-receipt-kicker">
            Patient scheduled
          </p>
          <strong>
            {record.appointmentDate}
            {record.appointmentTime ? ` at ${record.appointmentTime}` : ''}
          </strong>
          <p>
            {record.provider.name}
            {record.provider.city ? ` · ${record.provider.city}` : ''}
          </p>
          <p>Monday.com appointment date updated · entered end-of-day monitoring</p>
        </div>
      ) : record.status === 'blocked' ? (
        <div className="stage-ops-step-feed__schedule-receipt is-blocked">
          <p className="stage-ops-step-feed__schedule-receipt-kicker">
            Needs a new window
          </p>
          <strong>{schedulingBlockerLabel(record.blockerReason)}</strong>
          <p>Patient stays unscheduled for end-of-day follow-up</p>
        </div>
      ) : (
        <>
          <section
            className="stage-ops-step-feed__schedule-slots"
            aria-label="Provider availability"
          >
            <p className="stage-ops-step-feed__partner-label">
              {openCount} open slot{openCount === 1 ? '' : 's'}
            </p>
            {groupSlots(record.slots).map((group) => (
              <div
                key={group.dateLabel}
                className="stage-ops-step-feed__schedule-day"
              >
                <p className="stage-ops-step-feed__schedule-day-label">
                  {group.dateLabel}
                </p>
                <div className="stage-ops-step-feed__schedule-slot-row">
                  {group.slots.map((item) => {
                    const selected = record.selectedSlotId === item.id
                    const unavailable = item.status !== 'open'
                    return (
                      <button
                        key={item.id}
                        type="button"
                        className={`stage-ops-step-feed__schedule-slot${
                          selected ? ' is-selected' : ''
                        }${unavailable ? ' is-unavailable' : ''}`}
                        disabled={unavailable || !onSelectSlot}
                        aria-pressed={selected}
                        aria-label={
                          unavailable
                            ? `${group.dateLabel} ${item.timeLabel}, unavailable${
                                item.unavailableReason
                                  ? `, ${item.unavailableReason}`
                                  : ''
                              }`
                            : `${group.dateLabel} ${item.timeLabel}`
                        }
                        onClick={() => onSelectSlot?.(item.id)}
                      >
                        <span>{item.timeLabel}</span>
                        {unavailable && item.unavailableReason ? (
                          <small>{item.unavailableReason}</small>
                        ) : null}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </section>

          <div className="stage-ops-step-feed__schedule-actions">
            <button
              type="button"
              className={`stage-ops-step-feed__confirm${
                canSchedule ? ' is-actionable' : ''
              }`}
              onClick={onSchedule}
              disabled={!canSchedule}
            >
              Schedule patient
            </button>
            {onRecordBlocker ? (
              <button
                type="button"
                className="stage-ops-step-feed__availability-timeout"
                onClick={() => setShowReasons((open) => !open)}
                aria-expanded={showReasons}
              >
                No suitable time
              </button>
            ) : null}
          </div>

          {showReasons && onRecordBlocker ? (
            <div
              className="stage-ops-step-feed__schedule-reasons"
              aria-label="Scheduling blocker"
            >
              {BLOCKER_REASONS.map((reason) => (
                <button
                  key={reason}
                  type="button"
                  className="stage-ops-step-feed__schedule-reason"
                  onClick={() => onRecordBlocker(reason)}
                >
                  {SCHEDULING_BLOCKER_LABEL[reason]}
                </button>
              ))}
            </div>
          ) : null}
        </>
      )}
    </div>
  )
}

function EodPartiesSection({
  record,
  patientName,
  showScheduling = false,
}: {
  record: EodSchedulingCheckRecord
  patientName?: string
  showScheduling?: boolean
}) {
  return (
    <section className="stage-ops-step-feed__eod-check-parties">
      {patientName ? (
        <div className="stage-ops-step-feed__referral-handoff-row">
          <p className="stage-ops-step-feed__partner-label">Patient</p>
          <p className="stage-ops-step-feed__referral-handoff-name">
            {patientName}
          </p>
        </div>
      ) : null}

      {showScheduling ? (
        <div className="stage-ops-step-feed__referral-handoff-row">
          <p className="stage-ops-step-feed__partner-label">Scheduling</p>
          <p
            className="stage-ops-step-feed__referral-handoff-name"
            aria-label="Patient scheduling status"
          >
            {eodSchedulingStatusLabel(record)}
          </p>
        </div>
      ) : null}

      <div className="stage-ops-step-feed__eod-check-party-grid">
        <div className="stage-ops-step-feed__referral-handoff-row">
          <p className="stage-ops-step-feed__partner-label">Provider</p>
          <p className="stage-ops-step-feed__referral-handoff-name">
            {record.providerName}
          </p>
        </div>

        <div className="stage-ops-step-feed__referral-handoff-row">
          <p className="stage-ops-step-feed__partner-label">Case manager</p>
          <p className="stage-ops-step-feed__referral-handoff-name">
            {record.caseManagerName}
          </p>
        </div>
      </div>
      <p className="stage-ops-step-feed__referral-handoff-meta">
        {showScheduling
          ? eodSchedulingHoursMeta(record)
          : `Selected ${record.providerSelectedAt}`}
      </p>
    </section>
  )
}

function EodSchedulingCheckPanel({
  record,
  escalatedToManagement = false,
  manualCmFollowUpSent = false,
  onFollowUpWithCaseManager,
  onEscalateToManagement,
}: {
  record: EodSchedulingCheckRecord
  escalatedToManagement?: boolean
  manualCmFollowUpSent?: boolean
  onFollowUpWithCaseManager?: () => void
  onEscalateToManagement?: () => void
}) {
  const cmNotified = eodCmAutoNotifyDue(record)
  const cmNotifyPending = eodCmNotifyPending(record)
  const escalationDue = eodEscalationDue(record)
  const escalated = escalatedToManagement || Boolean(record.escalatedToManagement)
  const escalationLabel = eodEscalationConfirmLabel(record)
  const showEarlyActions =
    (cmNotifyPending &&
      ((!manualCmFollowUpSent && onFollowUpWithCaseManager) ||
        (!escalated && onEscalateToManagement))) ||
    false

  return (
    <div
      className={`stage-ops-step-feed__eod-check${
        record.overdue ? ' is-overdue' : ''
      }`}
      aria-label="Unscheduled referral review"
    >
      <EodPartiesSection record={record} />

      {cmNotifyPending ? (
        <>
          {!escalated && !manualCmFollowUpSent ? (
            <p className="stage-ops-step-feed__eod-check-notify is-pending">
              Case manager will be notified automatically at 24 hours
            </p>
          ) : null}

          {manualCmFollowUpSent ? (
            <p className="stage-ops-step-feed__eod-check-notify is-confirmed">
              {record.caseManagerName} notified on Teams
            </p>
          ) : null}

          {escalated ? (
            <p className="stage-ops-step-feed__eod-check-notify is-confirmed">
              {escalationLabel}
            </p>
          ) : null}

          {showEarlyActions ? (
            <div className="stage-ops-step-feed__availability-actions">
              {!manualCmFollowUpSent && onFollowUpWithCaseManager ? (
                <button
                  type="button"
                  className="stage-ops-step-feed__confirm is-actionable"
                  onClick={onFollowUpWithCaseManager}
                >
                  Follow up with case manager
                </button>
              ) : null}
              {!escalated && onEscalateToManagement ? (
                <button
                  type="button"
                  className="stage-ops-step-feed__confirm is-actionable"
                  onClick={onEscalateToManagement}
                >
                  Escalate to Nicole
                </button>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}

      {cmNotified ? (
        <p className="stage-ops-step-feed__eod-check-notify">
          {record.caseManagerName} notified on Teams automatically
        </p>
      ) : null}

      {cmNotified && !escalationDue ? (
        escalated ? (
          <p className="stage-ops-step-feed__eod-check-notify is-confirmed">
            {escalationLabel}
          </p>
        ) : onEscalateToManagement ? (
          <div className="stage-ops-step-feed__availability-actions">
            <button
              type="button"
              className="stage-ops-step-feed__confirm is-actionable"
              onClick={onEscalateToManagement}
            >
              Escalate to Nicole
            </button>
          </div>
        ) : null
      ) : null}

      {escalationDue ? (
        escalated ? (
          <p className="stage-ops-step-feed__eod-check-notify is-confirmed">
            {escalationLabel}
          </p>
        ) : onEscalateToManagement ? (
          <div className="stage-ops-step-feed__availability-actions">
            <button
              type="button"
              className="stage-ops-step-feed__confirm is-actionable"
              onClick={onEscalateToManagement}
            >
              Escalate to management
            </button>
          </div>
        ) : null
      ) : null}
    </div>
  )
}

function EodCmFollowUpPanel({
  record,
  patientName,
  manualFollowUp = false,
}: {
  record: EodSchedulingCheckRecord
  patientName: string
  manualFollowUp?: boolean
}) {
  const message = eodCmFollowUpMessage(record, patientName)

  return (
    <div
      className="stage-ops-step-feed__eod-followup"
      aria-label="Case manager follow-up"
    >
      <p className="stage-ops-step-feed__eod-check-notify is-confirmed">
        {manualFollowUp
          ? `${record.caseManagerName} notified on Teams`
          : `${record.caseManagerName} notified on Teams automatically at 24 hours`}
      </p>

      <EodPartiesSection
        record={record}
        patientName={patientName}
        showScheduling
      />

      <div
        className="stage-ops-step-feed__eod-followup-message"
        aria-label="Teams follow-up message"
      >
        <p className="stage-ops-step-feed__partner-label">Teams</p>
        <p className="stage-ops-step-feed__notification-message">{message}</p>
      </div>
    </div>
  )
}

function EodEscalationPanel({
  record,
  patientName,
}: {
  record: EodSchedulingCheckRecord
  patientName: string
}) {
  const message = eodManagementEscalationMessage(record, patientName)
  const escalationLabel = eodEscalationConfirmLabel(record)

  return (
    <div
      className="stage-ops-step-feed__eod-escalation"
      aria-label="Management escalation"
    >
      <p className="stage-ops-step-feed__eod-check-notify is-confirmed">
        {escalationLabel}
      </p>

      <div
        className="stage-ops-step-feed__eod-followup-message"
        aria-label="Management escalation email"
      >
        <p className="stage-ops-step-feed__partner-label">Email</p>
        <EodPartiesSection
          record={record}
          patientName={patientName}
          showScheduling
        />
        <p className="stage-ops-step-feed__notification-message">{message}</p>
      </div>
    </div>
  )
}

function WeeklyPartiesSection({
  record,
  patientName,
}: {
  record: WeeklyVisitCheckRecord
  patientName?: string
}) {
  return (
    <section className="stage-ops-step-feed__eod-check-parties">
      {patientName ? (
        <div className="stage-ops-step-feed__referral-handoff-row">
          <p className="stage-ops-step-feed__partner-label">Patient</p>
          <p className="stage-ops-step-feed__referral-handoff-name">
            {patientName}
          </p>
        </div>
      ) : null}
      <div className="stage-ops-step-feed__eod-check-party-grid">
        <div className="stage-ops-step-feed__referral-handoff-row">
          <p className="stage-ops-step-feed__partner-label">Provider</p>
          <p className="stage-ops-step-feed__referral-handoff-name">
            {record.providerName}
          </p>
        </div>
        <div className="stage-ops-step-feed__referral-handoff-row">
          <p className="stage-ops-step-feed__partner-label">Case manager</p>
          <p className="stage-ops-step-feed__referral-handoff-name">
            {record.caseManagerName}
          </p>
        </div>
      </div>
      <p className="stage-ops-step-feed__referral-handoff-meta">
        {patientName
          ? `Not seen · ${record.consecutiveNotSeen} consecutive week${
              record.consecutiveNotSeen === 1 ? '' : 's'
            } · last visit ${record.lastVisitAt}`
          : `Last visit ${record.lastVisitAt}`}
      </p>
    </section>
  )
}

function WeeklyVisitCheckPanel({
  record,
  patientName,
  rescheduleConfirmed = false,
  dischargeReviewSent = false,
  appointmentRescheduled = false,
  onConfirmReschedule,
  onEscalateDischargeReview,
  onConfirmAppointmentRescheduled,
}: {
  record: WeeklyVisitCheckRecord
  patientName: string
  rescheduleConfirmed?: boolean
  dischargeReviewSent?: boolean
  appointmentRescheduled?: boolean
  onConfirmReschedule?: () => void
  onEscalateDischargeReview?: () => void
  onConfirmAppointmentRescheduled?: () => void
}) {
  const pendingMiss = weeklyMissedVisitPending(record)
  const dischargeDue = weeklyDischargeReviewDue(record)
  const reviewQueued =
    dischargeReviewSent || Boolean(record.dischargeReviewQueued)
  const showMissFollowUp =
    (pendingMiss && (rescheduleConfirmed || appointmentRescheduled)) ||
    (dischargeDue && reviewQueued)
  const needsAttention =
    record.visitOutcome === 'not_seen' ||
    record.visitOutcome === 'on_hold' ||
    record.visitOutcome === 'healed' ||
    record.visitOutcome === 'expired'

  return (
    <div
      className={`stage-ops-step-feed__weekly-check${
        needsAttention ? ' is-attention' : ''
      }`}
      aria-label="Weekly visit review"
    >
      {!showMissFollowUp ? <WeeklyPartiesSection record={record} /> : null}

      {appointmentRescheduled ? (
        <p className="stage-ops-step-feed__eod-check-notify is-confirmed">
          Rescheduled confirmed
        </p>
      ) : pendingMiss ? (
        <>
          {rescheduleConfirmed ? (
            <p className="stage-ops-step-feed__eod-check-notify is-confirmed">
              Marked NOT seen · reschedule weekly
            </p>
          ) : !onConfirmReschedule ? (
            <p className="stage-ops-step-feed__eod-check-notify is-pending">
              Not seen · reschedule weekly
            </p>
          ) : (
            <div className="stage-ops-step-feed__availability-actions">
              <button
                type="button"
                className="stage-ops-step-feed__confirm is-actionable"
                onClick={onConfirmReschedule}
              >
                Mark NOT seen · reschedule
              </button>
            </div>
          )}
        </>
      ) : null}

      {dischargeDue ? (
        reviewQueued ? (
          <p className="stage-ops-step-feed__eod-check-notify is-confirmed">
            Queued for DC · noncompliance
          </p>
        ) : onEscalateDischargeReview ? (
          <div className="stage-ops-step-feed__availability-actions">
            <button
              type="button"
              className="stage-ops-step-feed__confirm is-actionable"
              onClick={onEscalateDischargeReview}
            >
              Escalate for DC (noncompliance)
            </button>
          </div>
        ) : null
      ) : null}

      {showMissFollowUp ? (
        <div
          className="stage-ops-step-feed__eod-followup-message"
          aria-label={
            dischargeDue || reviewQueued
              ? 'Discharge review message'
              : 'Teams reschedule message'
          }
        >
          <WeeklyPartiesSection record={record} patientName={patientName} />
          <p className="stage-ops-step-feed__notification-message">
            {weeklyMissedVisitMessage(record, patientName)}
          </p>
        </div>
      ) : null}

      {pendingMiss &&
      rescheduleConfirmed &&
      !appointmentRescheduled &&
      onConfirmAppointmentRescheduled ? (
        <div className="stage-ops-step-feed__availability-actions">
          <button
            type="button"
            className="stage-ops-step-feed__confirm is-actionable"
            onClick={onConfirmAppointmentRescheduled}
          >
            Confirm rescheduled
          </button>
        </div>
      ) : null}
    </div>
  )
}

function WeeklyHoldsClosuresPanel({
  record,
  patientName,
  actionTaken = false,
  onTakeAction,
}: {
  record: WeeklyVisitCheckRecord
  patientName: string
  actionTaken?: boolean
  onTakeAction?: () => void
}) {
  const message = weeklyHoldsClosuresMessage(record, patientName)
  const confirmed =
    actionTaken ||
    Boolean(record.movedToHolds || record.closureActionTaken)
  const actionLabel = weeklyHoldsClosuresActionLabel(record)
  const confirmLabel = weeklyHoldsClosuresSummary(record, true)
  const panelLabel = weeklyOutcomePanelLabel(record)

  return (
    <div
      className="stage-ops-step-feed__eod-escalation"
      aria-label={panelLabel}
    >
      {confirmed ? (
        <p className="stage-ops-step-feed__eod-check-notify is-confirmed">
          {confirmLabel}
        </p>
      ) : onTakeAction ? (
        <div className="stage-ops-step-feed__availability-actions">
          <button
            type="button"
            className="stage-ops-step-feed__confirm is-actionable"
            onClick={onTakeAction}
          >
            {actionLabel}
          </button>
        </div>
      ) : (
        <p className="stage-ops-step-feed__eod-check-notify is-pending">
          {weeklyHoldsClosuresSummary(record, false)}
        </p>
      )}

      {confirmed ? (
        <div
          className="stage-ops-step-feed__eod-followup-message"
          aria-label={`${panelLabel} message`}
        >
          <p className="stage-ops-step-feed__partner-label">
            {record.visitOutcome === 'on_hold' ? 'Holds list' : 'Email'}
          </p>
          <WeeklyPartiesSection record={record} />
          <p className="stage-ops-step-feed__notification-message">{message}</p>
        </div>
      ) : (
        <WeeklyPartiesSection record={record} />
      )}
    </div>
  )
}

/** Always-open Slack-style message: skim in under 3 seconds. */
export function StageFeedMessage({
  summary,
  patientName,
  status,
  statusLabel,
  occurredAt,
  detail,
  showPdf = false,
  isPartnerConfirmed = false,
  onConfirmPartner,
  assignmentSuggestion,
  caseManagerOptions = [],
  selectedCaseManagerEmail,
  isAssignmentConfirmed = false,
  onCaseManagerChange,
  onConfirmAssignment,
  caseManagerNotification,
  referralNotification,
  mondayRecord,
  drkDraft,
  providerRecommendation,
  providerOptions = [],
  providerSelectionLocation,
  fallbackProviderOptions = [],
  providerTerritoryResolution,
  selectedProviderId,
  isProviderConfirmed = false,
  onProviderChange,
  onConfirmProvider,
  onAssignFallbackProvider,
  onDischargePatient,
  providerAvailability,
  onProviderAvailabilityConfirmed,
  onProviderAvailabilityTimeout,
  onManualPlacementCompleted,
  schedulingHandoff,
  patientSchedule,
  onSelectSchedulingSlot,
  onCompletePatientSchedule,
  onRecordSchedulingBlocker,
  referralPacketPdf,
  eodSchedulingCheck,
  eodFollowUp = false,
  eodEscalation = false,
  eodManualFollowUp = false,
  eodEscalatedToManagement = false,
  eodManualCmFollowUpSent = false,
  onEodFollowUpWithCaseManager,
  onEodEscalateToManagement,
  weeklyVisitCheck,
  weeklyHoldsClosures = false,
  weeklyRescheduleConfirmed = false,
  weeklyDischargeReviewSent = false,
  weeklyHoldsActionTaken = false,
  weeklyAppointmentRescheduled = false,
  onWeeklyConfirmReschedule,
  onWeeklyEscalateDischargeReview,
  onWeeklyHoldsAction,
  onWeeklyConfirmAppointmentRescheduled,
  isUnread = false,
  intakeEditable = false,
  isIntakeConfirmed = false,
  onIntakeFieldChange,
  onIntakeSectionRowsReplace,
  onConfirmIntakeReview,
  onReopenIntakeReview,
  onScopePatient,
  actionTimer,
}: {
  summary: string
  patientName: string
  status: string
  statusLabel?: string
  occurredAt?: string
  detail: StepDetail | null
  showPdf?: boolean
  isPartnerConfirmed?: boolean
  onConfirmPartner?: () => void
  assignmentSuggestion?: CaseManagerSuggestion
  caseManagerOptions?: CaseManagerOption[]
  selectedCaseManagerEmail?: string
  isAssignmentConfirmed?: boolean
  onCaseManagerChange?: (email: string) => void
  onConfirmAssignment?: () => void
  caseManagerNotification?: CaseManagerNotification
  referralNotification?: ReferralSourceNotification
  mondayRecord?: MondayRecord
  drkDraft?: DrkDraftRecord
  providerRecommendation?: ProviderOption
  providerOptions?: ProviderOption[]
  providerSelectionLocation?: string
  fallbackProviderOptions?: ProviderOption[]
  providerTerritoryResolution?: 'assigned' | 'discharged'
  selectedProviderId?: string
  isProviderConfirmed?: boolean
  onProviderChange?: (providerId: string) => void
  onConfirmProvider?: () => void
  onAssignFallbackProvider?: () => void
  onDischargePatient?: () => void
  providerAvailability?: {
    provider: ProviderOption
    requestedAt: string
    deadlineAt: string
    outcome: 'waiting' | 'confirmed' | 'timeout' | 'placement_completed'
    resolvedAt?: string
    responseDuration?: string
  }
  onProviderAvailabilityConfirmed?: () => void
  onProviderAvailabilityTimeout?: () => void
  onManualPlacementCompleted?: () => void
  schedulingHandoff?: SchedulingHandoff
  patientSchedule?: PatientSchedulingRecord
  onSelectSchedulingSlot?: (slotId: string) => void
  onCompletePatientSchedule?: () => void
  onRecordSchedulingBlocker?: (reason: SchedulingBlockerReason) => void
  referralPacketPdf?: string
  eodSchedulingCheck?: EodSchedulingCheckRecord
  eodFollowUp?: boolean
  eodEscalation?: boolean
  eodManualFollowUp?: boolean
  eodEscalatedToManagement?: boolean
  eodManualCmFollowUpSent?: boolean
  onEodFollowUpWithCaseManager?: () => void
  onEodEscalateToManagement?: () => void
  weeklyVisitCheck?: WeeklyVisitCheckRecord
  weeklyHoldsClosures?: boolean
  weeklyRescheduleConfirmed?: boolean
  weeklyDischargeReviewSent?: boolean
  weeklyHoldsActionTaken?: boolean
  weeklyAppointmentRescheduled?: boolean
  onWeeklyConfirmReschedule?: () => void
  onWeeklyEscalateDischargeReview?: () => void
  onWeeklyHoldsAction?: () => void
  onWeeklyConfirmAppointmentRescheduled?: () => void
  isUnread?: boolean
  intakeEditable?: boolean
  isIntakeConfirmed?: boolean
  onIntakeFieldChange?: (key: string, value: string) => void
  onIntakeSectionRowsReplace?: (
    sectionId: string,
    rows: Array<{
      label: string
      value: string
      fieldPath?: string
      rowId?: string
      meta?: string
    }>,
  ) => void
  onConfirmIntakeReview?: () => void
  onReopenIntakeReview?: () => void
  onScopePatient?: () => void
  actionTimer?: ActionTimer
}) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [fieldsOpen, setFieldsOpen] = useState(false)
  const [intakeEditing, setIntakeEditing] = useState(false)
  const [intakeDrafts, setIntakeDrafts] = useState<Record<string, string>>({})
  const [intakeSectionDrafts, setIntakeSectionDrafts] = useState<
    Record<string, ArtifactField[]>
  >({})
  const fieldsEditable =
    intakeEditable && !isIntakeConfirmed && intakeEditing
  const when = occurredAt ? parseOpsDate(occurredAt) : null
  const meaning = statusLabel ?? statusMeaning(status)
  const decision = detail?.example?.feedDecision
  const contactConfirmation = detail?.example?.feedContactConfirmation
  const contactedBack =
    isPartnerConfirmed || contactConfirmation?.contactedBack || false
  const proofFields = decision || contactConfirmation
    ? []
    : (detail?.example?.artifactSections?.[0]?.fields ?? [])
        .filter((field) => !isHiddenProofField(field.label))
        .slice(0, 3)
  const samplePdf = showPdf ? detail?.example?.samplePdf : undefined
  const committedSections = (detail?.example?.artifactSections ?? []).filter(
    (section) =>
      section.id !== 'gate' &&
      (section.fields.length > 0 || section.repeatable),
  )
  const sectionsWithListDrafts = fieldsEditable
    ? committedSections.map((section) =>
        intakeSectionDrafts[section.id]
          ? { ...section, fields: intakeSectionDrafts[section.id] }
          : section,
      )
    : committedSections
  const allSections = fieldsEditable
    ? overlayIntakeFieldValues(sectionsWithListDrafts, intakeDrafts)
    : sectionsWithListDrafts

  const flushIntakeDrafts = () => {
    Object.entries(intakeDrafts).forEach(([key, value]) => {
      onIntakeFieldChange?.(key, value)
    })
    Object.entries(intakeSectionDrafts).forEach(([sectionId, rows]) => {
      onIntakeSectionRowsReplace?.(sectionId, rows)
    })
    setIntakeDrafts({})
    setIntakeSectionDrafts({})
  }
  const requiredFields =
    allSections.find((section) => section.id === 'required-fields')?.fields ??
    []
  const sections = allSections.filter(
    (section) => section.id !== 'required-fields',
  )
  const missingSet = new Set(decision?.missingLabels ?? [])
  const unclearSet = new Set(decision?.unclearLabels ?? [])
  const artifactId = detail?.example?.artifactId ?? 'feed-artifact'
  const selectedCaseManager =
    caseManagerOptions.find(
      (manager) => manager.email === selectedCaseManagerEmail,
    ) ?? assignmentSuggestion
  const selectedProvider =
    providerOptions.find((provider) => provider.id === selectedProviderId) ??
    providerRecommendation
  const selectedFallbackProvider =
    fallbackProviderOptions.find(
      (provider) => provider.id === selectedProviderId,
    ) ?? fallbackProviderOptions[0]

  return (
    <article
      className={`stage-ops-step-feed__message is-${status} is-open${
        isUnread ? ' is-unread' : ''
      }${actionTimer?.status === 'overdue' ? ' is-overdue' : ''}${
        actionTimer?.status === 'warning' ? ' is-warning' : ''
      }`}
      aria-label={`${summary} · ${patientName} · ${meaning}${actionTimerAriaSuffix(
        actionTimer,
      )}`}
    >
      <header className="stage-ops-step-feed__row">
        <time className="stage-ops-step-feed__time" dateTime={occurredAt}>
          {when ? when.time : '—'}
        </time>
        <div className="stage-ops-step-feed__copy">
          <strong className="stage-ops-step-feed__summary">{summary}</strong>
          {onScopePatient ? (
            <button
              type="button"
              className="stage-ops-step-feed__patient is-link"
              aria-label={`Show ${patientName}`}
              onClick={onScopePatient}
            >
              {patientName}
            </button>
          ) : (
            <span className="stage-ops-step-feed__patient">{patientName}</span>
          )}
          {isUnread ? (
            <span className="stage-ops-step-feed__unread-label">Unread</span>
          ) : null}
        </div>
        <span className={`stage-ops-step-feed__status is-${status}`}>
          {meaning}
        </span>
      </header>

      <div className="stage-ops-step-feed__body">
        {actionTimer ? (
          <ActionSlaAlert timer={actionTimer} patientName={patientName} />
        ) : null}
        {decision ? (
          <div className="stage-ops-step-feed__decision" aria-label="Key decision">
            <dl className="stage-ops-step-feed__decision-grid">
              <div className="stage-ops-step-feed__decision-item is-wide">
                <dt>Identity</dt>
                <dd>{decision.identityLine}</dd>
              </div>
              <div className="stage-ops-step-feed__decision-item">
                <dt>Threshold</dt>
                <dd className={decision.thresholdMet ? 'is-ok' : 'is-bad'}>
                  {decision.thresholdMet ? 'Met' : 'Not met'}
                </dd>
              </div>
              <div className="stage-ops-step-feed__decision-item">
                <dt>Completeness</dt>
                <dd>
                  {decision.completeCount}/{decision.totalRequired}
                </dd>
              </div>
              <div className="stage-ops-step-feed__decision-item is-wide">
                <dt>Missing</dt>
                <dd>
                  {decision.missingLabels.length
                    ? decision.missingLabels.join(' · ')
                    : 'None'}
                </dd>
              </div>
              {decision.unclearLabels.length ? (
                <div className="stage-ops-step-feed__decision-item is-wide">
                  <dt>Unclear</dt>
                  <dd className="is-warn">
                    {decision.unclearLabels.join(' · ')}
                  </dd>
                </div>
              ) : null}
            </dl>

            {requiredFields.length ? (
              <div className="stage-ops-step-feed__fields-panel">
                <button
                  type="button"
                  className={`stage-ops-step-feed__fields-toggle${
                    fieldsOpen ? ' is-open' : ''
                  }`}
                  aria-expanded={fieldsOpen}
                  aria-controls={`${artifactId}-required-fields`}
                  onClick={() => setFieldsOpen((current) => !current)}
                >
                  <span className="stage-ops-step-feed__fields-toggle-copy">
                    <strong>Detailed info</strong>
                    <small>
                      {requiredFields.length} fields
                      {decision
                        ? ` · ${decision.completeCount}/${decision.totalRequired}`
                        : ''}
                    </small>
                  </span>
                  <ChevronDown size={16} aria-hidden="true" />
                </button>
                {fieldsOpen ? (
                  <dl
                    id={`${artifactId}-required-fields`}
                    className="stage-ops-step-feed__required"
                    aria-label="Seven required fields"
                  >
                    {requiredFields.map((field) => {
                      const missing = missingSet.has(field.label)
                      const unclear = unclearSet.has(field.label)
                      const isLong = isMultilineIntakeField(field.label)
                      const tone = missing
                        ? 'is-bad'
                        : unclear
                          ? 'is-warn'
                          : 'is-ok'
                      return (
                        <div
                          key={intakeEditKey('required-fields', field)}
                          className={`stage-ops-step-feed__decision-item${
                            isLong ? ' is-wide' : ''
                          } ${tone}`}
                        >
                          <dt>{field.label}</dt>
                          <dd
                            className={tone}
                            title={
                              unclear
                                ? 'Extracted value conflicts with other evidence — needs review'
                                : undefined
                            }
                          >
                            {fieldsEditable ? (
                              <ArtifactFieldInput
                                label={field.label}
                                value={field.value}
                                multiline={isLong}
                                onChange={(value) =>
                                  setIntakeDrafts((current) => ({
                                    ...current,
                                    [intakeEditKey('required-fields', field)]:
                                      value,
                                  }))
                                }
                              />
                            ) : (
                              field.value
                            )}
                          </dd>
                        </div>
                      )
                    })}
                  </dl>
                ) : null}
              </div>
            ) : null}

            {intakeEditable && onConfirmIntakeReview ? (
              <div className="stage-ops-step-feed__intake-confirm">
                <button
                  type="button"
                  className={`stage-ops-step-feed__confirm${
                    isIntakeConfirmed ? ' is-confirmed' : ' is-actionable'
                  }`}
                  onClick={() => {
                    if (intakeEditing) {
                      flushIntakeDrafts()
                      setIntakeEditing(false)
                    }
                    onConfirmIntakeReview()
                  }}
                  disabled={isIntakeConfirmed}
                >
                  {isIntakeConfirmed
                    ? 'Confirmed'
                    : 'Confirm all information is correct'}
                </button>
                {isIntakeConfirmed ? (
                  <button
                    type="button"
                    className="stage-ops-step-feed__confirm is-actionable"
                    onClick={() => {
                      onReopenIntakeReview?.()
                      setIntakeEditing(true)
                    }}
                  >
                    Add or edit patient information
                  </button>
                ) : (
                  <button
                    type="button"
                    className="stage-ops-step-feed__confirm is-actionable"
                    onClick={() => {
                      if (intakeEditing) {
                        flushIntakeDrafts()
                        setIntakeEditing(false)
                        return
                      }
                      setIntakeEditing(true)
                    }}
                  >
                    {intakeEditing ? 'Save changes' : 'Edit'}
                  </button>
                )}
              </div>
            ) : null}

            {sections.length ? (
              <div className="stage-ops-step-feed__details">
                <button
                  type="button"
                  className={`stage-ops-step-feed__details-toggle${detailsOpen ? ' is-open' : ''}`}
                  aria-expanded={detailsOpen}
                  onClick={() => setDetailsOpen((current) => !current)}
                >
                  <span>
                    {detailsOpen
                      ? 'Hide extracted details'
                      : 'Show extracted details'}
                  </span>
                  <ChevronDown size={16} aria-hidden="true" />
                </button>
                {detailsOpen ? (
                  <ArtifactSections
                    sections={sections}
                    artifactId={artifactId}
                    density="feed"
                    editable={fieldsEditable}
                    onFieldChange={(key, value) =>
                      setIntakeDrafts((current) => ({
                        ...current,
                        [key]: value,
                      }))
                    }
                    onSectionRowsChange={(sectionId, rows) =>
                      setIntakeSectionDrafts((current) => ({
                        ...current,
                        [sectionId]: rows,
                      }))
                    }
                  />
                ) : null}
              </div>
            ) : null}
          </div>
        ) : assignmentSuggestion && selectedCaseManager ? (
          <div
            className="stage-ops-step-feed__assignment"
            aria-label="Case manager assignment"
          >
            <div className="stage-ops-step-feed__assignment-suggestion">
              <p className="stage-ops-step-feed__partner-label">
                AI recommendation
              </p>
              <p className="stage-ops-step-feed__partner-name">
                {assignmentSuggestion.name}
              </p>
              <p className="stage-ops-step-feed__partner-email">
                {assignmentSuggestion.email}
              </p>
            </div>

            <div className="stage-ops-step-feed__assignment-action">
              <label className="stage-ops-step-feed__manager-select">
                <span className="stage-ops-step-feed__manager-label">
                  Assigned case manager
                </span>
                <select
                  value={selectedCaseManager.email}
                  onChange={(event) =>
                    onCaseManagerChange?.(event.target.value)
                  }
                  disabled={isAssignmentConfirmed}
                >
                  {caseManagerOptions.map((manager) => (
                    <option key={manager.email} value={manager.email}>
                      {manager.name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className={`stage-ops-step-feed__confirm${
                  isAssignmentConfirmed ? ' is-confirmed' : ' is-actionable'
                }`}
                onClick={onConfirmAssignment}
                disabled={isAssignmentConfirmed || !onConfirmAssignment}
              >
                {isAssignmentConfirmed
                  ? 'Assigned'
                  : 'Confirm'}
              </button>
            </div>
          </div>
        ) : providerSelectionLocation && providerOptions.length === 0 ? (
          <div
            className="stage-ops-step-feed__provider-territory-empty"
            aria-label="Provider territory review"
          >
            <div>
              <strong>
                No company provider in {providerSelectionLocation}
              </strong>
              <p>
                Nicole can select another company provider or discharge the
                patient after review.
              </p>
            </div>
            {providerTerritoryResolution === 'assigned' &&
            selectedFallbackProvider ? (
              <p className="stage-ops-step-feed__territory-resolution">
                {selectedFallbackProvider.name} selected · Availability request
                ready
              </p>
            ) : providerTerritoryResolution === 'discharged' ? (
              <p className="stage-ops-step-feed__territory-resolution">
                Patient discharged
              </p>
            ) : selectedFallbackProvider ? (
              <div className="stage-ops-step-feed__territory-actions">
                <label className="stage-ops-step-feed__manager-select">
                  <span className="stage-ops-step-feed__manager-label">
                    Other company provider
                  </span>
                  <select
                    value={selectedFallbackProvider.id}
                    onChange={(event) =>
                      onProviderChange?.(event.target.value)
                    }
                  >
                    {fallbackProviderOptions.map((provider) => (
                      <option key={provider.id} value={provider.id}>
                        {provider.name}
                        {provider.city ? ` — ${provider.city}` : ''}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="stage-ops-step-feed__confirm is-actionable"
                  onClick={onAssignFallbackProvider}
                >
                  Use selected provider
                </button>
                <button
                  type="button"
                  className="stage-ops-step-feed__availability-timeout is-danger"
                  onClick={onDischargePatient}
                >
                  Discharge
                </button>
              </div>
            ) : null}
          </div>
        ) : providerRecommendation && selectedProvider ? (
          <div
            className="stage-ops-step-feed__assignment is-provider"
            aria-label="Provider selection"
          >
            <div className="stage-ops-step-feed__assignment-suggestion">
              <p className="stage-ops-step-feed__partner-label">
                <span>Patient location</span>
                {selectedProvider.npi ? <span>NPI</span> : null}
              </p>
              <p className="stage-ops-step-feed__partner-name is-location">
                <span>{providerSelectionLocation}</span>
                {selectedProvider.npi ? (
                  <span className="stage-ops-step-feed__partner-label-meta">
                    {selectedProvider.npi}
                  </span>
                ) : null}
              </p>
            </div>

            <div className="stage-ops-step-feed__assignment-action">
              <label className="stage-ops-step-feed__manager-select">
                <span className="stage-ops-step-feed__manager-label">
                  Selected provider
                </span>
                <select
                  value={selectedProvider.id}
                  onChange={(event) => onProviderChange?.(event.target.value)}
                  disabled={isProviderConfirmed}
                >
                  {providerOptions.map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.name}
                      {provider.city ? ` — ${provider.city}` : ' — Location unavailable'}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className={`stage-ops-step-feed__confirm${
                  isProviderConfirmed ? ' is-confirmed' : ' is-actionable'
                }`}
                onClick={onConfirmProvider}
                disabled={isProviderConfirmed || !onConfirmProvider}
              >
                {isProviderConfirmed ? 'Selected' : 'Confirm'}
              </button>
            </div>
          </div>
        ) : providerAvailability ? (
          <div
            className="stage-ops-step-feed__availability"
            aria-label="Provider availability response"
          >
            <section className="stage-ops-step-feed__availability-provider">
              <p className="stage-ops-step-feed__partner-label">Provider</p>
              <strong>{providerAvailability.provider.name}</strong>
              <p>
                {[
                  providerAvailability.provider.city,
                  providerAvailability.provider.npi
                    ? `NPI ${providerAvailability.provider.npi}`
                    : undefined,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
              <p>
                {[
                  providerAvailability.provider.email,
                  providerAvailability.provider.phone,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
            </section>

            <section className="stage-ops-step-feed__availability-request">
              <p className="stage-ops-step-feed__partner-label">
                Availability request
              </p>
              <dl>
                <div>
                  <dt>Sent</dt>
                  <dd>{providerAvailability.requestedAt}</dd>
                </div>
                <div>
                  <dt>
                    {providerAvailability.outcome === 'confirmed' ||
                    providerAvailability.outcome === 'placement_completed'
                      ? 'Confirmed'
                      : 'Response deadline'}
                  </dt>
                  <dd>
                    {providerAvailability.outcome === 'confirmed' ||
                    providerAvailability.outcome === 'placement_completed'
                      ? providerAvailability.resolvedAt
                      : providerAvailability.deadlineAt}
                  </dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>
                    <strong>
                      {providerAvailability.outcome === 'confirmed'
                        ? 'Provider confirmed'
                        : providerAvailability.outcome === 'placement_completed'
                          ? 'Placed manually'
                          : providerAvailability.outcome === 'timeout'
                            ? 'No response'
                            : 'Waiting for provider'}
                    </strong>
                  </dd>
                </div>
                <div>
                  <dt>
                    {providerAvailability.outcome === 'waiting'
                      ? 'Time remaining'
                      : 'Response time'}
                  </dt>
                  <dd>
                    <strong>
                      {providerAvailability.outcome === 'waiting'
                        ? actionTimer && actionTimer.status !== 'resolved'
                          ? <TimerRemainingValue timer={actionTimer} />
                          : '—'
                        : providerAvailability.responseDuration}
                    </strong>
                  </dd>
                </div>
              </dl>
            </section>

            {providerAvailability.outcome === 'confirmed' ? (
              <p className="stage-ops-step-feed__availability-result is-confirmed">
                Monday.com and DRK ready to update with the selected provider.
              </p>
            ) : providerAvailability.outcome === 'placement_completed' ? (
              <p className="stage-ops-step-feed__availability-result is-confirmed">
                Monday.com and DRK ready to update with the placed provider.
              </p>
            ) : providerAvailability.outcome === 'timeout' ? (
              <p className="stage-ops-step-feed__availability-result is-timeout">
                Place the patient manually using the provider’s known schedule.
              </p>
            ) : null}

            {providerAvailability.outcome === 'waiting' &&
            (onProviderAvailabilityConfirmed ||
              onProviderAvailabilityTimeout) ? (
              <div className="stage-ops-step-feed__availability-actions">
                <button
                  type="button"
                  className="stage-ops-step-feed__confirm is-actionable"
                  onClick={onProviderAvailabilityConfirmed}
                >
                  Provider confirmed
                </button>
                <button
                  type="button"
                  className="stage-ops-step-feed__availability-timeout"
                  onClick={onProviderAvailabilityTimeout}
                >
                  No response — place manually
                </button>
              </div>
            ) : providerAvailability.outcome === 'timeout' &&
              onManualPlacementCompleted ? (
              <div className="stage-ops-step-feed__availability-actions">
                <button
                  type="button"
                  className="stage-ops-step-feed__confirm is-actionable"
                  onClick={onManualPlacementCompleted}
                >
                  Placement completed
                </button>
              </div>
            ) : null}
          </div>
        ) : eodSchedulingCheck && eodFollowUp ? (
          <EodCmFollowUpPanel
            record={eodSchedulingCheck}
            patientName={patientName}
            manualFollowUp={eodManualFollowUp}
          />
        ) : eodSchedulingCheck && eodEscalation ? (
          <EodEscalationPanel
            record={eodSchedulingCheck}
            patientName={patientName}
          />
        ) : eodSchedulingCheck ? (
          <EodSchedulingCheckPanel
            record={eodSchedulingCheck}
            escalatedToManagement={eodEscalatedToManagement}
            manualCmFollowUpSent={eodManualCmFollowUpSent}
            onFollowUpWithCaseManager={onEodFollowUpWithCaseManager}
            onEscalateToManagement={onEodEscalateToManagement}
          />
        ) : weeklyVisitCheck && weeklyHoldsClosures ? (
          <WeeklyHoldsClosuresPanel
            record={weeklyVisitCheck}
            patientName={patientName}
            actionTaken={weeklyHoldsActionTaken}
            onTakeAction={onWeeklyHoldsAction}
          />
        ) : weeklyVisitCheck ? (
          <WeeklyVisitCheckPanel
            record={weeklyVisitCheck}
            patientName={patientName}
            rescheduleConfirmed={weeklyRescheduleConfirmed}
            dischargeReviewSent={weeklyDischargeReviewSent}
            appointmentRescheduled={weeklyAppointmentRescheduled}
            onConfirmReschedule={onWeeklyConfirmReschedule}
            onEscalateDischargeReview={onWeeklyEscalateDischargeReview}
            onConfirmAppointmentRescheduled={
              onWeeklyConfirmAppointmentRescheduled
            }
          />
        ) : patientSchedule ? (
          <SchedulingPanel
            record={patientSchedule}
            onSelectSlot={onSelectSchedulingSlot}
            onSchedule={onCompletePatientSchedule}
            onRecordBlocker={onRecordSchedulingBlocker}
          />
        ) : schedulingHandoff ? (
          <ReferralHandoffPanel
            patientId={schedulingHandoff.patientId}
            patientName={patientName}
            provider={schedulingHandoff.provider}
            samplePdf={referralPacketPdf ?? schedulingHandoff.samplePdf}
          />
        ) : referralPacketPdf ? (
          <div
            className="stage-ops-step-feed__referral-packet"
            aria-label="Referral documents"
          >
            <p className="stage-ops-step-feed__partner-label">
              Referral documents
            </p>
            <IntakePdfPreview samplePdf={referralPacketPdf} />
          </div>
        ) : caseManagerNotification ? (
          <div
            className="stage-ops-step-feed__notification"
            aria-label="Case manager notification"
          >
            <dl className="stage-ops-step-feed__notification-meta">
              <div className="stage-ops-step-feed__decision-item">
                <dt>Sent to</dt>
                <dd>
                  {caseManagerNotification.managerName} ·{' '}
                  {caseManagerNotification.managerEmail}
                </dd>
              </div>
              <div className="stage-ops-step-feed__decision-item">
                <dt>Subject</dt>
                <dd>{caseManagerNotification.subject}</dd>
              </div>
            </dl>
            <p className="stage-ops-step-feed__notification-message">
              {caseManagerNotification.message}
            </p>
            <dl
              className="stage-ops-step-feed__required"
              aria-label="Patient data shared with case manager"
            >
              {caseManagerNotification.patientFields.map((field) => (
                <div
                  key={field.label}
                  className={`stage-ops-step-feed__decision-item${
                    /^(Patient name|Date of birth|Contact number|Patient address)$/i.test(
                      field.label,
                    )
                      ? ''
                      : ' is-wide'
                  }`}
                >
                  <dt>{field.label}</dt>
                  <dd>{field.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        ) : mondayRecord || drkDraft ? (
          <div className="stage-ops-step-feed__records">
            {mondayRecord ? (
              <section className="stage-ops-step-feed__records-block">
                {drkDraft ? (
                  <h5 className="stage-ops-step-feed__records-heading">
                    Monday.com Master Sheet
                  </h5>
                ) : null}
                <MondayRecordView record={mondayRecord} />
              </section>
            ) : null}
            {drkDraft ? (
              <section className="stage-ops-step-feed__records-block">
                {mondayRecord ? (
                  <h5 className="stage-ops-step-feed__records-heading">
                    DRK chart
                  </h5>
                ) : null}
                <DrkDraftView
                  draft={drkDraft}
                  detailsOpen={detailsOpen}
                  onToggleDetails={() =>
                    setDetailsOpen((current) => !current)
                  }
                />
              </section>
            ) : null}
          </div>
        ) : referralNotification ? (
          <div
            className="stage-ops-step-feed__email"
            aria-label="Referral source notification email"
          >
            <dl className="stage-ops-step-feed__email-headers">
              <div>
                <dt>To</dt>
                <dd>{referralNotification.to}</dd>
              </div>
              <div>
                <dt>CC</dt>
                <dd>
                  {referralNotification.ccName} ·{' '}
                  {referralNotification.ccEmail}
                </dd>
              </div>
              <div>
                <dt>Subject</dt>
                <dd>{referralNotification.subject}</dd>
              </div>
            </dl>
            <p className="stage-ops-step-feed__email-body">
              {referralNotification.body}
            </p>
          </div>
        ) : contactConfirmation ? (
          <div
            className="stage-ops-step-feed__contact"
            aria-label="Referral partner contact confirmation"
          >
            <div className="stage-ops-step-feed__partner">
              <p className="stage-ops-step-feed__partner-label">Referral partner</p>
              <p className="stage-ops-step-feed__partner-name">
                {contactConfirmation.partnerName}
              </p>
              {contactConfirmation.partnerEmail ? (
                <p className="stage-ops-step-feed__partner-email">
                  {contactConfirmation.partnerEmail}
                </p>
              ) : null}
            </div>
            <div className="stage-ops-step-feed__contact-action">
              <div className="stage-ops-step-feed__reply-status">
                <span className="stage-ops-step-feed__reply-label">
                  Partner replied?
                </span>
                <span
                  className={`stage-ops-step-feed__reply-pill${
                    contactedBack ? ' is-confirmed' : ' is-pending'
                  }`}
                >
                  {contactedBack ? 'Confirmed' : 'Not yet'}
                </span>
              </div>
              {!contactedBack ? (
                <button
                  type="button"
                  className="stage-ops-step-feed__confirm is-actionable"
                  onClick={onConfirmPartner}
                  disabled={!onConfirmPartner}
                >
                  Confirm partner is contacted
                </button>
              ) : null}
            </div>
          </div>
        ) : proofFields.length || samplePdf ? (
          <div className="stage-ops-step-feed__meta-row">
            {proofFields.length ? (
              <dl className="stage-ops-step-feed__proof" aria-label="Key proof">
                {proofFields.map((field) => (
                  <div
                    key={`${field.label}-${field.value}`}
                    className="stage-ops-step-feed__proof-item"
                  >
                    <dt>{field.label}</dt>
                    <dd>{field.value}</dd>
                  </div>
                ))}
              </dl>
            ) : null}

            {samplePdf ? <IntakePdfPreview samplePdf={samplePdf} /> : null}
          </div>
        ) : null}
      </div>
    </article>
  )
}
