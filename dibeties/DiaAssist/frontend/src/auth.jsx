import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { api, getToken, setToken } from './api.js'

const Ctx = createContext(null)
export const useAuth = () => useContext(Ctx)

const GUEST = 'diaassist_guest'
const readGuest = () => { try { return sessionStorage.getItem(GUEST) === '1' } catch { return false } }
const writeGuest = (v) => { try { v ? sessionStorage.setItem(GUEST, '1') : sessionStorage.removeItem(GUEST) } catch { /* ignore */ } }

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)
  const [guest, setGuestState] = useState(readGuest)

  useEffect(() => {
    if (!getToken()) { setReady(true); return }
    api.get('/auth/me').then(setUser).catch(() => setToken(null)).finally(() => setReady(true))
  }, [])

  const login = useCallback(async (email, password, role) => {
    const res = await api.post('/auth/login', { email, password, role })
    setToken(res.token); setUser(res.user); writeGuest(false); setGuestState(false)
    return res.user
  }, [])
  const logout = useCallback(() => { setToken(null); setUser(null); writeGuest(false); setGuestState(false) }, [])
  const continueAsGuest = useCallback(() => { writeGuest(true); setGuestState(true) }, [])

  return <Ctx.Provider value={{ user, setUser, ready, login, logout, guest, continueAsGuest }}>{children}</Ctx.Provider>
}
