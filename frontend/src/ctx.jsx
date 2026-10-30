import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, getToken, setToken } from './api'
import { CheckCircle2, AlertCircle } from 'lucide-react'

const Ctx = createContext(null)
export const useApp = () => useContext(Ctx)

export function AppProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(!getToken())
  const [def, setDef] = useState(null)
  const [toasts, setToasts] = useState([])

  const toast = useCallback((text, tone = 'ok') => {
    const id = Math.random()
    setToasts((t) => [...t, { id, text, tone }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200)
  }, [])

  const loadSession = useCallback(async () => {
    const [u, d] = await Promise.all([api.get('/api/auth/me'), api.get('/api/workflow')])
    setUser(u)
    setDef(d)
  }, [])

  useEffect(() => {
    if (!getToken()) return
    loadSession()
      .catch(() => setToken(null))
      .finally(() => setReady(true))
  }, [loadSession])

  useEffect(() => {
    const out = () => setUser(null)
    window.addEventListener('neo-logout', out)
    return () => window.removeEventListener('neo-logout', out)
  }, [])

  const login = async (email, password) => {
    const r = await api.post('/api/auth/login', { email, password })
    setToken(r.token)
    await loadSession()
  }
  const logout = () => {
    setToken(null)
    setUser(null)
  }

  const value = useMemo(() => {
    const roles = Object.fromEntries((def?.roles || []).map((r) => [r.key, r]))
    const phases = Object.fromEntries((def?.phases || []).map((p) => [p.key, p]))
    const oversight = ['admin', 'otc_director', 'india_director'].includes(user?.role)
    const canAdd = ['initiator', 'admin'].includes(user?.role)
    return { user, ready, def, roles, phases, oversight, canAdd, login, logout, toast, reload: loadSession }
  }, [user, ready, def, toast, loadSession]) // eslint-disable-line

  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.tone}`}>
            {t.tone === 'ok' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  )
}
