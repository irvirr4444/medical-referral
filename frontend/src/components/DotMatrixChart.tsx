import './DotMatrixChart.css'

export interface DotMatrixPoint {
  label: string
  value: number
}

export function DotMatrixChart({
  series,
  maxRows = 12,
  title = 'Trend',
}: {
  series: DotMatrixPoint[]
  maxRows?: number
  title?: string
}) {
  const peak = Math.max(1, ...series.map((point) => point.value))
  const rows = Math.min(maxRows, Math.max(4, Math.ceil(peak)))

  return (
    <figure className="dot-matrix" aria-label={title}>
      <figcaption className="mono-label">{title}</figcaption>
      <div
        className="dot-matrix__plot"
        style={{
          gridTemplateColumns: `repeat(${Math.max(series.length, 1)}, minmax(0, 1fr))`,
        }}
      >
        {series.map((point) => {
          const filled = Math.max(
            0,
            Math.round((point.value / peak) * rows),
          )
          return (
            <div key={point.label} className="dot-matrix__column">
              <div
                className="dot-matrix__stack"
                style={{ gridTemplateRows: `repeat(${rows}, 1fr)` }}
                title={`${point.label}: ${point.value}`}
              >
                {Array.from({ length: rows }, (_, index) => {
                  const fromBottom = rows - index
                  const isFilled = fromBottom <= filled
                  return (
                    <span
                      key={index}
                      className={`dot-matrix__dot ${isFilled ? 'is-filled' : ''}`}
                      aria-hidden="true"
                    />
                  )
                })}
              </div>
              <span className="dot-matrix__tick">{point.label}</span>
            </div>
          )
        })}
      </div>
    </figure>
  )
}
