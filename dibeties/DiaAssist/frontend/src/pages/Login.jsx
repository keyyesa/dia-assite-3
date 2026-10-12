import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth.jsx'
import { api } from '../api.js'
import { Err, Ok } from '../components.jsx'
import { Icon, Brand } from '../icons.jsx'

const SPECIALITIES = ['Endocrinology', 'Diabetes educator', 'Nutrition', 'Eye care', 'Kidney care', 'Foot care']
const SHOW_DEMO = import.meta.env.DEV || import.meta.env.VITE_SHOW_DEMO === 'true'

// Opens first (route "/" for visitors, and "/login"): intro on the left, sign in / sign up on the right.
export default function Login() {
  const { user, login, continueAsGuest } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [role, setRole] = useState('patient')
  const [mode, setMode] = useState('login')
  const [f, setF] = useState({ email: '', password: '', name: '', diabetes_type: 'Type 2 diabetes', category: 'Endocrinology', qualification: '', fee: 2000, experience_years: 5, bio: '' })
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const target = (u) => loc.state?.from || (u.role === 'doctor' ? '/doctor' : u.role === 'admin' ? '/admin' : '/')

  useEffect(() => { if (user) nav(target(user), { replace: true }) }, [user])  // eslint-disable-line react-hooks/exhaustive-deps

  const pick = (r) => { setRole(r); setError(''); setOk('') }
  const submit = async (e) => {
    e.preventDefault(); setError(''); setOk(''); setBusy(true)
    try {
      if (mode === 'login') {
        await login(f.email.trim(), f.password, role)
      } else if (role !== 'doctor') {
        await api.post('/auth/register/patient', { email: f.email.trim(), name: f.name, password: f.password, diabetes_type: f.diabetes_type })
        await login(f.email.trim(), f.password, 'patient')
      } else {
        const r = await api.post('/auth/register/doctor', { email: f.email.trim(), name: f.name, password: f.password, category: f.category, qualification: f.qualification, fee: Number(f.fee), experience_years: Number(f.experience_years), bio: f.bio })
        setOk(r.message)
      }
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  const guest = () => { continueAsGuest(); nav('/doctors') }
  const isAdmin = role === 'admin'

  return (
    <div className="welcome">
      <section className="welcome-l">
        <div className="brand" style={{ color: '#fff' }}><Brand light size={40} /></div>
        <div>
          <h1>Understand your reports. Reach the right doctor.</h1>
          <p style={{ fontSize: '1.1rem', opacity: .9, maxWidth: 520 }}>Log in to analyse lab reports, ask guideline-based questions and book a diabetes specialist.</p>
          <ul>
            <li><Icon name="flask" /> Lab values explained, abnormal ones flagged</li>
            <li><Icon name="chat" /> AI answers with sources from trusted guidelines</li>
            <li><Icon name="calendar" /> Book appointments and get a token number</li>
          </ul>
        </div>
        <p className="demo" style={{ color: '#ffffffb0' }}>Decision support only. It does not replace a qualified healthcare professional.</p>
      </section>

      <section className="welcome-r">
        <div className="welcome-form">
          <h2>{mode === 'login' ? (isAdmin ? 'Administrator login' : 'Welcome back') : 'Create your account'}</h2>
          <p className="muted" style={{ marginTop: 0 }}>{mode === 'login' ? 'Choose how you want to sign in.' : 'It takes less than a minute.'}</p>
          {!isAdmin && (
            <div className="tabs">
              <button type="button" className={role === 'patient' ? 'on' : ''} onClick={() => pick('patient')}>I am a patient</button>
              <button type="button" className={role === 'doctor' ? 'on' : ''} onClick={() => pick('doctor')}>I am a doctor</button>
            </div>
          )}
          <form className="card" onSubmit={submit}>
            {mode === 'signup' && (<><label style={{ marginTop: 0 }}>Full name</label><input required value={f.name} onChange={set('name')} autoComplete="name" /></>)}
            <label style={mode === 'login' ? { marginTop: 0 } : {}}>Email</label><input required type="email" value={f.email} onChange={set('email')} autoComplete="email" placeholder="you@example.com" />
            <label>Password{mode === 'signup' && ' (at least 6 characters)'}</label><input required type="password" minLength={mode === 'signup' ? 6 : 1} value={f.password} onChange={set('password')} autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} />
            {mode === 'signup' && role !== 'doctor' && (<><label>Diabetes type</label>
              <select value={f.diabetes_type} onChange={set('diabetes_type')}><option>Type 1 diabetes</option><option>Type 2 diabetes</option><option>Gestational diabetes</option><option>Pre-diabetes</option></select></>)}
            {mode === 'signup' && role === 'doctor' && (<>
              <label>Speciality</label>
              <select value={f.category} onChange={set('category')}>{SPECIALITIES.map((c) => <option key={c}>{c}</option>)}</select>
              <label>Qualification</label><input required value={f.qualification} onChange={set('qualification')} placeholder="MBBS, FCPS (Endocrinology)" />
              <div className="row"><div style={{ flex: 1 }}><label>Fee (Rs)</label><input type="number" min="0" value={f.fee} onChange={set('fee')} /></div>
                <div style={{ flex: 1 }}><label>Experience (years)</label><input type="number" min="0" value={f.experience_years} onChange={set('experience_years')} /></div></div>
              <label>Short bio</label><textarea rows={3} value={f.bio} onChange={set('bio')} />
              <p className="muted">New doctor accounts are reviewed and approved by the administrator before login.</p></>)}
            <Err text={error} /><Ok text={ok} />
            <button className="btn block" style={{ marginTop: '1rem' }} disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Sign up'}</button>
            {!isAdmin && (
              <p className="muted" style={{ textAlign: 'center', marginBottom: 0 }}>
                {mode === 'login' ? 'New here? ' : 'Already registered? '}
                <a href="#" onClick={(e) => { e.preventDefault(); setMode(mode === 'login' ? 'signup' : 'login'); setError(''); setOk('') }}>{mode === 'login' ? 'Create an account' : 'Log in'}</a>
              </p>
            )}
          </form>
          <div className="divider">or</div>
          <button className="btn ghost block" onClick={guest}>Continue as guest: browse doctors and blogs</button>
          <p className="muted" style={{ textAlign: 'center' }}>
            <a href="#" onClick={(e) => { e.preventDefault(); setMode('login'); pick(isAdmin ? 'patient' : 'admin') }}>{isAdmin ? 'Back to patient / doctor login' : 'Administrator login'}</a>
          </p>
          {SHOW_DEMO && mode === 'login' && <p className="demo">Demo accounts (development only) — patient: patient@diaassist.ai / patient123 · doctor: sana.malik@diaassist.ai / doctor123 · admin: admin@diaassist.ai / admin123</p>}
        </div>
      </section>
    </div>
  )
}
