import { useDemo } from '../state/useDemo'
import type { QueueFilter } from '../types'
import { DuplicateBadge, OutcomeBadge } from './StatusBadges'
import './ReferralQueue.css'

const FILTERS: Array<{ id: QueueFilter; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'ready', label: 'Ready' },
  { id: 'needs_information', label: 'Needs information' },
  { id: 'possible_duplicate', label: 'Possible duplicate' },
  { id: 'confirmed', label: 'Confirmed' },
]

export function ReferralQueue() {
  const { state, dispatch, filteredReferrals } = useDemo()
  const queueReferrals = filteredReferrals.filter((referral) => referral.inboxBatch)

  return (
    <section className="referral-queue panel" aria-labelledby="queue-heading">
      <div className="section-heading">
        <div>
          <h2 id="queue-heading">Referral inbox</h2>
          <p className="muted">New emails waiting for intake processing and human confirmation.</p>
        </div>
      </div>

      <div className="referral-queue__filters" role="toolbar" aria-label="Referral filters">
        {FILTERS.map((filter) => (
          <button
            key={filter.id}
            type="button"
            className={`btn ${state.queueFilter === filter.id ? 'btn-primary' : 'btn-secondary'}`}
            aria-pressed={state.queueFilter === filter.id}
            onClick={() => dispatch({ type: 'SET_QUEUE_FILTER', filter: filter.id })}
          >
            {filter.label}
          </button>
        ))}
      </div>

      <ul className="referral-queue__list">
        {queueReferrals.map((referral) => (
          <li key={referral.id}>
            <article className="referral-card">
              <div className="referral-card__top">
                <div>
                  <h3>{referral.patientName}</h3>
                  <p className="muted">{referral.subject}</p>
                </div>
                <OutcomeBadge
                  outcome={referral.outcome}
                  duplicateStatus={referral.duplicateStatus}
                  confirmed={referral.confirmed}
                  processed={referral.processed}
                />
              </div>
              <dl className="referral-card__meta">
                <div>
                  <dt>Sender</dt>
                  <dd>{referral.sender}</dd>
                </div>
                <div>
                  <dt>Received</dt>
                  <dd>{referral.receivedAt}</dd>
                </div>
                <div>
                  <dt>PDF</dt>
                  <dd>
                    {referral.pdfFilename} · {referral.pageCount} pages
                  </dd>
                </div>
                <div>
                  <dt>Completeness</dt>
                  <dd>{referral.completenessScore}</dd>
                </div>
                <div>
                  <dt>Duplicate</dt>
                  <dd>
                    <DuplicateBadge status={referral.duplicateStatus} />
                  </dd>
                </div>
                <div>
                  <dt>Stage</dt>
                  <dd>{referral.stage.replaceAll('_', ' ')}</dd>
                </div>
                <div>
                  <dt>Minutes returned</dt>
                  <dd>{referral.minutesReturned}</dd>
                </div>
              </dl>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => dispatch({ type: 'SELECT_REFERRAL', id: referral.id })}
              >
                Review Referral
              </button>
            </article>
          </li>
        ))}
      </ul>
    </section>
  )
}
