import { ArrowLeft, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  getPatientProfile,
  type PatientProfileViewModel,
} from '../data/patientProfiles'
import { useDemo } from '../state/useDemo'
import './PatientProfilePage.css'

function DetailItem({
  label,
  value,
}: {
  label: string
  value: string | number | null | undefined
}) {
  return (
    <div className="patient-profile__detail">
      <dt>{label}</dt>
      <dd>{value || 'Not documented'}</dd>
    </div>
  )
}

type ProfileDetailModal = 'clinical' | 'diagnoses' | 'insurance' | null

function PatientProfileContent({
  profile,
}: {
  profile: PatientProfileViewModel
}) {
  const [detailModal, setDetailModal] = useState<ProfileDetailModal>(null)
  const titleId = 'patient-profile-title'
  const { identity } = profile

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [profile.profileId])

  useEffect(() => {
    if (!detailModal) return

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        setDetailModal(null)
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [detailModal])

  const closeDetailModal = () => setDetailModal(null)

  const primaryDiagnosis = profile.diagnoses.find((item) => item.isPrimary)
  const primaryInsurance = profile.insurances[0]

  const modalTitle =
    detailModal === 'clinical'
      ? 'Clinical summary'
      : detailModal === 'diagnoses'
        ? 'Diagnosis'
        : 'Insurance'

  const modalSubtitle =
    detailModal === 'clinical'
      ? 'Referral clinical overview'
      : detailModal === 'diagnoses'
        ? `${profile.diagnoses.length} documented diagnoses`
        : `${profile.insurances.length} insurance ${
            profile.insurances.length === 1 ? 'record' : 'records'
          }`

  return (
    <main className="patient-profile-page" aria-labelledby={titleId}>
      <header className="patient-profile__hero panel">
        <div className="patient-profile__identity">
          <span className="patient-profile__avatar" aria-hidden="true">
            {identity.displayName
              .split(' ')
              .map((part) => part[0])
              .join('')
              .slice(0, 2)}
          </span>
          <div>
            <p className="caption">Patient profile</p>
            <h1 id={titleId}>{identity.displayName}</h1>
            <p className="patient-profile__legal-name">{identity.legalName}</p>
          </div>
        </div>

        <dl className="patient-profile__identity-grid">
          <DetailItem label="Date of birth" value={identity.dateOfBirth} />
          <DetailItem label="Age" value={identity.age} />
          <DetailItem label="Sex / gender" value={identity.sexOrGender} />
          <DetailItem label="Phone" value={identity.phone} />
          <DetailItem label="Email" value={identity.email} />
          <DetailItem label="Address" value={identity.address} />
          <DetailItem
            label={identity.sourcePatientIdLabel ?? 'Source patient ID'}
            value={identity.sourcePatientId}
          />
          <DetailItem label="MRN" value={identity.mrn} />
        </dl>
      </header>

      <div className="patient-profile__body">
        <div className="patient-profile__layout">
          <aside className="patient-profile__rail">
            {profile.workflow ? (
              <section
                className="patient-profile__section panel"
                aria-labelledby={`${titleId}-workflow`}
              >
                <div className="patient-profile__section-heading">
                  <h2 id={`${titleId}-workflow`}>Workflow status</h2>
                </div>
                <p className="patient-profile__summary">
                  {profile.workflow.summary}
                </p>

                <dl className="patient-profile__detail-grid patient-profile__detail-grid--stack">
                  <DetailItem
                    label="Current stage"
                    value={profile.workflow.currentStageTitle}
                  />
                  <DetailItem
                    label="Current step"
                    value={`Step ${profile.workflow.currentStepNumber} of ${profile.workflow.currentStepCount}: ${profile.workflow.currentStepName}`}
                  />
                  <DetailItem
                    label="Monday.com"
                    value={
                      profile.workflow.monday.present
                        ? `In Monday.com${
                            profile.workflow.monday.recordId
                              ? ` · ${profile.workflow.monday.recordId}`
                              : ''
                          }`
                        : profile.workflow.monday.label
                    }
                  />
                  <DetailItem
                    label="DRK"
                    value={
                      profile.workflow.drk.present
                        ? `In DRK${
                            profile.workflow.drk.recordId
                              ? ` · ${profile.workflow.drk.recordId}`
                              : ''
                          }`
                        : profile.workflow.drk.label
                    }
                  />
                </dl>

                <h3>Stages</h3>
                <ol className="patient-profile__stages">
                  {profile.workflow.stages.map((stage) => (
                    <li
                      key={stage.stageId}
                      className={`patient-profile__stage is-${stage.status}`}
                    >
                      <span className="patient-profile__stage-status">
                        {stage.status === 'completed'
                          ? 'Done'
                          : stage.status === 'current'
                            ? 'Current'
                            : 'Next'}
                      </span>
                      <span className="patient-profile__stage-copy">
                        <strong>{stage.stageTitle}</strong>
                        {stage.status === 'current' && stage.currentStepName ? (
                          <small>
                            Step {stage.currentStepNumber} of {stage.stepCount}:{' '}
                            {stage.currentStepName}
                          </small>
                        ) : (
                          <small>{stage.stepCount} steps</small>
                        )}
                      </span>
                    </li>
                  ))}
                </ol>
              </section>
            ) : null}
          </aside>

          <div className="patient-profile__main">
            <div className="patient-profile__topic-row">
              <button
                type="button"
                className="patient-profile__topic-card panel"
                onClick={() => setDetailModal('clinical')}
                aria-label="Open clinical summary details"
              >
                <h2>Clinical summary</h2>
                <p>
                  {profile.clinicalSummary
                    ? profile.clinicalSummary.length > 140
                      ? `${profile.clinicalSummary.slice(0, 140).trim()}…`
                      : profile.clinicalSummary
                    : 'Not documented'}
                </p>
                <span className="patient-profile__open-hint">View details</span>
              </button>

              <button
                type="button"
                className="patient-profile__topic-card panel"
                onClick={() => setDetailModal('diagnoses')}
                aria-label="Open diagnosis details"
              >
                <h2>Diagnosis</h2>
                {profile.diagnoses.length > 0 ? (
                  <>
                    <p>
                      <strong>
                        {profile.diagnoses.length} diagnoses
                        {primaryDiagnosis?.code
                          ? ` · Primary ${primaryDiagnosis.code}`
                          : ''}
                      </strong>
                    </p>
                    <p className="patient-profile__topic-meta">
                      {profile.diagnoses
                        .slice(0, 3)
                        .map(
                          (item) =>
                            item.code ?? item.description ?? 'Undocumented',
                        )
                        .join(' · ')}
                      {profile.diagnoses.length > 3
                        ? ` · +${profile.diagnoses.length - 3} more`
                        : ''}
                    </p>
                  </>
                ) : (
                  <p>No diagnoses documented</p>
                )}
                <span className="patient-profile__open-hint">View details</span>
              </button>

              <button
                type="button"
                className="patient-profile__topic-card panel"
                onClick={() => setDetailModal('insurance')}
                aria-label="Open insurance details"
              >
                <h2>Insurance</h2>
                {primaryInsurance ? (
                  <>
                    <p>
                      <strong>
                        {[
                          primaryInsurance.payerName,
                          primaryInsurance.insuranceType,
                        ]
                          .filter(Boolean)
                          .join(' · ') || 'Insurance on file'}
                      </strong>
                    </p>
                    <p className="patient-profile__topic-meta">
                      {profile.insurances.length > 1
                        ? `${profile.insurances.length} payers on file`
                        : primaryInsurance.policyNumber || 'Policy on file'}
                    </p>
                  </>
                ) : (
                  <p>No insurance documented</p>
                )}
                <span className="patient-profile__open-hint">View details</span>
              </button>
            </div>

            <section
              className="patient-profile__services-card panel"
              aria-labelledby={`${titleId}-services`}
            >
              <h2 id={`${titleId}-services`}>Requested service</h2>
              {profile.requestedServices.length > 0 ? (
                <ul className="patient-profile__services patient-profile__services--row">
                  {profile.requestedServices.map((service, index) => (
                    <li key={`${service.service}-${index}`}>
                      <strong>{service.service ?? 'Service'}</strong>
                      <span>
                        {[service.frequency, service.instructions]
                          .filter(Boolean)
                          .join(' · ') || 'No details documented'}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="patient-profile__unavailable">
                  No requested services documented in the canonical referral.
                </p>
              )}
            </section>
          </div>
        </div>
      </div>

      {detailModal ? (
        <div
          className="patient-profile__backdrop"
          role="presentation"
          onClick={closeDetailModal}
        >
          <section
            className="patient-profile__modal panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="patient-profile-detail-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="patient-profile__modal-header">
              <div>
                <h2 id="patient-profile-detail-title">{modalTitle}</h2>
                <p className="muted">{modalSubtitle}</p>
              </div>
              <button
                type="button"
                className="patient-profile__modal-close"
                aria-label="Close details"
                onClick={closeDetailModal}
              >
                <X size={16} aria-hidden="true" />
              </button>
            </header>

            {detailModal === 'clinical' ? (
              <div className="patient-profile__modal-body">
                <p className="patient-profile__summary">
                  {profile.clinicalSummary ?? 'Not documented'}
                </p>
                {profile.clinicalNotes.length > 0 ? (
                  <>
                    <h3>Clinical notes</h3>
                    <ul className="patient-profile__notes">
                      {profile.clinicalNotes.map((note) => (
                        <li key={note}>{note}</li>
                      ))}
                    </ul>
                  </>
                ) : null}
              </div>
            ) : null}

            {detailModal === 'diagnoses' ? (
              <div className="patient-profile__modal-body">
                {profile.diagnoses.length > 0 ? (
                  <ul className="patient-profile__diagnoses">
                    {profile.diagnoses.map((diagnosis) => (
                      <li key={`${diagnosis.code}-${diagnosis.description}`}>
                        <strong>
                          {diagnosis.code ?? '—'}
                          {diagnosis.isPrimary ? ' · Primary' : ''}
                        </strong>
                        <span>
                          {diagnosis.description ?? 'Not documented'}
                        </span>
                        {diagnosis.status ? (
                          <small>{diagnosis.status}</small>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="patient-profile__unavailable">
                    No diagnoses documented in the canonical referral.
                  </p>
                )}
              </div>
            ) : null}

            {detailModal === 'insurance' ? (
              <div className="patient-profile__modal-body">
                {profile.insurances.length > 0 ? (
                  <ul className="patient-profile__insurances">
                    {profile.insurances.map((insurance) => (
                      <li
                        key={`${insurance.payerName}-${insurance.policyNumber}`}
                      >
                        <strong>
                          {[insurance.payerName, insurance.insuranceType]
                            .filter(Boolean)
                            .join(' · ')}
                        </strong>
                        <span>
                          {[insurance.policyNumber, insurance.groupNumber]
                            .filter(Boolean)
                            .join(' · ') || 'Not documented'}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="patient-profile__unavailable">
                    No insurance documented in the canonical referral.
                  </p>
                )}
              </div>
            ) : null}
          </section>
        </div>
      ) : null}
    </main>
  )
}

export function PatientProfilePage() {
  const { profileId } = useParams<{ profileId: string }>()
  const { dispatch } = useDemo()
  const navigate = useNavigate()
  const profile = getPatientProfile(profileId)

  if (!profile) {
    return (
      <main className="patient-profile-page panel">
        <header className="patient-profile__hero">
          <button
            type="button"
            className="patient-profile__back"
            onClick={() => {
              dispatch({ type: 'CLOSE_PATIENT_PROFILE', reopenList: false })
              navigate('/')
            }}
          >
            <ArrowLeft size={16} aria-hidden="true" />
            Back
          </button>
          <h1>Patient profile unavailable</h1>
          <p className="muted">
            This patient does not have a profile in the current demo.
          </p>
        </header>
      </main>
    )
  }

  return <PatientProfileContent profile={profile} />
}
