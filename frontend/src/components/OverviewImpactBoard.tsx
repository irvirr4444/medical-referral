import {
  CalendarDays,
  ChevronDown,
  Info,
  Minus,
  Search,
  TrendingDown,
  TrendingUp,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
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
import { useEscapeDismiss } from '../hooks/useEscapeDismiss'
import { DatePeriodPicker } from './DatePeriodPicker'
import './OverviewImpactBoard.css'

export function OverviewImpactBoard({
  scope = 'overview',
  density = 'comfortable',
}: {
  scope?: BossMetricsScope
  density?: 'comfortable' | 'compact'
}) {
  const periodTabs = useMemo(
    () =>
      buildBossPeriodViews(scope).map((period) => ({
        id: period.id as Exclude<BossPeriodId, 'custom'>,
        label: period.label,
      })),
    [scope],
  )
  const periodOptions: Array<{ id: BossPeriodId; label: string }> = [
    ...periodTabs,
    { id: 'custom', label: 'Pick dates' },
  ]
  const headingId = `boss-metrics-heading-${scope}`

  const [selectedId, setSelectedId] = useState<BossPeriodId>('today')
  const [periodMenuOpen, setPeriodMenuOpen] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const periodMenuRef = useRef<HTMLDivElement>(null)
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
  }

  const openPicker = () => {
    setPickerOpen(true)
  }

  const closePicker = () => {
    setPickerOpen(false)
  }

  const closePeriodMenu = () => {
    setPeriodMenuOpen(false)
  }

  const choosePeriod = (id: BossPeriodId) => {
    setPeriodMenuOpen(false)
    if (id === 'custom') {
      openPicker()
      return
    }
    setSelectedId(id)
  }

  useEscapeDismiss(selectedMetric !== null, closePatientList)
  useEscapeDismiss(pickerOpen, closePicker)
  useEscapeDismiss(periodMenuOpen, closePeriodMenu)

  useEffect(() => {
    if (!periodMenuOpen) return

    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (
        periodMenuRef.current &&
        !periodMenuRef.current.contains(event.target as Node)
      ) {
        setPeriodMenuOpen(false)
      }
    }

    document.addEventListener('pointerdown', closeOnOutsidePointer)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsidePointer)
    }
  }, [periodMenuOpen])

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
    <section
      className={`impact-board panel impact-board--${density}`}
      aria-labelledby={headingId}
    >
      <div className="impact-board__toolbar">
        <h2 id={headingId}>{active.label}</h2>
        <div className="impact-board__period-dropdown" ref={periodMenuRef}>
          <button
            type="button"
            className="impact-board__period-trigger"
            aria-label="Reporting period"
            aria-haspopup="listbox"
            aria-expanded={periodMenuOpen}
            onClick={() => setPeriodMenuOpen((open) => !open)}
          >
            <span>
              {selectedId === 'custom'
                ? appliedCustom?.label ?? 'Pick dates'
                : periodTabs.find((tab) => tab.id === selectedId)?.label ??
                  'Today'}
            </span>
            <ChevronDown size={16} aria-hidden="true" />
          </button>
          {periodMenuOpen ? (
            <ul
              className="impact-board__period-menu"
              role="listbox"
              aria-label="Reporting period"
            >
              {periodOptions.map((option) => (
                <li key={option.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={selectedId === option.id}
                    className={`impact-board__period-option${
                      selectedId === option.id ? ' is-selected' : ''
                    }`}
                    onClick={() => choosePeriod(option.id)}
                  >
                    {option.id === 'custom' ? (
                      <CalendarDays size={15} aria-hidden="true" />
                    ) : null}
                    {option.label}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>

      <article className="impact-board__period" aria-live="polite">
        <div className="impact-board__body">
          <ul className="impact-board__stats">
            {active.metrics.map((metric) => {
              const trend =
                metric.delta > 0 ? 'up' : metric.delta < 0 ? 'down' : 'flat'
              const TrendIcon =
                trend === 'up'
                  ? TrendingUp
                  : trend === 'down'
                    ? TrendingDown
                    : Minus
              return (
                <li key={metric.id}>
                  <button
                    type="button"
                    className="impact-board__stat-card"
                    onClick={() => {
                      setSelectedMetric(metric)
                      setPatientQuery('')
                    }}
                    aria-label={`View patients for ${metric.label}`}
                  >
                    <span className="impact-board__stat-top">
                      <strong className="stat-number">{metric.value}</strong>
                      <span
                        className={`impact-board__delta is-${trend}`}
                        title={active.comparisonHoverLabel}
                        aria-label={`${formatMetricDelta(metric.delta)}, ${metric.deltaPercent}% ${active.comparisonHoverLabel}`}
                      >
                        <TrendIcon size={14} aria-hidden="true" />
                        {formatMetricDelta(metric.delta)} ({metric.deltaPercent}
                        %)
                      </span>
                    </span>
                    <span className="impact-board__stat-label mono-label">
                      {metric.label}
                      <span
                        className="impact-board__metric-info"
                        aria-label={metric.meaning}
                      >
                        <Info size={13} aria-hidden="true" />
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
        </div>
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
              {visiblePatients.map((patient) => (
                <article
                  key={patient.id}
                  className="impact-board__patient-row"
                  role="listitem"
                >
                  <span className="impact-board__patient-avatar" aria-hidden="true">
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
                  </span>
                </article>
              ))}
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
