import { Activity } from 'lucide-react'
import { activityForStage, stageActivityBlurb, type ActivityStage } from '../data/activityFeed'
import { useDemo } from '../state/useDemo'
import './ActivityFeed.css'

export function ActivityFeed({ stage = 'overview' }: { stage?: ActivityStage }) {
  const { state } = useDemo()
  const events = activityForStage(state.activityFeed, stage)

  return (
    <section className="activity-feed panel" aria-labelledby={`activity-heading-${stage}`}>
      <div className="section-heading">
        <div>
          <h2 id={`activity-heading-${stage}`}>
            <Activity size={18} aria-hidden="true" /> Live activity
          </h2>
          <p className="muted">{stageActivityBlurb(stage)}</p>
        </div>
        <p className="caption">
          {stage === 'intake' || stage === 'overview'
            ? `Last inbox sync: ${state.lastInboxSyncLabel}`
            : `${events.length} events on this stage`}
        </p>
      </div>
      <ul>
        {events.map((event) => (
          <li key={event.id}>
            <time>{event.time}</time>
            <span>{event.text}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
