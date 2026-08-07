import '@testing-library/jest-dom/vitest'
import { createElement, type ReactNode } from 'react'
import { vi } from 'vitest'

vi.mock('react-pdf', () => ({
  Document: ({ children }: { children?: ReactNode }) =>
    createElement('div', { 'data-testid': 'pdf-document' }, children),
  Page: () => createElement('div', { 'data-testid': 'pdf-page' }),
  pdfjs: { GlobalWorkerOptions: { workerSrc: '' } },
}))

class DOMMatrixPolyfill {
  a = 1
  b = 0
  c = 0
  d = 1
  e = 0
  f = 0
}

if (!(globalThis as { DOMMatrix?: unknown }).DOMMatrix) {
  ;(globalThis as { DOMMatrix: unknown }).DOMMatrix = DOMMatrixPolyfill
}

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }),
})
