import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { ArtifactSections } from './ArtifactSections'
import { IntakePdfPreview } from './IntakePdfPreview'
import { statusMeaning } from './StagePatientStepDetail'
import { parseOpsDate, type detailForPatientStep } from './ops'
import type {
  CaseManagerNotification,
  CaseManagerOption,
  CaseManagerSuggestion,
  DrkDraftRecord,
  MondayRecord,
  ReferralSourceNotification,
} from './fixtures/caseManagerAssignments'
import type { LiveInboxReferral, LiveInboxStep } from './liveInbox/types'
import './StageOps.css'

type StepDetail = ReturnType<typeof detailForPatientStep>

function isHiddenProofField(label: string) {
  return /attachment|pdf|file name|filename|message id|attachment id|received|result/i.test(
    label,
  )
}

/** Always-open Slack-style message: skim in under 3 seconds. */
export function StageFeedMessage({
  summary,
  patientName,
  status,
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
  isUnread = false,
  liveInboxReferral,
  liveInboxStep,
}: {
  summary: string
  patientName: string
  status: string
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
  isUnread?: boolean
  liveInboxReferral?: LiveInboxReferral
  liveInboxStep?: LiveInboxStep
}) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const when = occurredAt ? parseOpsDate(occurredAt) : null
  const meaning =
    liveInboxReferral && !liveInboxStep && status === 'waiting'
      ? 'Queued'
      : statusMeaning(status)
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
  const allSections = (detail?.example?.artifactSections ?? []).filter(
    (section) => section.fields.length > 0 && section.id !== 'gate',
  )
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

  return (
    <article
      className={`stage-ops-step-feed__message is-${status} is-open${
        isUnread ? ' is-unread' : ''
      }`}
      aria-label={`${summary} · ${patientName} · ${meaning}`}
    >
      <header className="stage-ops-step-feed__row">
        <time className="stage-ops-step-feed__time" dateTime={occurredAt}>
          {when ? when.time : '—'}
        </time>
        <div className="stage-ops-step-feed__copy">
          <strong className="stage-ops-step-feed__summary">{summary}</strong>
          <span className="stage-ops-step-feed__patient">{patientName}</span>
          {isUnread ? (
            <span className="stage-ops-step-feed__unread-label">Unread</span>
          ) : null}
        </div>
        <span className={`stage-ops-step-feed__status is-${status}`}>
          {meaning}
        </span>
      </header>

      <div className="stage-ops-step-feed__body">
        {liveInboxReferral && (!liveInboxStep || liveInboxStep.step_id === 'receive-referral') ? (
          <div className="stage-ops-step-feed__meta-row" aria-label="Live inbox message">
            <dl className="stage-ops-step-feed__proof" aria-label="Key proof">
              <div className="stage-ops-step-feed__proof-item">
                <dt>Sender</dt>
                <dd>{liveInboxReferral.sender || 'Sender unavailable'}</dd>
              </div>
            </dl>
            <IntakePdfPreview
              samplePdf={liveInboxReferral.filename}
              fileUrl={`/api/intake/inbox/pdf/${encodeURIComponent(liveInboxReferral.id)}`}
            />
          </div>
        ) : liveInboxStep ? (
          <dl className="stage-ops-step-feed__proof is-live-workflow" aria-label="Live workflow output">
            {liveStepProof(liveInboxStep).map((field) => (
              <div className="stage-ops-step-feed__proof-item" key={field.label}>
                <dt>{field.label}</dt>
                <dd>{field.value}</dd>
              </div>
            ))}
          </dl>
        ) : decision ? (
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
              <dl
                className="stage-ops-step-feed__required"
                aria-label="Seven required fields"
              >
                {requiredFields.map((field) => {
                  const missing = missingSet.has(field.label)
                  const unclear = unclearSet.has(field.label)
                  const isLong = !/^(Patient name|Date of birth|Contact number|Patient address)$/i.test(
                    field.label,
                  )
                  return (
                    <div
                      key={`${field.label}-${field.value}`}
                      className={`stage-ops-step-feed__decision-item${
                        isLong ? ' is-wide' : ''
                      }`}
                    >
                      <dt>{field.label}</dt>
                      <dd
                        className={
                          missing ? 'is-bad' : unclear ? 'is-warn' : 'is-ok'
                        }
                        title={
                          unclear
                            ? 'Extracted value conflicts with other evidence — needs review'
                            : undefined
                        }
                      >
                        {field.value}
                      </dd>
                    </div>
                  )
                })}
              </dl>
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
        ) : drkDraft ? (
          <div
            className="stage-ops-step-feed__drk"
            aria-label="DRK chart draft details"
          >
            <dl className="stage-ops-step-feed__drk-summary">
              {[
                [
                  'Patient',
                  [
                    drkDraft.demographics.find(
                      (field) => field.label === 'First name',
                    )?.value,
                    drkDraft.demographics.find(
                      (field) => field.label === 'Last name',
                    )?.value,
                  ]
                    .filter(Boolean)
                    .join(' '),
                ],
                [
                  'Date of birth',
                  drkDraft.demographics.find(
                    (field) => field.label === 'Date of birth',
                  )?.value ?? 'Not documented',
                ],
                [
                  'Primary phone',
                  drkDraft.contact.find(
                    (field) => field.label === 'Primary phone',
                  )?.value ?? 'Not documented',
                ],
                [
                  'Address',
                  drkDraft.primaryAddress.find(
                    (field) => field.label === 'Address',
                  )?.value ?? 'Not documented',
                ],
                [
                  'Home health',
                  drkDraft.admission.find(
                    (field) => field.label === 'Home health query',
                  )?.value ?? 'Not documented',
                ],
                [
                  'Insurance',
                  drkDraft.insurance.find(
                    (field) => field.label === 'Payer query',
                  )?.value ?? 'Not documented',
                ],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            {drkDraft.blockers.length ? (
              <div className="stage-ops-step-feed__drk-note is-blocker">
                <strong>Blockers</strong>
                <ul>
                  {drkDraft.blockers.map((blocker) => (
                    <li key={blocker}>{blocker}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            <button
              type="button"
              className={`stage-ops-step-feed__details-toggle${
                detailsOpen ? ' is-open' : ''
              }`}
              aria-expanded={detailsOpen}
              onClick={() => setDetailsOpen((current) => !current)}
            >
              <span>
                {detailsOpen
                  ? 'Hide full DRK details'
                  : 'Show full DRK details'}
              </span>
              <ChevronDown size={16} aria-hidden="true" />
            </button>
            {detailsOpen ? (
              <>
                <div className="stage-ops-step-feed__drk-sections">
                  {[
                    ['Demographics', drkDraft.demographics],
                    ['Primary address', drkDraft.primaryAddress],
                    ['Contact', drkDraft.contact],
                    ['Admission', drkDraft.admission],
                    ['Referral', drkDraft.referral],
                    ['Insurance', drkDraft.insurance],
                  ].map(([title, fields]) => (
                    <section key={title as string}>
                      <h5>{title as string}</h5>
                      <dl>
                        {(
                          fields as Array<{ label: string; value: string }>
                        ).map((field) => (
                          <div key={field.label}>
                            <dt>{field.label}</dt>
                            <dd>{field.value}</dd>
                          </div>
                        ))}
                      </dl>
                    </section>
                  ))}
                </div>
              </>
            ) : null}
          </div>
        ) : mondayRecord ? (
          <div
            className="stage-ops-step-feed__monday-record"
            aria-label="Monday.com record details"
          >
            <dl className="stage-ops-step-feed__monday-fields">
              {[
                ['Patient name', mondayRecord.data.patient_name],
                ['Date of birth', mondayRecord.data.date_of_birth],
                ['Contact number', mondayRecord.data.contact_number],
                ['Patient address', mondayRecord.data.patient_address],
                [
                  'Home health or hospice agency',
                  mondayRecord.data.home_health_or_hospice_agency,
                ],
                [
                  'Wound or clinical information',
                  mondayRecord.data.wound_or_clinical_information,
                ],
                [
                  'Insurance information',
                  mondayRecord.data.insurance_information,
                ],
                [
                  'Case manager',
                  `${mondayRecord.data.case_manager.name} · ${mondayRecord.data.case_manager.email}`,
                ],
                ['Sent by', mondayRecord.data.sent_by],
                ['Referral status', mondayRecord.data.referral_status],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className={`stage-ops-step-feed__decision-item${
                    /^(Home health|Wound|Insurance|Case manager)/i.test(label)
                      ? ' is-wide'
                      : ''
                  }`}
                >
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
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
                  Mark partner contacted
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

function liveStepProof(step: LiveInboxStep): Array<{ label: string; value: string }> {
  const fields = step.details.fields
  if (fields && typeof fields === 'object' && !Array.isArray(fields)) {
    return Object.entries(fields)
      .filter(([, value]) => value !== null && value !== undefined && String(value).trim())
      .map(([label, value]) => ({ label: readableLabel(label), value: String(value) }))
  }
  return Object.entries(step.details)
    .filter(([label, value]) => label !== 'write_performed' && value !== null && value !== undefined)
    .slice(0, 4)
    .map(([label, value]) => ({
      label: readableLabel(label),
      value: Array.isArray(value) ? value.join(', ') : String(value),
    }))
}

function readableLabel(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}
