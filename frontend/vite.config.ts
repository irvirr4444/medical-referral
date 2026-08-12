import { defineConfig } from 'vitest/config'
import path from 'node:path'
import fs from 'node:fs'
import type { ServerResponse } from 'node:http'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import type { Connect, Plugin, ViteDevServer } from 'vite'

const rootDir = path.dirname(fileURLToPath(import.meta.url))
const samplesDir = path.resolve(rootDir, '../samples')

const ALLOWED_PDFS = new Set([
  'BUTLER, ALVA demo.pdf',
  'EC - REFERRAL FORM.pdf',
  'fax20260710-1422744-nkqbp2.pdf',
  'fax20260711-48483-ougwp2.pdf',
  'fax20260713-16377-syrmla.pdf',
  'fax20260713-2485963-94q8kc.pdf',
  'fax20260713-620-tw3x6v.pdf',
])

function serveReferralPdf(
  req: Connect.IncomingMessage,
  res: ServerResponse,
  next: Connect.NextFunction,
) {
  try {
    const requestPath = (req.url ?? '').split('?')[0] ?? ''
    const raw = decodeURIComponent(
      requestPath.replace(/^\/referrals\/?/, '').replace(/^\//, ''),
    )
    if (!raw || !ALLOWED_PDFS.has(raw)) {
      res.statusCode = 404
      res.setHeader('Content-Type', 'text/plain; charset=utf-8')
      res.end('Referral PDF not found')
      return
    }

    const filePath = path.join(samplesDir, raw)
    if (!filePath.startsWith(samplesDir) || !fs.existsSync(filePath)) {
      res.statusCode = 404
      res.setHeader('Content-Type', 'text/plain; charset=utf-8')
      res.end('Referral PDF not found')
      return
    }

    const stat = fs.statSync(filePath)
    res.statusCode = 200
    res.setHeader('Content-Type', 'application/pdf')
    res.setHeader(
      'Content-Disposition',
      `inline; filename="${raw.replace(/"/g, '')}"`,
    )
    res.setHeader('Content-Length', String(stat.size))
    res.setHeader('Cache-Control', 'no-store')
    fs.createReadStream(filePath).pipe(res)
  } catch {
    next()
  }
}

function attachReferralPdfMiddleware(server: ViteDevServer) {
  // Register before Vite's HTML fallback so /referrals/* serves real PDFs.
  server.middlewares.use((req, res, next) => {
    if (!req.url?.startsWith('/referrals/')) {
      next()
      return
    }
    serveReferralPdf(req, res, next)
  })
}

function referralPdfPlugin(): Plugin {
  return {
    name: 'wcw-referral-pdfs',
    configureServer(server) {
      attachReferralPdfMiddleware(server)
    },
    configurePreviewServer(server) {
      attachReferralPdfMiddleware(server as unknown as ViteDevServer)
    },
  }
}

export default defineConfig({
  plugins: [react(), referralPdfPlugin()],
  resolve: {
    alias: {
      '@': path.resolve(rootDir, 'src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
  server: {
    port: 5173,
    strictPort: true,
  },
})
