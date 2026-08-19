export function isDemoDataMode(): boolean {
  if (typeof window !== 'undefined') {
    const flag = new URLSearchParams(window.location.search).get('demo-data')
    if (flag === '1' || flag === 'true') return true
    if (flag === '0' || flag === 'false') return false
  }
  const env = String(import.meta.env.VITE_DEMO_DATA ?? '').toLowerCase()
  if (env === 'true' || env === '1') return true
  if (env === 'false' || env === '0') return false
  return import.meta.env.MODE === 'test'
}
