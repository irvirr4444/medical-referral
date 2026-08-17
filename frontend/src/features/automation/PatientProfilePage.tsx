import { ArtifactSections } from './ArtifactSections'
import { cityFromAddress, displayValue } from './livePatient'
import { navigateAppPath } from './patientRoute'
import { PatientWorkflowPipeline } from './PatientWorkflowPipeline'
import { useLivePatient } from './useLivePatient'
import { useDemo } from '../../state/useDemo'
import './PatientProfilePage.css'

export function PatientProfilePage({ patientKey }: { patientKey: string }) {
  const live = useLivePatient(patientKey)
  const settled = !live.mondayLoading && !live.drkLoading
  const hasLive = Boolean(live.monday || live.drk)

  if (settled && !hasLive && (live.mondayStatus === 409 || live.drkStatus === 409)) {
    return (
      <main className="patient-profile panel" aria-labelledby="patient-profile-title">
        <OverviewBack />
        <h1 id="patient-profile-title">Multiple matches</h1>
        <p className="muted">More than one Monday or DRK patient matches this URL.</p>
        <CandidateList
          label="Monday"
          candidates={live.mondayBody?.candidates?.monday}
        />
        <CandidateList label="DRK" candidates={live.drkBody?.candidates?.drk} />
      </main>
    )
  }

  if (settled && !hasLive && live.mondayStatus === 404 && live.drkStatus === 404) {
    return (
      <main className="patient-profile panel" aria-labelledby="patient-profile-title">
        <OverviewBack />
        <h1 id="patient-profile-title">Patient not found</h1>
        <p className="muted">No patient matches this URL in Monday or DRK.</p>
      </main>
    )
  }

  if (settled && !hasLive) {
    return (
      <main className="patient-profile panel" aria-labelledby="patient-profile-title">
        <OverviewBack />
        <h1 id="patient-profile-title">Patient lookup failed</h1>
        <p className="muted">
          {live.mondayError || live.drkError || 'The patient API is unavailable.'}
        </p>
      </main>
    )
  }

  const monday = live.monday
  const drk = live.drk
  const patientName =
    monday?.name ||
    drk?.name ||
    (live.mondayLoading || live.drkLoading ? 'Loading…' : 'Patient')
  const dob = monday?.dob || drk?.dob
  const phone = monday?.phone || drk?.phone
  const city = cityFromAddress(monday?.address) || drk?.city
  const sentBy = monday?.sent_by
  const sections = drk?.sections ?? []

  const mondayOps = [
    ['Referral sent', live.mondayLoading ? 'Loading…' : displayValue(monday?.referral_sent)],
    ['Appointment', live.mondayLoading ? 'Loading…' : displayValue(monday?.appointment)],
    ['Scheduled', live.mondayLoading ? 'Loading…' : displayValue(monday?.scheduled)],
    [
      'Scheduled complete',
      live.mondayLoading ? 'Loading…' : displayValue(monday?.scheduled_complete),
    ],
    ['Visit', live.mondayLoading ? 'Loading…' : displayValue(monday?.visit)],
    ['Sent to CM', live.mondayLoading ? 'Loading…' : displayValue(monday?.sent_to_cm)],
    ['POS', live.mondayLoading ? 'Loading…' : displayValue(monday?.pos)],
    ['Address', live.mondayLoading ? 'Loading…' : displayValue(monday?.address)],
    ['Due date', live.mondayLoading ? 'Loading…' : displayValue(monday?.due_date)],
    ['Stage', live.mondayLoading ? 'Loading…' : displayValue(monday?.stage)],
    ['Referral received', live.mondayLoading ? 'Loading…' : displayValue(monday?.referral_received)],
    ['QA hold', live.mondayLoading ? 'Loading…' : displayValue(monday?.qa_hold_reason)],
    ['Discharge', live.mondayLoading ? 'Loading…' : displayValue(monday?.discharge_reason)],
  ]

  const drkOps = [
    ['Status', live.drkLoading ? 'Loading…' : displayValue(drk?.status)],
    ['MRN', live.drkLoading ? 'Loading…' : displayValue(drk?.mrn)],
    ['Facility', live.drkLoading ? 'Loading…' : displayValue(drk?.facility)],
    ['Provider', live.drkLoading ? 'Loading…' : displayValue(drk?.provider)],
    ['Last visit', live.drkLoading ? 'Loading…' : displayValue(drk?.visit)],
    ['Appointment', live.drkLoading ? 'Loading…' : displayValue(drk?.appointment)],
    ['Home health', live.drkLoading ? 'Loading…' : displayValue(drk?.home_health)],
    ['Email', live.drkLoading ? 'Loading…' : displayValue(drk?.email)],
  ]

  return (
    <main className="patient-profile panel" aria-labelledby="patient-profile-title">
      <OverviewBack />
      <header className="patient-profile__now">
        <h1 id="patient-profile-title">{patientName}</h1>
        <p className="patient-profile__identity">
          DOB {displayValue(dob)} · {displayValue(phone)} · {displayValue(city)}
        </p>
        {sentBy ? (
          <div className="patient-profile__pdf">
            <p className="patient-profile__sent-by">Sent by {sentBy}</p>
          </div>
        ) : null}
      </header>

      <PatientWorkflowPipeline key={patientKey} patientKey={patientKey} />

      <section className="patient-profile__people" aria-label="People">
        <div>
          <p className="patient-profile__label">Case manager</p>
          <p className="patient-profile__name">
            {live.mondayLoading ? 'Loading…' : displayValue(monday?.case_manager)}
          </p>
        </div>
        <div>
          <p className="patient-profile__label">Provider</p>
          <p className="patient-profile__name">
            {live.mondayLoading && live.drkLoading
              ? 'Loading…'
              : displayValue(monday?.provider || drk?.provider)}
          </p>
        </div>
        <div>
          <p className="patient-profile__label">Referral source</p>
          <p className="patient-profile__name">
            {live.mondayLoading ? 'Loading…' : displayValue(monday?.agency_contact)}
          </p>
          {!live.mondayLoading && monday?.agency_phone ? (
            <p className="patient-profile__identity">{monday.agency_phone}</p>
          ) : null}
        </div>
      </section>

      <section aria-label="Monday ops">
        <p className="patient-profile__label">Monday</p>
        {live.mondayError && !monday ? (
          <p className="muted">{live.mondayError}</p>
        ) : (
          <dl className="patient-profile__monday-ops">
            {mondayOps.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      <section aria-label="DRK chart">
        <p className="patient-profile__label">DRK</p>
        {live.drkStatus === 404 && !live.drkLoading ? (
          <p className="muted">Not in DRK</p>
        ) : live.drkError && !drk ? (
          <p className="muted">{live.drkError}</p>
        ) : (
          <dl className="patient-profile__monday-ops">
            {drkOps.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      <details className="patient-profile__disclosure" open={Boolean(sections.length) || live.drkLoading}>
        <summary>Chart details</summary>
        {live.drkLoading ? (
          <p className="muted">Loading DRK chart…</p>
        ) : sections.length ? (
          <ArtifactSections
            sections={sections}
            artifactId={`${drk?.patient_id ?? patientKey}-chart`}
            density="feed"
          />
        ) : (
          <p className="muted">No DRK chart details captured for this patient.</p>
        )}
      </details>
    </main>
  )
}

function OverviewBack() {
  const { dispatch } = useDemo()
  return (
    <button
      type="button"
      className="patient-profile__back"
      onClick={() => {
        navigateAppPath('/')
        dispatch({ type: 'SET_ACTIVE_PAGE', page: 'overview' })
      }}
    >
      Overview
    </button>
  )
}

function CandidateList({
  label,
  candidates,
}: {
  label: string
  candidates?: Array<{ name: string; dob?: string; item_id?: string; patient_id?: string }>
}) {
  if (!candidates?.length) return null
  return (
    <section aria-label={`${label} candidates`}>
      <p className="patient-profile__label">{label}</p>
      <ul>
        {candidates.map((item) => (
          <li key={item.item_id || item.patient_id || item.name}>
            {item.name}
            {item.dob ? ` · ${item.dob}` : ''}
          </li>
        ))}
      </ul>
    </section>
  )
}
