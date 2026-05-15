import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const RENDER_URL = import.meta.env.VITE_API_BASE_URL || 'https://wemeet-api-dchk.onrender.com'

// Render 직접 호출 (CORS: access-control-allow-origin: * 확인됨)
export const api = axios.create({
  baseURL: `${RENDER_URL}/api`,
  timeout: 60000,
})

export function useApiHealth() {
  const [status, setStatus] = useState('waking')
  const [elapsed, setElapsed] = useState(0)

  const check = useCallback(async () => {
    setStatus('waking')
    setElapsed(0)
    const t = setInterval(() => setElapsed(s => s + 1), 1000)
    try {
      await api.get('/health')
      setStatus('online')
    } catch {
      setStatus('offline')
    } finally {
      clearInterval(t)
    }
  }, [])

  useEffect(() => { check() }, [check])

  return { status, elapsed, retry: check }
}
