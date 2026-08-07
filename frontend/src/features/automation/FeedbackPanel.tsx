import { useState } from 'react'
import type { MicrostepFeedback } from './types'
import './FeedbackPanel.css'

type FeedbackCategory = MicrostepFeedback['category']

const CATEGORY_LABELS: Record<FeedbackCategory, string> = {
  'incorrect-output': 'Incorrect output',
  'missing-context': 'Missing context',
  'workflow-change': 'Workflow change',
  question: 'Question',
}

export function FeedbackPanel({
  feedback,
  onAdd,
}: {
  feedback: MicrostepFeedback[]
  onAdd: (category: FeedbackCategory, comment: string) => void
}) {
  const [category, setCategory] = useState<FeedbackCategory>('incorrect-output')
  const [comment, setComment] = useState('')

  const submit = () => {
    const clean = comment.trim()
    if (!clean) return
    onAdd(category, clean)
    setComment('')
  }

  return (
    <section className="feedback-panel" aria-labelledby="feedback-panel-title">
      <div>
        <p className="caption">Step-level feedback</p>
        <h3 id="feedback-panel-title">Comment on this microstep</h3>
        <p className="muted">
          This prototype keeps comments in the browser. The functional version
          will persist them by workflow run and microstep.
        </p>
      </div>
      <div className="feedback-panel__form">
        <label>
          Feedback type
          <select
            value={category}
            onChange={(event) =>
              setCategory(event.target.value as FeedbackCategory)
            }
          >
            {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Comment
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="Describe what looks wrong or what should change."
            rows={3}
          />
        </label>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={!comment.trim()}
          onClick={submit}
        >
          Add feedback
        </button>
      </div>
      {feedback.length > 0 ? (
        <ul
          className="feedback-panel__comments"
          aria-label="Comments on this microstep"
        >
          {feedback.map((item) => (
            <li key={item.id}>
              <span>{CATEGORY_LABELS[item.category]}</span>
              <p>{item.comment}</p>
              <time>{item.createdAt}</time>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
