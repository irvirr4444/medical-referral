import { useMemo, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { COPY } from '../data/constants'
import type { ReferralRecord } from '../types'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import './PdfViewer.css'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

interface PdfViewerProps {
  referral: ReferralRecord
  focusPage?: number
}

export function PdfViewer({ referral, focusPage }: PdfViewerProps) {
  const [pageNumber, setPageNumber] = useState(focusPage ?? 1)
  const [numPages, setNumPages] = useState<number | null>(null)
  const [scale, setScale] = useState(1.05)
  const [error, setError] = useState<string | null>(null)

  const fileUrl = useMemo(
    () => `/referrals/${encodeURIComponent(referral.samplePdf)}`,
    [referral.samplePdf],
  )

  return (
    <div className="pdf-viewer">
      <div className="pdf-viewer__toolbar">
        <div>
          <strong>{referral.pdfFilename}</strong>
          <p className="caption">
            Source email: {referral.sender} · {referral.receivedAt}
          </p>
          <p className="caption">{COPY.confidentialNotice}</p>
        </div>
        <div className="pdf-viewer__controls">
          <button
            type="button"
            className="btn btn-secondary"
            disabled={pageNumber <= 1}
            onClick={() => setPageNumber((n) => Math.max(1, n - 1))}
          >
            Previous
          </button>
          <span className="caption">
            Page {pageNumber}
            {numPages ? ` / ${numPages}` : ''}
          </span>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={numPages != null && pageNumber >= numPages}
            onClick={() => setPageNumber((n) => n + 1)}
          >
            Next
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setScale((s) => Math.max(0.7, Number((s - 0.1).toFixed(2))))}
          >
            Zoom out
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setScale((s) => Math.min(1.6, Number((s + 0.1).toFixed(2))))}
          >
            Zoom in
          </button>
        </div>
      </div>

      <div className="pdf-viewer__frame">
        {error ? (
          <p role="alert">{error}</p>
        ) : (
          <Document
            file={fileUrl}
            loading={<p className="muted">Loading PDF…</p>}
            onLoadSuccess={({ numPages: pages }) => {
              setNumPages(pages)
              setError(null)
            }}
            onLoadError={() =>
              setError('Unable to load the approved local referral PDF for this demo.')
            }
          >
            <Page pageNumber={pageNumber} scale={scale} />
          </Document>
        )}
      </div>
    </div>
  )
}
