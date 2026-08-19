import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

export default function IntakePdfDocument({
  fileUrl,
  pageCount,
  pageWidth,
  onLoadSuccess,
  onLoadError,
}: {
  fileUrl: string
  pageCount: number
  pageWidth: number
  onLoadSuccess: (numPages: number) => void
  onLoadError: () => void
}) {
  return (
    <Document
      file={fileUrl}
      loading={<p className="gmail-pdf__status">Loading PDF…</p>}
      onLoadSuccess={({ numPages }) => onLoadSuccess(numPages)}
      onLoadError={onLoadError}
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
  )
}
