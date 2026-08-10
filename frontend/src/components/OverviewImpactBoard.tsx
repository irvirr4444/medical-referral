import {
  CalendarDays,
  Info,
  Minus,
  Search,
  TrendingDown,
  TrendingUp,
  X,
} from 'lucide-react'
import { useMemo, useState } from 'react'
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

  const [selectedId, setSelectedId] = useState<BossPeriodId>('today')
  const [pickerOpen, setPickerOpen] = useState(false)
  const [customStart, setCustomStart] = useState('2026-08-01')
  const [customEnd, setCustomEnd] = useState(BOSS_DEMO_TODAY)
  const [appliedCustom, setAppliedCustom] = useState<BossPeriodView | null>(null)
  const [selectedMetric, setSelectedMetric] = useState<BossMetricCard | null>(
    null,
  )
  const [patientQuery, setPatientQuery] = useState('')

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

            <div className="impact-board__patient-list" role="list">
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
