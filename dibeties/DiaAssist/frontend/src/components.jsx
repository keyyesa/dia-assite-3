import { useEffect, useState } from 'react'
import { NavLink, Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from './auth.jsx'
import { api } from './api.js'
import { Icon, Brand } from './icons.jsx'
import { initials } from './lib/ranges.js'

function Bell() {
  const [data, setData] = useState({ unread: 0, items: [] })
  const [open, setOpen] = useState(false)
  const load = () => api.get('/notifications').then(setData).catch(() => {})
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t) }, [])
  const toggle = async () => {
    setOpen(!open)
    if (!open && data.unread) { await api.post('/notifications/read').catch(() => {}); setTimeout(load, 800) }
  }
  return (
    <>
      <button className="bell" onClick={toggle} aria-label="Notifications"><Icon name="bell" size={22} />{data.unread > 0 && <i>{data.unread}</i>}</button>
      {open && (
        <div className="drop">
          {data.items.length === 0 && <div className="muted">No notifications yet.</div>}
          {data.items.map((n) => (
            <div key={n.id} style={{ background: n.read ? '#fff' : '#f0f8f7' }}>{n.text}<div className="muted">{n.created_at?.replace('T', ' ').slice(0, 16)}</div></div>
          ))}
        </div>
      )}
    </>
  )
}

export function Avatar({ name, size = '' }) {
  return <span className={`avatar ${size}`} aria-hidden="true">{initials(name)}</span>
}

export default function Nav() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [open, setOpen] = useState(false)
  useEffect(() => { setOpen(false) }, [loc.pathname])
  const L = ({ to, children }) => <NavLink to={to} end={to === '/'} className={({ isActive }) => (isActive ? 'active' : '')}>{children}</NavLink>
  return (
    <header className={`nav ${open ? 'open' : ''}`}><div className="nav-in">
      <Link to="/" className="brand" aria-label="DiaAssist AI home"><Brand /></Link>
      <button className="burger" onClick={() => setOpen(!open)} aria-label="Menu" aria-expanded={open}><Icon name={open ? 'x' : 'menu'} /></button>
      <nav className="links">
        <L to="/">Home</L><L to="/doctors">Doctors</L>
        {user && <L to="/report">Report analysis</L>}{user && <L to="/assistant">AI assistant</L>}
        {user?.role === 'patient' && <><L to="/appointments">Appointments</L><L to="/history">History</L></>}
        {user && user.role !== 'admin' && <L to="/messages">Messages</L>}
        {user?.role === 'doctor' && <L to="/doctor">My clinic</L>}
        {user?.role === 'admin' && <L to="/admin">Admin</L>}
        <L to="/blogs">Blogs</L><L to="/contact">Contact us</L>
      </nav>
      <div className="right">
        {user ? (<><Bell />
          <Link to="/profile" className="me" title="My profile"><Avatar name={user.name} size="sm" />{user.name}</Link>
          <button className="btn ghost sm" onClick={() => { logout(); nav('/') }}>Log out</button></>)
          : <Link className="btn sm" to="/login">Log in / Sign up</Link>}
      </div>
    </div></header>
  )
}

export const Err = ({ text }) => (text ? <div className="err" role="alert">{text}</div> : null)
export const Ok = ({ text }) => (text ? <div className="ok" role="status">{text}</div> : null)
export function Modal({ title, onClose, children }) {
  return (
    <div className="modal-bg" onClick={onClose}><div className="modal" role="dialog" aria-label={title} onClick={(e) => e.stopPropagation()}>
      <div className="row between"><h3>{title}</h3><button className="btn ghost sm" onClick={onClose} aria-label="Close"><Icon name="x" size={16} /></button></div>{children}
    </div></div>
  )
}
export const stateBadge = (a) => {
  const m = { upcoming: ['green', 'Upcoming'], completed: ['gray', 'Completed'], cancelled: ['red', 'Cancelled'] }[a.state] || ['gray', a.state]
  return <span className={`badge ${m[0]}`}>{m[1]}</span>
}

// A shared lab-report summary (values + status) for the doctor, from an attached report.
import { NAMES, tone, pretty } from './lib/ranges.js'
export function ReportSummary({ report }) {
  const T = { good: 'green', warn: 'amber', bad: 'red', neutral: 'gray' }
  return (
    <div>
      {Object.entries(report).map(([k, v]) => (
        <div className="val" key={k}><b>{NAMES[k] || k}</b><span>{v.value} {v.unit}</span><span className={`badge ${T[tone(v.classification)]}`}>{pretty(v.classification)}</span></div>
      ))}
      <p className="demo">Values were extracted from the patient's report and compared with ADA ranges. Not a diagnosis.</p>
    </div>
  )
}
