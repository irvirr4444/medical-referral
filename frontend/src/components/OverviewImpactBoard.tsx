import { CalendarDays, Info, Minus, TrendingDown, TrendingUp, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import {
  bossPeriodById,
  buildBossPeriodViews,
  buildCustomBossMetrics,
  BOSS_DEMO_TODAY,
  emptyBossPeriodView,
  formatMetricDelta,
  type BossMetricsScope,
  type BossPeriodId,
  type BossPeriodView,
} from '../data/bossMetrics'
import './OverviewImpactBoard.css'

export function OverviewImpactBoard({
  scope = 'overview',
}: {
  scope?: BossMetricsScope
}) {
  const periodTabs = useMemo(
    () =>
      buildBossPeriodViews(scope).map((period) => ({
        id: period.id as Exclude<BossPeriodId, 'custom'>,
        label: period.label,
      })),
    [scope],
  )
  const headingId = `boss-metrics-heading-${scope}`
  const startInputId = `boss-metrics-start-${scope}`
  const endInputId = `boss-metrics-end-${scope}`

  const [selectedId, setSelectedId] = useState<BossPeriodId>('today')
  const [pickerOpen, setPickerOpen] = useState(false)
  const [customStart, setCustomStart] = useState('2026-08-01')
  const [customEnd, setCustomEnd] = useState(BOSS_DEMO_TODAY)
  const [draftStart, setDraftStart] = useState('2026-08-01')
  const [draftEnd, setDraftEnd] = useState(BOSS_DEMO_TODAY)
  const [appliedCustom, setAppliedCustom] = useState<BossPeriodView | null>(null)
  const [customError, setCustomError] = useState<string | null>(null)

  const active = useMemo(() => {
    if (selectedId === 'custom') {
      return appliedCustom ?? emptyBossPeriodView(scope)
    }
    return bossPeriodById(selectedId, scope)
  }, [appliedCustom, scope, selectedId])

  const openPicker = () => {
    setDraftStart(customStart)
    setDraftEnd(customEnd)
    setCustomError(null)
    setPickerOpen(true)
  }

  const closePicker = () => {
    setPickerOpen(false)
    setCustomError(null)
  }

  const applyCustomRange = () => {
    const next = buildCustomBossMetrics(draftStart, draftEnd, scope)
    if (!next) {
      setCustomError(
        'Choose a valid range where the end date is on or after the start date.',
      )
      return
    }
    setCustomStart(draftStart)
    setCustomEnd(draftEnd)
    setAppliedCustom(next)
    setSelectedId('custom')
    setCustomError(null)
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
                <div className="impact-board__stat-top">
                  <strong>{metric.value}</strong>
                  <span
                    className={`impact-board__delta is-${trend}`}
                    title={active.comparisonHoverLabel}
                    aria-label={`${formatMetricDelta(metric.delta)}, ${metric.deltaPercent}% ${active.comparisonHoverLabel}`}
                  >
                    <TrendIcon size={14} aria-hidden="true" />
                    {formatMetricDelta(metric.delta)} ({metric.deltaPercent}%)
                  </span>
                </div>
                <span className="impact-board__stat-label">
                  {metric.label}
                  <span
                    className="impact-board__metric-info"
                    tabIndex={0}
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
              </li>
            )
          })}
        </ul>
      </article>

      {pickerOpen ? (
        <div
          className="impact-board__backdrop"
          role="presentation"
          onClick={closePicker}
        >
          <section
            className="impact-board__modal panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`boss-date-picker-title-${scope}`}
            onClick={(event) => event.stopPropagation()}
          >
            <header className="impact-board__modal-header">
              <div>
                <h2 id={`boss-date-picker-title-${scope}`}>Pick a date range</h2>
                <p className="muted">Choose start and end dates for these metrics.</p>
              </div>
              <button
                type="button"
                className="impact-board__modal-close"
                aria-label="Close date picker"
                onClick={closePicker}
              >
                <X size={16} aria-hidden="true" />
              </button>
            </header>

            <div className="impact-board__modal-fields">
              <label htmlFor={startInputId}>
                <span>Start date</span>
                <input
                  id={startInputId}
                  type="date"
                  value={draftStart}
                  onChange={(event) => setDraftStart(event.target.value)}
                />
              </label>
              <label htmlFor={endInputId}>
                <span>End date</span>
                <input
                  id={endInputId}
                  type="date"
                  value={draftEnd}
                  onChange={(event) => setDraftEnd(event.target.value)}
                />
              </label>
            </div>

            {customError ? (
              <p className="impact-board__error" role="alert">
                {customError}
              </p>
            ) : null}

            <div className="impact-board__modal-actions">
              <button
                type="button"
                className="impact-board__modal-cancel"
                onClick={closePicker}
              >
                Cancel
              </button>
              <button
                type="button"
                className="impact-board__modal-apply"
                onClick={applyCustomRange}
              >
                Apply dates
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  )
}
