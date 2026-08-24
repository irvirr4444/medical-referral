import { CalendarDays, ChevronDown, ChevronRight } from 'lucide-react'
import { useMemo, useState } from 'react'
import { activityForStage } from '../../data/activityFeed'
import { bossPeriodById } from '../../data/bossMetrics'
import { STAGE_LABEL } from './ops'
import { navigateAppPath, patientKeyFromPath } from './patientRoute'
import type { ActionTimer } from '../../types'
import { useDemo } from '../../state/useDemo'
import {
  displayPatientName,
  needsYouCopy,
  needsYouDigest,
  patientFirstName,
} from './needsYou'

function opsTimestamp(date = new Date()) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
}

function lateSummary(lateTotal: number, waitingTotal: number) {
  if (waitingTotal === 0) return 'Nothing waiting on you'
  if (lateTotal === waitingTotal) {
    return waitingTotal === 1
      ? 'The 1 thing waiting on you is running late'
      : `All ${waitingTotal} things waiting on you are running late`
  }
  const waitingLabel = `${waitingTotal} waiting on you total`
  if (lateTotal === 0) return waitingLabel
  const lateLabel =
    lateTotal === 1 ? '1 thing is running late' : `${lateTotal} things are running late`
  return `${lateLabel}, ${waitingLabel}`
}

