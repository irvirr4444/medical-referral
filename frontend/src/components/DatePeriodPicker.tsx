import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { BOSS_DEMO_TODAY } from '../data/bossMetrics'

type PickerMode = 'day' | 'month' | 'year' | 'range'

interface DatePeriodPickerProps {
  titleId: string
  initialStart: string
  initialEnd: string
  onCancel: () => void
  onApply: (start: string, end: string) => void
}

const MODES: Array<{ id: PickerMode; label: string }> = [
  { id: 'day', label: 'Day' },
  { id: 'month', label: 'Month' },
  { id: 'year', label: 'Year' },
  { id: 'range', label: 'Custom range' },
]

const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']
const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]

function parseIso(value: string): Date {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day))
}

function toIso(date: Date): string {
  return date.toISOString().slice(0, 10)
}

function startOfMonth(date: Date): Date {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1))
}

function endOfMonth(date: Date): Date {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0))
}

function addMonths(date: Date, amount: number): Date {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + amount, 1))
}

function calendarDays(month: Date): Date[] {
  const first = startOfMonth(month)
  const gridStart = new Date(first)
  gridStart.setUTCDate(first.getUTCDate() - first.getUTCDay())
  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(gridStart)
    day.setUTCDate(gridStart.getUTCDate() + index)
    return day
  })
}

function displayDate(value: string): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(parseIso(value))
}

