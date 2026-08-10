import {
  CalendarDays,
  Info,
  Minus,
  Search,
  TrendingDown,
  TrendingUp,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import {
  bossPeriodById,
  buildBossPeriodViews,
  buildCustomBossMetrics,
  BOSS_DEMO_TODAY,
  emptyBossPeriodView,
  formatMetricDelta,
  type BossMetricCard,
  type BossMetricsScope,
  type BossPeriodId,
  type BossPeriodView,
} from '../data/bossMetrics'
import { buildBossMetricPatients } from '../data/bossMetricPatients'
import { DatePeriodPicker } from './DatePeriodPicker'
import { useDemo } from '../state/useDemo'
import { useNavigate } from 'react-router-dom'
import './OverviewImpactBoard.css'

export function OverviewImpactBoard({
  scope = 'overview',
}: {
  scope?: BossMetricsScope
}) {
  const { state, dispatch } = useDemo()
  const navigate = useNavigate()
  const periodTabs = useMemo(
    () =>
      buildBossPeriodViews(scope).map((period) => ({
        id: period.id as Exclude<BossPeriodId, 'custom'>,
        label: period.label,
      })),
    [scope],
  )
  const headingId = `boss-metrics-heading-${scope}`

  const [selectedId, setSelectedId] = useState<BossPeriodId>('today')
  const [pickerOpen, setPickerOpen] = useState(false)
  const [customStart, setCustomStart] = useState('2026-08-01')
  const [customEnd, setCustomEnd] = useState(BOSS_DEMO_TODAY)
  const [appliedCustom, setAppliedCustom] = useState<BossPeriodView | null>(null)
  const [selectedMetric, setSelectedMetric] = useState<BossMetricCard | null>(
    null,
  )
  const [patientQuery, setPatientQuery] = useState('')
  const modalOpen = pickerOpen || selectedMetric !== null

  useEffect(() => {
    if (!modalOpen) return

    const scrollY = window.scrollY
    const body = document.body
    const root = document.documentElement
    const previousBodyStyles = {
      overflow: body.style.overflow,
      paddingRight: body.style.paddingRight,
      position: body.style.position,
      top: body.style.top,
      left: body.style.left,
      right: body.style.right,
      width: body.style.width,
    }
    const previousRootStyles = {
      overflow: root.style.overflow,
      overscrollBehavior: root.style.overscrollBehavior,
    }
    const scrollbarWidth =
      window.innerWidth - root.clientWidth

    root.style.overflow = 'hidden'
    root.style.overscrollBehavior = 'none'
    body.style.overflow = 'hidden'
    body.style.position = 'fixed'
    body.style.top = `-${scrollY}px`
    body.style.left = '0'
    body.style.right = '0'
    body.style.width = '100%'
    if (scrollbarWidth > 0) {
      body.style.paddingRight = `${scrollbarWidth}px`
    }

    const canScroll = (target: EventTarget | null, deltaY: number) => {
      if (!(target instanceof Element)) return false
      let scrollable = target.closest<HTMLElement>('[data-modal-scroll]')
      while (scrollable) {
        if (scrollable.scrollHeight > scrollable.clientHeight) {
          if (deltaY < 0 && scrollable.scrollTop > 0) return true
          if (
            deltaY > 0 &&
            scrollable.scrollTop + scrollable.clientHeight <
              scrollable.scrollHeight
          ) {
            return true
          }
        }
        scrollable =
          scrollable.parentElement?.closest<HTMLElement>(
            '[data-modal-scroll]',
          ) ?? null
      }
      return deltaY === 0
    }

    const preventWheelScroll = (event: WheelEvent) => {
      if (!canScroll(event.target, event.deltaY)) event.preventDefault()
    }

    let previousTouchY: number | null = null
    const rememberTouch = (event: TouchEvent) => {
      previousTouchY = event.touches[0]?.clientY ?? null
    }
    const preventTouchScroll = (event: TouchEvent) => {
      const currentTouchY = event.touches[0]?.clientY
      if (previousTouchY === null || currentTouchY === undefined) {
        event.preventDefault()
        return
      }
      const deltaY = previousTouchY - currentTouchY
      previousTouchY = currentTouchY
      if (!canScroll(event.target, deltaY)) event.preventDefault()
    }

    document.addEventListener('wheel', preventWheelScroll, {
      passive: false,
      capture: true,
    })
    document.addEventListener('touchstart', rememberTouch, {
      passive: true,
      capture: true,
    })
    document.addEventListener('touchmove', preventTouchScroll, {
      passive: false,
      capture: true,
    })

    return () => {
      document.removeEventListener('wheel', preventWheelScroll, {
        capture: true,
      })
      document.removeEventListener('touchstart', rememberTouch, {
        capture: true,
      })
      document.removeEventListener('touchmove', preventTouchScroll, {
        capture: true,
      })
      root.style.overflow = previousRootStyles.overflow
      root.style.overscrollBehavior = previousRootStyles.overscrollBehavior
      Object.assign(body.style, previousBodyStyles)
      if (scrollY > 0) window.scrollTo(0, scrollY)
    }
  }, [modalOpen])

  const active = useMemo(() => {
    if (selectedId === 'custom') {
      return appliedCustom ?? emptyBossPeriodView(scope)
    }
    return bossPeriodById(selectedId, scope)
  }, [appliedCustom, scope, selectedId])

  useEffect(() => {
    if (!state.reopenPatientMetricId) return
    const metric = active.metrics.find(
      (item) => item.id === state.reopenPatientMetricId,
    )
    if (metric) {
      setSelectedMetric(metric)
      setPatientQuery('')
    }
  }, [active.metrics, state.reopenPatientMetricId])

  const metricPatients = useMemo(() => {
    if (!selectedMetric) return []
    return buildBossMetricPatients(
      scope,
      selectedMetric.id,
      selectedMetric.label,
    )
  }, [scope, selectedMetric])

  const visiblePatients = useMemo(() => {
    const query = patientQuery.trim().toLowerCase()
    if (!query) return metricPatients
    return metricPatients.filter((patient) =>
      [
        patient.name,
        patient.id,
        patient.owner,
        patient.status,
        patient.dateOfBirth,
        patient.phone,
        patient.address,
      ].some((value) => value.toLowerCase().includes(query)),
    )
  }, [metricPatients, patientQuery])

  const closePatientList = () => {
    setSelectedMetric(null)
    setPatientQuery('')
    if (state.reopenPatientMetricId) {
      dispatch({ type: 'CLEAR_REOPEN_PATIENT_METRIC' })
    }
  }

  const openPicker = () => {
    setPickerOpen(true)
  }

  const closePicker = () => {
    setPickerOpen(false)
  }

  const applyCustomRange = (start: string, end: string) => {
    const next = buildCustomBossMetrics(start, end, scope)
    if (!next) return
    setCustomStart(start)
    setCustomEnd(end)
    setAppliedCustom(next)
    setSelectedId('custom')
    setPickerOpen(false)
  }

  return (
    <section className="impact-board panel" aria-labelledby={headingId}>
      <div className="impact-board__toolbar">
        <h2 id={headingId}>Objectives</h2>
        <div
          className="impact-board__segment"
          role="tablist"
          aria-label="Reporting period"
        >
          {periodTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={selectedId === tab.id}
              className={`impact-board__segment-btn ${
                selectedId === tab.id ? 'is-active' : ''
              }`}
              onClick={() => setSelectedId(tab.id)}
            >
              {tab.label}
            </button>
          ))}
          <button
            type="button"
            role="tab"
            aria-selected={selectedId === 'custom'}
            aria-haspopup="dialog"
            aria-expanded={pickerOpen}
            className={`impact-board__segment-btn ${
              selectedId === 'custom' ? 'is-active' : ''
            }`}
            onClick={openPicker}
          >
            <CalendarDays size={15} aria-hidden="true" />
            Pick dates
          </button>
        </div>
      </div>

      <article className="impact-board__period" aria-live="polite">
        <header>
          <h3>{active.label}</h3>
          <p className="caption">{active.caption}</p>
        </header>
        <ul className="impact-board__stats">
          {active.metrics.map((metric) => {
            const trend =
              metric.delta > 0 ? 'up' : metric.delta < 0 ? 'down' : 'flat'
            const TrendIcon =
              trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus
            return (
              <li key={metric.id}>
                <button
                  type="button"
                  className="impact-board__stat-card"
                  onClick={() => {
                    setSelectedMetric(metric)
                    setPatientQuery('')
                    if (state.reopenPatientMetricId) {
                      dispatch({ type: 'CLEAR_REOPEN_PATIENT_METRIC' })
                    }
                  }}
                  aria-label={`View patients for ${metric.label}`}
                >
                  <span className="impact-board__stat-top">
                    <strong>{metric.value}</strong>
                    <span
                      className={`impact-board__delta is-${trend}`}
                      title={active.comparisonHoverLabel}
                      aria-label={`${formatMetricDelta(metric.delta)}, ${metric.deltaPercent}% ${active.comparisonHoverLabel}`}
                    >
                      <TrendIcon size={14} aria-hidden="true" />
                      {formatMetricDelta(metric.delta)} ({metric.deltaPercent}%)
                    </span>
                  </span>
                  <span className="impact-board__stat-label">
                    {metric.label}
                    <span
                      className="impact-board__metric-info"
                      aria-label={metric.meaning}
                    >
                      <Info size={14} aria-hidden="true" />
                      <span className="impact-board__tooltip" role="tooltip">
                        {metric.meaning}
                      </span>
                    </span>
                  </span>
                  <span className="impact-board__comparison">
                    {active.comparisonLabel}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </article>

      {selectedMetric ? (
        <div
          className="impact-board__backdrop"
          role="presentation"
          onClick={closePatientList}
        >
          <section
            className="impact-board__modal impact-board__patient-modal panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`metric-patients-title-${scope}`}
            data-modal-scroll
            onClick={(event) => event.stopPropagation()}
          >
            <header className="impact-board__modal-header">
              <div>
                <h2 id={`metric-patients-title-${scope}`}>
                  {selectedMetric.label}
                </h2>
                <p className="impact-board__patient-count">
                  {visiblePatients.length === metricPatients.length
                    ? `${metricPatients.length} patients`
                    : `${visiblePatients.length} of ${metricPatients.length} patients`}
                </p>
              </div>
              <button
                type="button"
                className="impact-board__modal-close"
                aria-label="Close patient list"
                onClick={closePatientList}
              >
                <X size={16} aria-hidden="true" />
              </button>
            </header>

            <label className="impact-board__patient-search">
              <Search size={16} aria-hidden="true" />
              <input
                type="search"
                value={patientQuery}
                onChange={(event) => setPatientQuery(event.target.value)}
                placeholder="Search patient, referral ID, or case manager"
                aria-label="Search patients"
              />
            </label>

            <div
              className="impact-board__patient-list"
              role="list"
              data-modal-scroll
            >
              {visiblePatients.map((patient) => {
                const openProfile = () => {
                  if (!patient.profileId || !selectedMetric) return
                  dispatch({
                    type: 'OPEN_PATIENT_PROFILE',
                    returnPage: state.activePage,
                    metricId: selectedMetric.id,
                  })
                  navigate(`/patients/${patient.profileId}`)
                }

                const rowContent = (
                  <>
                    <span
                      className="impact-board__patient-avatar"
                      aria-hidden="true"
                    >
                      {patient.name
                        .split(' ')
                        .map((part) => part[0])
                        .join('')}
                    </span>
                    <span className="impact-board__patient-copy">
                      <strong>{patient.name}</strong>
                      <small>
                        DOB: {patient.dateOfBirth} · {patient.phone}
                      </small>
                      <small>{patient.address}</small>
                    </span>
                    <span className="impact-board__patient-status">
                      <strong>{patient.status}</strong>
                      {patient.profileId ? <small>View profile</small> : null}
                    </span>
                  </>
                )

                return (
                  <div key={patient.id} role="listitem">
                    {patient.profileId ? (
                      <button
                        type="button"
                        className="impact-board__patient-row is-interactive"
                        onClick={openProfile}
                        aria-label={`Open profile for ${patient.name}`}
                      >
                        {rowContent}
                      </button>
                    ) : (
                      <article className="impact-board__patient-row">
                        {rowContent}
                      </article>
                    )}
                  </div>
                )
              })}
              {visiblePatients.length === 0 ? (
                <p className="impact-board__patient-empty">
                  No patients match your search.
                </p>
              ) : null}
            </div>
          </section>
        </div>
      ) : null}

      {pickerOpen ? (
        <div
          className="impact-board__backdrop"
          role="presentation"
          onClick={closePicker}
        >
          <section
            className="impact-board__modal impact-board__date-modal panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`boss-date-picker-title-${scope}`}
            data-modal-scroll
            onClick={(event) => event.stopPropagation()}
          >
            <DatePeriodPicker
              titleId={`boss-date-picker-title-${scope}`}
              initialStart={customStart}
              initialEnd={customEnd}
              onCancel={closePicker}
              onApply={applyCustomRange}
            />
          </section>
        </div>
      ) : null}
    </section>
  )
}
