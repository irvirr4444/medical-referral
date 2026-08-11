import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  Download,
  ExternalLink,
  FileText,
  Minus,
  Plus,
  Printer,
  X,
} from 'lucide-react'
import { Document, Page, pdfjs } from 'react-pdf'
import { useEscapeDismiss } from '../../hooks/useEscapeDismiss'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import './IntakePdfPreview.css'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

export function IntakePdfPreview({
  samplePdf,
  label,
}: {
  samplePdf: string
  label?: string
  /** @deprecated Preview opens in a modal; compact is ignored. */
  compact?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [pageCount, setPageCount] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [loadError, setLoadError] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [baseWidth, setBaseWidth] = useState(780)
  const title = label ?? samplePdf
  const fileUrl = useMemo(
    () => `/referrals/${encodeURIComponent(samplePdf)}`,
    [samplePdf],
  )
  const pageWidth = Math.round(baseWidth * zoom)

  useEscapeDismiss(open, () => setOpen(false))

  useEffect(() => {
    if (!open) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const updateWidth = () => {
      setBaseWidth(Math.max(300, Math.min(820, window.innerWidth - 160)))
    }
    updateWidth()
    window.addEventListener('resize', updateWidth)
    return () => window.removeEventListener('resize', updateWidth)
  }, [open])

  useEffect(() => {
    if (!open) {
      setPageCount(0)
      setCurrentPage(1)
      setLoadError(false)
      setZoom(1)
    }
  }, [open])

  const modal =
    open && typeof document !== 'undefined'
      ? createPortal(
          <div className="gmail-pdf" role="dialog" aria-modal="true" aria-label={title}>
            <header className="gmail-pdf__top">
              <div className="gmail-pdf__top-left">
                <button
                  type="button"
                  className="gmail-pdf__icon"
                  aria-label="Close attachment"
                  onClick={() => setOpen(false)}
                >
                  <X size={20} aria-hidden="true" />
                </button>
                <div className="gmail-pdf__file">
                  <FileText size={18} aria-hidden="true" />
                  <span>{title}</span>
                </div>
              </div>

              <div className="gmail-pdf__top-right">
                <a
                  href={fileUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="gmail-pdf__icon"
                  aria-label="Open PDF in new tab"
                >
                  <ExternalLink size={18} aria-hidden="true" />
                </a>
                <button
                  type="button"
                  className="gmail-pdf__icon"
                  aria-label="Print PDF"
                  onClick={() => window.open(fileUrl, '_blank', 'noopener')}
                >
                  <Printer size={18} aria-hidden="true" />
                </button>
                <a
                  href={fileUrl}
                  download={samplePdf}
                  className="gmail-pdf__icon"
                  aria-label="Download PDF"
                >
                  <Download size={18} aria-hidden="true" />
                </a>
              </div>
            </header>

            <div
              className="gmail-pdf__stage"
              aria-label="Referral PDF"
              data-modal-scroll
              onClick={() => setOpen(false)}
              onScroll={(event) => {
                if (!pageCount) return
                const target = event.currentTarget
                const pages = Array.from(
                  target.querySelectorAll<HTMLElement>('[data-pdf-page]'),
                )
                if (!pages.length) return
                const mid = target.scrollTop + target.clientHeight / 3
                let active = 1
                for (const page of pages) {
                  if (page.offsetTop <= mid) {
                    active = Number(page.dataset.pdfPage ?? 1)
                  }
                }
                setCurrentPage(active)
              }}
            >
              <div
                className="gmail-pdf__pages"
                onClick={(event) => event.stopPropagation()}
              >
                {loadError ? (
                  <p className="gmail-pdf__status" role="alert">
                    Unable to preview this PDF.{' '}
                    <a href={fileUrl} target="_blank" rel="noreferrer">
                      Open it in a new tab
                    </a>
                    .
                  </p>
                ) : (
                  <Document
                    file={fileUrl}
                    loading={<p className="gmail-pdf__status">Loading PDF…</p>}
                    onLoadSuccess={({ numPages }) => {
                      setPageCount(numPages)
                      setLoadError(false)
                    }}
                    onLoadError={() => setLoadError(true)}
                  >
                    {Array.from({ length: pageCount }, (_, index) => (
                      <div
                        key={`page-${index + 1}`}
                        data-pdf-page={index + 1}
                        className="gmail-pdf__page-wrap"
                      >
                        <Page
                          pageNumber={index + 1}
                          width={pageWidth}
                          className="gmail-pdf__page"
                          renderTextLayer={false}
                          renderAnnotationLayer={false}
                        />
                      </div>
                    ))}
                  </Document>
                )}
              </div>
            </div>

            {pageCount > 0 ? (
              <div className="gmail-pdf__dock" onClick={(event) => event.stopPropagation()}>
                <span className="gmail-pdf__page-label">
                  Page {currentPage} / {pageCount}
                </span>
                <span className="gmail-pdf__dock-sep" aria-hidden="true" />
                <button
                  type="button"
                  className="gmail-pdf__dock-btn"
                  aria-label="Zoom out"
                  onClick={() => setZoom((value) => Math.max(0.7, Number((value - 0.1).toFixed(2))))}
                >
                  <Minus size={16} aria-hidden="true" />
                </button>
                <span className="gmail-pdf__zoom">{Math.round(zoom * 100)}%</span>
                <button
                  type="button"
                  className="gmail-pdf__dock-btn"
                  aria-label="Zoom in"
                  onClick={() => setZoom((value) => Math.min(1.6, Number((value + 0.1).toFixed(2))))}
                >
                  <Plus size={16} aria-hidden="true" />
                </button>
              </div>
            ) : null}
          </div>,
          document.body,
        )
      : null

  return (
    <>
      <button
        type="button"
        className="intake-pdf-chip"
        aria-label={`Open attachment ${title}`}
        onClick={() => setOpen(true)}
      >
        <span className="intake-pdf-chip__icon" aria-hidden="true">
          <FileText size={15} strokeWidth={1.75} />
        </span>
        <span className="intake-pdf-chip__name">{title}</span>
        <span className="intake-pdf-chip__type" aria-hidden="true">
          PDF
        </span>
      </button>
      {modal}
    </>
  )
}
