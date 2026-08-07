import { defineConfig } from 'vitest/config'
import path from 'node:path'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import type { Plugin } from 'vite'

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

function referralPdfPlugin(): Plugin {
  return {
    name: 'wcw-referral-pdfs',
    configureServer(server) {
      server.middlewares.use('/referrals', (req, res, next) => {
        try {
          const raw = decodeURIComponent((req.url ?? '').replace(/^\//, '').split('?')[0] ?? '')
          if (!ALLOWED_PDFS.has(raw)) {
            res.statusCode = 404
            res.end('Not found')
            return
          }
          const filePath = path.join(samplesDir, raw)
          if (!fs.existsSync(filePath)) {
            res.statusCode = 404
            res.end('Not found')
            return
          }
          res.setHeader('Content-Type', 'application/pdf')
          res.setHeader('Cache-Control', 'no-store')
          fs.createReadStream(filePath).pipe(res)
        } catch {
          next()
        }
      })
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
