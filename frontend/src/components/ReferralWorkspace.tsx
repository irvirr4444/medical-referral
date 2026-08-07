import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { useDemo } from '../state/useDemo'
import { DuplicateBadge, FieldStatusBadge, OutcomeBadge } from './StatusBadges'
import { PdfViewer } from './PdfViewer'
import './ReferralWorkspace.css'

export function ReferralWorkspace() {
  const { selectedReferral, dispatch } = useDemo()
  const [evidenceFieldKey, setEvidenceFieldKey] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<
    'overview' | 'monday' | 'drk' | 'confirm' | 'timeline'
  >('overview')

  useEffect(() => {
    setEvidenceFieldKey(null)
    setActiveTab('overview')
  }, [selectedReferral?.id])

  useEffect(() => {
    if (!selectedReferral) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') dispatch({ type: 'SELECT_REFERRAL', id: null })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dispatch, selectedReferral])

  if (!selectedReferral) return null

  const referral = selectedReferral
  const evidenceField =
    referral.requiredFields.find((field) => field.key === evidenceFieldKey) ?? null
  const attentionItems = [
    ...referral.requiredFields
      .filter((field) => field.status === 'missing' || field.status === 'unclear')
      .map((field) => `${field.label}: ${field.status}`),
    ...(referral.duplicateStatus === 'probable_duplicate'
      ? ['Possible duplicate requires human resolution']
      : []),
    ...(referral.mondayPreview.blockers.length
      ? referral.mondayPreview.blockers.map((item) => `Blocker: ${item}`)
      : []),
    ...(referral.nextAction ? [`Recommended next action: ${referral.nextAction}`] : []),
  ]

  const canConfirm =
    referral.processed &&
    !referral.confirmed &&
    referral.duplicateStatus !== 'probable_duplicate' &&
    referral.outcome !== 'needs_information' &&
    referral.outcome !== 'needs_clarification'

  const canSendMonday =
    referral.confirmed &&
    referral.mondayStatus !== 'created' &&
    referral.mondayStatus !== 'creating' &&
    referral.duplicateStatus !== 'probable_duplicate' &&
    referral.mondayPreview.blockers.length === 0

  return (
    <div
      className="workspace-backdrop"
      role="presentation"
      onClick={() => dispatch({ type: 'SELECT_REFERRAL', id: null })}
    >
      <div
        className="workspace panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="workspace-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="workspace__header">
          <div>
            <p className="caption">Referral workspace</p>
            <h2 id="workspace-title">{referral.patientName}</h2>
            <p className="muted">{referral.clinicalSummary}</p>
          </div>
          <div className="workspace__header-actions">
            <OutcomeBadge
              outcome={referral.outcome}
              duplicateStatus={referral.duplicateStatus}
              confirmed={referral.confirmed}
              processed={referral.processed}
            />
            <button
              type="button"
              className="btn btn-ghost"
              aria-label="Close referral workspace"
              onClick={() => dispatch({ type: 'SELECT_REFERRAL', id: null })}
            >
              <X size={18} aria-hidden="true" />
              Close
            </button>
          </div>
        </header>

        {attentionItems.length > 0 ? (
          <aside className="workspace__attention" aria-label="Needs attention">
            <h3>Needs attention</h3>
            <ul>
              {attentionItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </aside>
        ) : null}

        <div className="workspace__tabs" role="tablist" aria-label="Referral panels">
          {(
            [
              ['overview', 'Overview'],
              ['monday', 'Monday.com'],
              ['drk', 'DRK draft'],
              ['confirm', 'Confirmation'],
              ['timeline', 'Audit timeline'],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={activeTab === id}
              className={`btn ${activeTab === id ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveTab(id)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="workspace__body">
          <div className="workspace__pdf">
            <PdfViewer
              referral={referral}
              focusPage={evidenceField?.evidencePage}
            />
          </div>

          <div className="workspace__details">
            {activeTab === 'overview' ? (
              <>
                <section>
                  <h3>Seven-field readiness</h3>
                  <ul className="readiness-list">
                    {referral.requiredFields.map((field) => (
                      <li key={field.key}>
                        <div>
                          <strong>{field.label}</strong>
                          <p>{field.value}</p>
                        </div>
                        <div className="readiness-list__actions">
                          <FieldStatusBadge status={field.status} />
                          <button
                            type="button"
                            className="btn btn-ghost"
                            onClick={() => setEvidenceFieldKey(field.key)}
                          >
                            View source
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>

                {evidenceField ? (
                  <section className="evidence-panel" aria-label="Evidence panel">
                    <h3>Evidence</h3>
                    <p>
                      <strong>Page:</strong> {evidenceField.evidencePage}
                    </p>
                    <p>
                      <strong>Quote:</strong> “{evidenceField.evidenceQuote}”
                    </p>
                    <p>
                      <strong>Confidence:</strong> {Math.round(evidenceField.confidence * 100)}%
                    </p>
                    <p>
                      <strong>Verification:</strong> Source verified
                    </p>
                  </section>
                ) : null}

                <section>
                  <h3>Extracted information</h3>
                  <dl className="detail-grid">
                    <div>
                      <dt>Referral source</dt>
                      <dd>{referral.referralSource}</dd>
                    </div>
                    <div>
                      <dt>Referring provider</dt>
                      <dd>{referral.referringProvider}</dd>
                    </div>
                    <div>
                      <dt>Diagnosis</dt>
                      <dd>{referral.diagnosis}</dd>
                    </div>
                    <div>
                      <dt>Insurance</dt>
                      <dd>{referral.insurance}</dd>
                    </div>
                    <div>
                      <dt>Requested service</dt>
                      <dd>{referral.requestedService}</dd>
                    </div>
                    <div>
                      <dt>Medications</dt>
                      <dd>{referral.medications.join(', ')}</dd>
                    </div>
                    <div>
                      <dt>Allergies</dt>
                      <dd>{referral.allergies.join(', ')}</dd>
                    </div>
                    <div>
                      <dt>Clinical summary</dt>
                      <dd>{referral.clinicalSummary}</dd>
                    </div>
                  </dl>
                </section>

                {referral.duplicateCandidate ? (
                  <section className="duplicate-panel">
                    <h3>Duplicate comparison</h3>
                    <p className="badge badge-blocked">
                      Creation blocked — human resolution required.
                    </p>
                    <div className="duplicate-panel__grid">
                      <article>
                        <h4>Incoming referral</h4>
                        <p>{referral.patientName}</p>
                        <p>{referral.dateOfBirth}</p>
                        <p>{referral.phone}</p>
                        <p>{referral.address}</p>
                      </article>
                      <article>
                        <h4>Existing Monday.com record</h4>
                        <p>{referral.duplicateCandidate.name}</p>
                        <p>{referral.duplicateCandidate.dateOfBirth}</p>
                        <p>{referral.duplicateCandidate.phone}</p>
                        <p>{referral.duplicateCandidate.address}</p>
                        <p className="caption">
                          Item {referral.duplicateCandidate.mondayItemId}
                        </p>
                      </article>
                    </div>
                    <ul>
                      {referral.duplicateCandidate.matchNotes.map((note) => (
                        <li key={note}>{note}</li>
                      ))}
                    </ul>
                    <div className="workspace__actions">
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={referral.duplicateStatus !== 'probable_duplicate'}
                        onClick={() =>
                          dispatch({
                            type: 'RESOLVE_DUPLICATE',
                            id: referral.id,
                            decision: 'different',
                          })
                        }
                      >
                        Mark as different patient
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() =>
                          dispatch({
                            type: 'RESOLVE_DUPLICATE',
                            id: referral.id,
                            decision: 'keep_blocked',
                          })
                        }
                      >
                        Keep blocked
                      </button>
                      <button type="button" className="btn btn-ghost" disabled>
                        Open existing record
                      </button>
                    </div>
                    <DuplicateBadge status={referral.duplicateStatus} />
                  </section>
                ) : null}

                {(referral.outcome === 'needs_information' ||
                  referral.outcome === 'needs_clarification') && (
                  <section>
                    <h3>Follow-up</h3>
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={referral.followUpPrepared}
                      onClick={() =>
                        dispatch({ type: 'PREPARE_FOLLOW_UP', id: referral.id })
                      }
                    >
                      Prepare follow-up
                    </button>
                    {referral.followUpPrepared ? (
                      <div className="follow-up-box">
                        <p>
                          <strong>Owner:</strong> {referral.followUpOwner}
                        </p>
                        <p>
                          <strong>Status:</strong> Follow-up prepared
                        </p>
                        <p>{referral.followUpMessage}</p>
                      </div>
                    ) : null}
                  </section>
                )}

                <section className="impact-receipt">
                  <h3>Automation-impact receipt</h3>
                  <ul>
                    <li>{referral.impactReceipt.pagesAnalyzed} pages analyzed</li>
                    <li>
                      {referral.impactReceipt.valuesExtracted} patient and clinical values
                      extracted
                    </li>
                    <li>
                      {referral.impactReceipt.requiredFieldsVerified} required fields verified
                    </li>
                    <li>
                      {referral.impactReceipt.duplicateSearches} duplicate search completed
                    </li>
                    <li>
                      {referral.impactReceipt.destinationRecordsPrepared} destination records
                      prepared
                    </li>
                    <li>
                      {referral.impactReceipt.manualActionsAvoided} repetitive manual actions
                      avoided
                    </li>
                    <li>
                      {referral.impactReceipt.minutesReturned} estimated minutes returned to
                      staff
                    </li>
                  </ul>
                </section>
              </>
            ) : null}

            {activeTab === 'monday' ? (
              <section>
                <h3>Monday.com preview</h3>
                <dl className="detail-grid">
                  <div>
                    <dt>Item name</dt>
                    <dd>{referral.mondayPreview.itemName}</dd>
                  </div>
                  <div>
                    <dt>Board</dt>
                    <dd>{referral.mondayPreview.board}</dd>
                  </div>
                  <div>
                    <dt>Group</dt>
                    <dd>{referral.mondayPreview.group}</dd>
                  </div>
                  <div>
                    <dt>Agency relation</dt>
                    <dd>{referral.mondayPreview.agencyRelation}</dd>
                  </div>
                  <div>
                    <dt>Write status</dt>
                    <dd>{referral.mondayStatus.replaceAll('_', ' ')}</dd>
                  </div>
                  <div>
                    <dt>Approval status</dt>
                    <dd>{referral.confirmed ? 'Confirmed' : 'Awaiting confirmation'}</dd>
                  </div>
                </dl>
                <h4>Column values</h4>
                <ul>
                  {referral.mondayPreview.columns.map((column) => (
                    <li key={column.label}>
                      <strong>{column.label}:</strong> {column.value}
                    </li>
                  ))}
                </ul>
                <p>
                  <strong>Update/comment:</strong> {referral.mondayPreview.updateComment}
                </p>
                {referral.mondayPreview.blockers.length > 0 ? (
                  <p className="badge badge-blocked">
                    Blockers: {referral.mondayPreview.blockers.join('; ')}
                  </p>
                ) : null}
                <div className="workspace__actions">
                  <button type="button" className="btn btn-secondary" disabled={!canConfirm}>
                    Preview Record
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!canConfirm}
                    onClick={() => dispatch({ type: 'CONFIRM_REFERRAL', id: referral.id })}
                  >
                    Confirm Referral
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!canSendMonday}
                    onClick={() => {
                      dispatch({ type: 'SEND_TO_MONDAY', id: referral.id })
                      window.setTimeout(() => {
                        dispatch({
                          type: 'MONDAY_CREATED',
                          id: referral.id,
                          itemId: `DEMO-${Math.floor(100000 + Math.random() * 900000)}`,
                        })
                      }, 900)
                    }}
                  >
                    Send to Monday.com
                  </button>
                  <a
                    className="btn btn-secondary"
                    href={referral.mondayPreview.demoUrl ?? '#'}
                    aria-disabled={!referral.mondayPreview.demoUrl}
                    onClick={(event) => {
                      if (!referral.mondayPreview.demoUrl) event.preventDefault()
                    }}
                  >
                    Open Record
                  </a>
                </div>
                {referral.mondayStatus === 'created' ? (
                  <p className="badge badge-ready">
                    Monday.com item created successfully · {referral.mondayPreview.itemId}
                  </p>
                ) : null}
              </section>
            ) : null}

            {activeTab === 'drk' ? (
              <section>
                <h3>DRK draft preview</h3>
                <p className="badge badge-planned">
                  Draft prepared — DRK chart ready · Create Patient remains human-controlled.
                </p>
                <dl className="detail-grid">
                  {[
                    ...referral.drkDraft.demographics,
                    ...referral.drkDraft.contact,
                    ...referral.drkDraft.address,
                    ...referral.drkDraft.emergencyContact,
                    ...referral.drkDraft.admission,
                    ...referral.drkDraft.insurance,
                  ].map((row) => (
                    <div key={row.label}>
                      <dt>{row.label}</dt>
                      <dd>{row.value}</dd>
                    </div>
                  ))}
                  <div>
                    <dt>Requested service</dt>
                    <dd>{referral.drkDraft.requestedService}</dd>
                  </div>
                  <div>
                    <dt>Duplicate check</dt>
                    <dd>{referral.drkDraft.duplicateCheck}</dd>
                  </div>
                  <div>
                    <dt>DRK status</dt>
                    <dd>{referral.drkStatus.replaceAll('_', ' ')}</dd>
                  </div>
                </dl>
                <p>
                  <strong>Diagnoses:</strong> {referral.drkDraft.diagnoses.join(', ')}
                </p>
                {referral.drkDraft.unresolvedLookups.length > 0 ? (
                  <p>
                    <strong>Unresolved lookups:</strong>{' '}
                    {referral.drkDraft.unresolvedLookups.join(', ')}
                  </p>
                ) : null}
                <div className="workspace__actions">
                  <button type="button" className="btn btn-secondary">
                    Preview DRK Draft
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!referral.confirmed}
                    onClick={() =>
                      dispatch({ type: 'MARK_DRK_ASSISTED', id: referral.id })
                    }
                  >
                    Open DRK Assisted Entry
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!referral.confirmed}
                    onClick={() =>
                      dispatch({ type: 'MARK_DRK_FACE_SHEET', id: referral.id })
                    }
                  >
                    Mark Ready for Face-Sheet Team
                  </button>
                </div>
              </section>
            ) : null}

            {activeTab === 'confirm' ? (
              <section className="confirm-panel">
                <h3>Confirmation</h3>
                <article className="outlook-preview">
                  <p>
                    <strong>Subject:</strong> Referral Review: {referral.patientName}
                  </p>
                  <p>
                    <strong>To:</strong> {referral.sender}
                  </p>
                  <p>
                    Please review the extracted referral and reply <em>Confirm</em> to approve
                    the Monday.com handoff and DRK draft preparation.
                  </p>
                </article>
                <label className="confirm-panel__reply">
                  Reply
                  <textarea
                    defaultValue="Confirm"
                    rows={3}
                    aria-label="Review reply"
                  />
                </label>
                <div className="workspace__actions">
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!canConfirm}
                    onClick={() => dispatch({ type: 'CONFIRM_REFERRAL', id: referral.id })}
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() =>
                      dispatch({ type: 'REQUEST_CORRECTION', id: referral.id })
                    }
                  >
                    Request correction
                  </button>
                </div>
                {referral.confirmed ? (
                  <pre className="confirm-checklist">
{`Confirmation recorded
✓ Authorized sender matched
✓ Original email thread matched
✓ Review snapshot validated
✓ Seven required fields complete
✓ No blocking duplicate detected
✓ Monday.com handoff ready
✓ DRK draft ready`}
                  </pre>
                ) : null}
              </section>
            ) : null}

            {activeTab === 'timeline' ? (
              <section>
                <h3>Activity / audit timeline</h3>
                <ol className="timeline">
                  {referral.timeline.map((event) => (
                    <li key={event.id}>
                      <div>
                        <strong>{event.label}</strong>
                        <p>{event.result}</p>
                      </div>
                      <div className="timeline__meta">
                        <span>{event.timestamp}</span>
                        <span>{event.actor}</span>
                        <span>
                          {event.humanRequired ? 'Human required' : 'Automated'}
                        </span>
                      </div>
                    </li>
                  ))}
                </ol>
              </section>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}
