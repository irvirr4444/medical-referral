import { COPY, computeImpact } from '../data/constants'
import { useDemo } from '../state/useDemo'
import './CapacityCalculator.css'

export function CapacityCalculator() {
  const { state, dispatch } = useDemo()
  const a = state.impactAssumptions
  const projection = computeImpact(a)

  return (
    <section className="capacity panel" aria-labelledby="capacity-heading">
      <div className="section-heading">
        <div>
          <h2 id="capacity-heading">Annual capacity projection</h2>
          <p className="muted">{COPY.capacityCaption}</p>
        </div>
      </div>

      <div className="capacity__grid">
        <label>
          Referrals / day
          <input
            type="number"
            min={1}
            value={a.referralsPerDay}
            onChange={(event) =>
              dispatch({
                type: 'UPDATE_IMPACT_ASSUMPTIONS',
                patch: { referralsPerDay: Number(event.target.value) || 0 },
              })
            }
          />
        </label>
        <label>
          Manual minutes / referral
          <input
            type="number"
            min={1}
            value={a.manualMinutes}
            onChange={(event) =>
              dispatch({
                type: 'UPDATE_IMPACT_ASSUMPTIONS',
                patch: { manualMinutes: Number(event.target.value) || 0 },
              })
            }
          />
        </label>
        <label>
          Assisted minutes / referral
          <input
            type="number"
            min={1}
            value={a.assistedMinutes}
            disabled
            readOnly
            aria-label="Assisted minutes per referral (fixed at 8)"
            title="Fixed at 8 minutes of focused review"
          />
        </label>
        <label>
          Working days / year
          <input
            type="number"
            min={1}
            value={a.workingDaysPerYear}
            onChange={(event) =>
              dispatch({
                type: 'UPDATE_IMPACT_ASSUMPTIONS',
                patch: { workingDaysPerYear: Number(event.target.value) || 0 },
              })
            }
          />
        </label>
        <label>
          Annual productive hours / employee
          <input
            type="number"
            min={1}
            value={a.annualProductiveHours}
            onChange={(event) =>
              dispatch({
                type: 'UPDATE_IMPACT_ASSUMPTIONS',
                patch: { annualProductiveHours: Number(event.target.value) || 0 },
              })
            }
          />
        </label>
      </div>

      <div className="capacity__results">
        <article>
          <strong>{projection.minutesReturnedPerReferral}</strong>
          <span>Minutes returned / referral</span>
        </article>
        <article>
          <strong>{projection.hoursPerDay.toFixed(1)}</strong>
          <span>Hours / day</span>
        </article>
        <article>
          <strong>{projection.hoursPerWeek.toFixed(1)}</strong>
          <span>Hours / week</span>
        </article>
        <article>
          <strong>{Math.round(projection.hoursPerYear)}</strong>
          <span>Hours / year</span>
        </article>
        <article>
          <strong>{projection.addedReferralCapacity}</strong>
          <span>Added annual referral capacity</span>
        </article>
        <article>
          <strong>{projection.fteEquivalent.toFixed(1)}</strong>
          <span>Full-time staff capacity returned</span>
        </article>
      </div>
    </section>
  )
}