function CalendarMonth({
  month,
  selectedStart,
  selectedEnd,
  maxDate,
  onSelect,
}: {
  month: Date
  selectedStart: string
  selectedEnd: string
  maxDate: Date
  onSelect: (date: Date) => void
}) {
  const monthNumber = month.getUTCMonth()
  return (
    <section className="date-period-picker__calendar">
      <h3>
        {MONTHS[monthNumber]} {month.getUTCFullYear()}
      </h3>
      <div className="date-period-picker__weekdays" aria-hidden="true">
        {WEEKDAYS.map((day) => (
          <span key={day}>{day}</span>
        ))}
      </div>
      <div className="date-period-picker__days">
        {calendarDays(month).map((date) => {
          const iso = toIso(date)
          const outside = date.getUTCMonth() !== monthNumber
          const disabled = date > maxDate
          const selected = iso === selectedStart || iso === selectedEnd
          const inRange =
            Boolean(selectedStart && selectedEnd) &&
            iso > selectedStart &&
            iso < selectedEnd
          return (
            <button
              key={iso}
              type="button"
              disabled={disabled}
              aria-label={displayDate(iso)}
              aria-pressed={selected}
              className={[
                outside ? 'is-outside' : '',
                selected ? 'is-selected' : '',
                inRange ? 'is-in-range' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => onSelect(date)}
            >
              {date.getUTCDate()}
            </button>
          )
        })}
      </div>
    </section>
  )
}

export function DatePeriodPicker({
  titleId,
  initialStart,
  initialEnd,
  onCancel,
  onApply,
}: DatePeriodPickerProps) {
  const maxDate = useMemo(() => parseIso(BOSS_DEMO_TODAY), [])
  const [mode, setMode] = useState<PickerMode>('month')
  const [visibleMonth, setVisibleMonth] = useState(() =>
    startOfMonth(parseIso(initialEnd)),
  )
  const [visibleYear, setVisibleYear] = useState(
    () => parseIso(initialEnd).getUTCFullYear(),
  )
  const [start, setStart] = useState(initialStart)
  const [end, setEnd] = useState(initialEnd)

  const selectDay = (date: Date) => {
    const iso = toIso(date)
    if (mode === 'range') {
      if (!start || end || iso < start) {
        setStart(iso)
        setEnd('')
      } else {
        setEnd(iso)
      }
      return
    }
    setStart(iso)
    setEnd(iso)
  }

  const selectMonth = (month: number) => {
    const monthStart = new Date(Date.UTC(visibleYear, month, 1))
    if (monthStart > maxDate) return
    const monthEnd = endOfMonth(monthStart)
    setStart(toIso(monthStart))
    setEnd(toIso(monthEnd > maxDate ? maxDate : monthEnd))
  }

  const selectYear = (year: number) => {
    const yearStart = new Date(Date.UTC(year, 0, 1))
    if (yearStart > maxDate) return
    const yearEnd = new Date(Date.UTC(year, 11, 31))
    setStart(toIso(yearStart))
    setEnd(toIso(yearEnd > maxDate ? maxDate : yearEnd))
  }

  const summary =
    start && end
      ? start === end
        ? displayDate(start)
        : `${displayDate(start)} – ${displayDate(end)}`
      : start
        ? `${displayDate(start)} – Select an end date`
        : 'Select a reporting period'

  const decadeStart = Math.floor(visibleYear / 10) * 10

  return (
    <>
      <header className="impact-board__modal-header">
        <div>
          <h2 id={titleId}>Select reporting period</h2>
          <p className="muted">{summary}</p>
        </div>
        <button
          type="button"
          className="impact-board__modal-close"
          aria-label="Close date picker"
          onClick={onCancel}
        >
          <X size={16} aria-hidden="true" />
        </button>
      </header>

      <div className="date-period-picker__modes" role="tablist" aria-label="Period type">
        {MODES.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={mode === item.id}
            className={mode === item.id ? 'is-active' : ''}
            onClick={() => {
              setMode(item.id)
              if (
                item.id === 'range' &&
                addMonths(visibleMonth, 1) > startOfMonth(maxDate)
              ) {
                setVisibleMonth(addMonths(startOfMonth(maxDate), -1))
              }
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      {mode === 'day' || mode === 'range' ? (
        <>
          <div className="date-period-picker__navigation">
            <button
              type="button"
              aria-label="Previous month"
              onClick={() => setVisibleMonth((current) => addMonths(current, -1))}
            >
              <ChevronLeft size={18} aria-hidden="true" />
            </button>
            <strong>
              {mode === 'range'
                ? `${MONTHS[visibleMonth.getUTCMonth()]} – ${
                    MONTHS[addMonths(visibleMonth, 1).getUTCMonth()]
                  } ${addMonths(visibleMonth, 1).getUTCFullYear()}`
                : `${MONTHS[visibleMonth.getUTCMonth()]} ${visibleMonth.getUTCFullYear()}`}
            </strong>
            <button
              type="button"
              aria-label="Next month"
              disabled={addMonths(visibleMonth, 1) > startOfMonth(maxDate)}
              onClick={() => setVisibleMonth((current) => addMonths(current, 1))}
            >
              <ChevronRight size={18} aria-hidden="true" />
            </button>
          </div>
          <div
            className={`date-period-picker__calendars ${
              mode === 'range' ? 'has-two' : ''
            }`}
          >
            <CalendarMonth
              month={visibleMonth}
              selectedStart={start}
              selectedEnd={end}
              maxDate={maxDate}
              onSelect={selectDay}
            />
            {mode === 'range' ? (
              <CalendarMonth
                month={addMonths(visibleMonth, 1)}
                selectedStart={start}
                selectedEnd={end}
                maxDate={maxDate}
                onSelect={selectDay}
              />
            ) : null}
          </div>
        </>
      ) : null}

      {mode === 'month' ? (
        <>
          <div className="date-period-picker__navigation">
            <button
              type="button"
              aria-label="Previous year"
              onClick={() => setVisibleYear((year) => year - 1)}
            >
              <ChevronLeft size={18} aria-hidden="true" />
            </button>
            <strong>{visibleYear}</strong>
            <button
              type="button"
              aria-label="Next year"
              disabled={visibleYear >= maxDate.getUTCFullYear()}
              onClick={() => setVisibleYear((year) => year + 1)}
            >
              <ChevronRight size={18} aria-hidden="true" />
            </button>
          </div>
          <div className="date-period-picker__month-grid">
            {MONTHS.map((month, index) => {
              const disabled =
                new Date(Date.UTC(visibleYear, index, 1)) > maxDate
              const selected =
                start === toIso(new Date(Date.UTC(visibleYear, index, 1))) &&
                Boolean(end)
              return (
                <button
                  key={month}
                  type="button"
                  disabled={disabled}
                  className={selected ? 'is-selected' : ''}
                  onClick={() => selectMonth(index)}
                >
                  {month.slice(0, 3)}
                </button>
              )
            })}
          </div>
        </>
      ) : null}

      {mode === 'year' ? (
        <>
          <div className="date-period-picker__navigation">
            <button
              type="button"
              aria-label="Previous decade"
              onClick={() => setVisibleYear((year) => year - 10)}
            >
              <ChevronLeft size={18} aria-hidden="true" />
            </button>
            <strong>
              {decadeStart}–{decadeStart + 11}
            </strong>
            <button
              type="button"
              aria-label="Next decade"
              disabled={decadeStart + 10 > maxDate.getUTCFullYear()}
              onClick={() => setVisibleYear((year) => year + 10)}
            >
              <ChevronRight size={18} aria-hidden="true" />
            </button>
          </div>
          <div className="date-period-picker__year-grid">
            {Array.from({ length: 12 }, (_, index) => decadeStart + index).map(
              (year) => (
                <button
                  key={year}
                  type="button"
                  disabled={year > maxDate.getUTCFullYear()}
                  className={
                    start === toIso(new Date(Date.UTC(year, 0, 1)))
                      ? 'is-selected'
                      : ''
                  }
                  onClick={() => selectYear(year)}
                >
                  {year}
                </button>
              ),
            )}
          </div>
        </>
      ) : null}

      <div className="impact-board__modal-actions">
        <button
          type="button"
          className="impact-board__modal-cancel"
          onClick={onCancel}
        >
          Cancel
        </button>
        <button
          type="button"
          className="impact-board__modal-apply"
          disabled={!start || !end}
          onClick={() => onApply(start, end)}
        >
          Confirm
        </button>
      </div>
    </>
  )
}
