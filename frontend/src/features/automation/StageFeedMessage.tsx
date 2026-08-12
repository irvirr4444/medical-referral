import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { ArtifactSections } from './ArtifactSections'
import { IntakePdfPreview } from './IntakePdfPreview'
import { statusMeaning } from './StagePatientStepDetail'
import { parseOpsDate, type detailForPatientStep } from './ops'
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
}: {
  summary: string
  patientName: string
  status: string
  occurredAt?: string
  detail: StepDetail | null
  showPdf?: boolean
  isPartnerConfirmed?: boolean
  onConfirmPartner?: () => void
}) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const when = occurredAt ? parseOpsDate(occurredAt) : null
  const meaning = statusMeaning(status)
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

  return (
    <article
      className={`stage-ops-step-feed__message is-${status} is-open`}
      aria-label={`${summary} · ${patientName} · ${meaning}`}
    >
      <header className="stage-ops-step-feed__row">
        <time className="stage-ops-step-feed__time" dateTime={occurredAt}>
          {when ? when.time : '—'}
        </time>
        <div className="stage-ops-step-feed__copy">
          <strong className="stage-ops-step-feed__summary">{summary}</strong>
          <span className="stage-ops-step-feed__patient">{patientName}</span>
        </div>
        <span className={`stage-ops-step-feed__status is-${status}`}>
          {meaning}
        </span>
      </header>

      <div className="stage-ops-step-feed__body">
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
