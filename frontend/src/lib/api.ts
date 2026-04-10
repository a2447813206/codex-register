import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ── Banner（广告内容由后端下发）──
export const getBanner = () => api.get('/banner')

// ── Config ──
export const getConfig = () => api.get('/config', { params: { _t: Date.now() } })
export const saveConfig = (cfg: Record<string, any>) => api.post('/config', cfg)

// ── Dashboard ──
export const getDashboardSummary = () => api.get('/dashboard-summary')

// ── Task ──
export const startTask = (count: number, workers: number, proxy?: string) =>
  api.post('/start', { count, workers, proxy })
export const stopTask = () => api.post('/stop')
export const getTaskStatus = () => api.get('/status')

// ── Accounts ──
export const getAccounts = () => api.get('/accounts')
export const deleteAccounts = (mode: string, indices: number[] = []) =>
  api.delete('/accounts', { data: { mode, indices } })
export const exportAccounts = (mode: string, indices: number[] = []) =>
  api.post('/export', { mode, indices }, { responseType: 'blob' })

// ── Logs ──
export const getLogHistoryList = () => api.get('/logs/history')
export const getLogHistoryFile = (filename: string) =>
  api.get(`/logs/history/${filename}`)
export const deleteLogHistoryFile = (filename: string) =>
  api.delete(`/logs/history/${filename}`)
export const deleteCurrentLog = () => api.delete('/logs/current')

// ── SingBox ──
export const parseSingboxSub = (url: string, proxy?: string) =>
  api.post('/singbox/parse', { url, proxy })
export const startSingbox = (url: string, proxy?: string, listenPort?: number, apiPort?: number) =>
  api.post('/singbox/start', { url, proxy, listen_port: listenPort, api_port: apiPort })
export const stopSingbox = () => api.post('/singbox/stop')
export const getSingboxStatus = (url?: string) =>
  api.get('/singbox/status', { params: { url, _t: Date.now() } })
export const testSingboxNodes = (url: string, testUrl?: string) =>
  api.post('/singbox/test', { url, test_url: testUrl })

export default api