export function OverviewNeedsYou() {
  const { state, dispatch } = useDemo()
  const digest = useMemo(
    () => needsYouDigest(state.actionTimers),
    [state.actionTimers],
  )
  const todayMetrics = useMemo(() => bossPeriodById('today', 'overview'), [])
  const patientsSeen =
    todayMetrics.metrics.find((metric) => metric.id === 'patients-seen')?.value ?? 0
  const newReferrals =
    todayMetrics.metrics.find((metric) => metric.id === 'new-referrals')?.value ?? 0
  const latestEvents = activityForStage(state.activityFeed, 'overview', 5)
  const [handledOpen, setHandledOpen] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [slotByPatient, setSlotByPatient] = useState<Record<string, string>>({})

  const visible = showAll ? digest.ordered : digest.ordered.slice(0, 6)
  const late = visible.filter((timer) => timer.status === 'overdue')
  const soon = visible.filter((timer) => timer.status !== 'overdue')

  const openTask = (timer: ActionTimer, stageId = timer.stageId, stepId = timer.stepId) => {
    if (patientKeyFromPath(window.location.pathname)) {
      navigateAppPath('/')
    }
    dispatch({ type: 'SET_ACTIVE_PAGE', page: stageId })
    dispatch({ type: 'SET_OPS_SELECTED_STEP', stageId, stepId })
    dispatch({
      type: 'SCOPE_OPS_PATIENT',
      patientId: timer.patientId,
      patientName: timer.patientName,
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handlePrimary = (timer: ActionTimer) => {
    switch (timer.actionId) {
      case 'confirm-partner-contacted':
        dispatch({
          type: 'CONFIRM_PARTNER_CONTACTED',
          patientId: timer.patientId,
          patientName: timer.patientName,
          occurredAt: opsTimestamp(),
        })
        return
      case 'eod-escalate':
        openTask(timer, 'scheduling', 'schedule-patient')
        return
      case 'eod-follow-up-cm':
        dispatch({ type: 'CONFIRM_EOD_FOLLOW_UP', patientId: timer.patientId })
        return
      case 'weekly-mark-not-seen':
        dispatch({
          type: 'RESOLVE_ACTION_TIMER',
          patientId: timer.patientId,
          actionId: 'weekly-mark-not-seen',
        })
        dispatch({
          type: 'START_ACTION_TIMER',
          patientId: timer.patientId,
          patientName: timer.patientName,
          actionId: 'weekly-confirm-rescheduled',
        })
        return
      case 'weekly-escalate-dc':
      case 'weekly-confirm-rescheduled':
      case 'weekly-qa-discharge':
      case 'weekly-remove-dc':
      case 'weekly-move-holds':
        dispatch({
          type: 'RESOLVE_ACTION_TIMER',
          patientId: timer.patientId,
          actionId: timer.actionId,
        })
        return
      default:
        openTask(timer)
    }
  }

  const handleSecondary = (timer: ActionTimer) => {
    switch (timer.actionId) {
      case 'confirm-partner-contacted':
        return
      case 'eod-escalate':
        dispatch({ type: 'CONFIRM_EOD_ESCALATION', patientId: timer.patientId })
        return
      case 'weekly-escalate-dc':
        dispatch({
          type: 'RESOLVE_ACTION_TIMER',
          patientId: timer.patientId,
          actionId: 'weekly-escalate-dc',
        })
        return
      default:
        openTask(timer)
    }
  }

  const confirmSchedule = (timer: ActionTimer) => {
    const record = state.patientSchedules[timer.patientId]
    const slotId =
      slotByPatient[timer.patientId] ||
      record?.slots.find((slot) => slot.status === 'open')?.id
    if (!record || record.status !== 'waiting' || !slotId) {
      openTask(timer)
      return
    }
    dispatch({
      type: 'COMPLETE_PATIENT_SCHEDULE',
      patientId: timer.patientId,
      scheduledAt: opsTimestamp(),
      slotId,
    })
  }

  const renderTask = (timer: ActionTimer) => {
    const copy = needsYouCopy(timer.actionId)
    const name = displayPatientName(timer.patientName)
    const firstName = patientFirstName(timer.patientName)
    const schedule = state.patientSchedules[timer.patientId]
    const openSlots = schedule?.slots.filter((slot) => slot.status === 'open') ?? []
    const chosenSlotId = slotByPatient[timer.patientId] ?? ''
    const canConfirmSchedule =
      schedule?.status === 'waiting' &&
      openSlots.some((slot) => slot.id === chosenSlotId)

    return (
      <article key={timer.id} className="overview-needs__task">
        <button
          type="button"
          className="overview-needs__task-copy"
          aria-label={`Open ${name} in ${STAGE_LABEL[timer.stageId]}`}
          onClick={() => openTask(timer)}
        >
          <strong>
            {name}
            <ChevronRight
              size={14}
              strokeWidth={2}
              className="overview-needs__task-go"
              aria-hidden="true"
            />
          </strong>
          <p>{copy.prompt(firstName)}</p>
        </button>
        <div className="overview-needs__task-actions">
          {copy.variant === 'schedule' ? (
            <>
              <label className="overview-needs__when">
                <CalendarDays size={14} aria-hidden="true" />
                <select
                  value={chosenSlotId}
                  onChange={(event) =>
                    setSlotByPatient((current) => ({
                      ...current,
                      [timer.patientId]: event.target.value,
                    }))
                  }
                  aria-label={`Visit time for ${name}`}
                >
                  <option value="">Pick a time</option>
                  {openSlots.map((slot) => (
                    <option key={slot.id} value={slot.id}>
                      {slot.dateLabel} · {slot.timeLabel}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="overview-needs__action"
                disabled={!canConfirmSchedule}
                onClick={() => confirmSchedule(timer)}
              >
                {copy.primary}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="overview-needs__action"
                onClick={() => handlePrimary(timer)}
              >
                {copy.primary}
              </button>
              {copy.secondary ? (
                <button
                  type="button"
                  className="overview-needs__action"
                  onClick={() => handleSecondary(timer)}
                >
                  {copy.secondary}
                </button>
              ) : null}
            </>
          )}
        </div>
      </article>
    )
  }

  return (
    <section className="overview-needs panel" aria-labelledby="overview-needs-title">
      <div className="overview-needs__heading">
        <p className={`overview-needs__pulse${digest.lateTotal > 0 ? ' is-late' : ''}`}>
          {digest.lateTotal > 0 ? (
            <span className="overview-needs__dot" aria-hidden="true" />
          ) : null}
          {lateSummary(digest.lateTotal, digest.waitingTotal)}
        </p>
        <h2 id="overview-needs-title">Needs you</h2>
        <p className="overview-needs__sub">Grouped by urgency, sorted late first</p>
      </div>

      {late.length > 0 ? (
        <div className="overview-needs__group">
          <p className="overview-needs__group-label is-late">Running late</p>
          <div className="overview-needs__tasks">{late.map(renderTask)}</div>
        </div>
      ) : null}

      {soon.length > 0 ? (
        <div className="overview-needs__group">
          <p className="overview-needs__group-label is-soon">Due soon</p>
          <div className="overview-needs__tasks">{soon.map(renderTask)}</div>
        </div>
      ) : null}

      {visible.length === 0 ? (
        <p className="overview-needs__empty">You are all caught up.</p>
      ) : null}

      {digest.ordered.length > 6 ? (
        <button
          type="button"
          className="overview-needs__more"
          onClick={() => setShowAll((open) => !open)}
        >
          {showAll
            ? `Showing all ${digest.ordered.length} — Show less`
            : `Showing ${visible.length} of ${digest.ordered.length} — See all`}
        </button>
      ) : null}

      <div className="overview-needs__handled">
        <button
          type="button"
          className="overview-needs__handled-toggle"
          aria-expanded={handledOpen}
          onClick={() => setHandledOpen((open) => !open)}
        >
          <span>
            Handled automatically today — {patientsSeen} patients seen, {newReferrals}{' '}
            new referrals came in
          </span>
          <ChevronDown size={16} aria-hidden="true" />
        </button>
        {handledOpen ? (
          <ul className="overview-needs__events">
            {latestEvents.map((event) => (
              <li key={event.id}>
                <time>{event.time}</time>
                <span>{event.text}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  )
}
